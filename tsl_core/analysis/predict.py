import os
import math
import datetime
import matplotlib
# Headless backend: graphs are rendered off the main thread, which the default
# TkAgg backend on Windows does not support.
matplotlib.use("Agg")
from matplotlib import pyplot as plt
import numpy as np
import pandas as pd
from sklearn.model_selection import TimeSeriesSplit
from xgboost import XGBRegressor
from tsl_core.db import get_stock_from_db
from io import BytesIO

# Helpers
def remap(val, val_min, val_max, map_min, map_max):
	return (val - val_min) / (val_max - val_min) * (map_max - map_min) + map_min

def clamp_(val, min_val, max_val):
	if val <= min_val:
		return min_val
	elif val >= max_val:
		return max_val
	else:
		return val

# ──────────────────────────────────────────────
#  Design notes
#  Torn prices track hidden real-world stocks plus per-minute jitter, so they
#  behave close to a random walk. The pipeline is built to be honest about that:
#   • Every feature is causal (row t uses only prices up to t) and price-level
#     free, computed on raw closes. No centred smoothing: a centred filter leaks
#     future prices into features and target.
#   • Targets are log returns, so trees are not capped by the training price range.
#   • A few direct models at anchor horizons replace recursive feedback.
#   • Skill is measured walk-forward against "no change" and "drift" baselines.
# ──────────────────────────────────────────────

# Longest indicator window; rows before this have incomplete features.
WARMUP = 100
# Fraction points of the forecast horizon that get their own direct model.
ANCHOR_FRACTIONS = (0.25, 0.5, 0.75, 1.0)
MIN_TRAIN_ROWS = 150
MAX_TREES = 800
EARLY_STOPPING_ROUNDS = 50


# ──────────────────────────────────────────────
#  Feature Engineering (causal, scale-free)
# ──────────────────────────────────────────────
def build_features(df, has_ohlc=True):
	"""
	Build causal, price-level-free features from raw OHLC data.
	Every value at row t depends only on rows <= t, so computing features on
	a prefix of the series gives identical rows (see tests/test_predict.py).
	`has_ohlc` is False for m1, where the DB stores one price in all four
	columns and candle-shape features would be constant zero.
	Returns a new dataframe of feature columns aligned to df's index.
	"""
	close = df["Close"].astype(float)
	high = df["High"].astype(float)
	low = df["Low"].astype(float)
	open_ = df["Open"].astype(float)
	log_close = np.log(close)
	ret_1 = log_close.diff()
	f = pd.DataFrame(index=df.index)

	# Multi-horizon momentum
	for k in [1, 3, 5, 10, 20, 50]:
		f[f"logret_{k}"] = log_close - log_close.shift(k)

	# Distance from moving averages
	sma = {w: close.rolling(w).mean() for w in [10, 20, 50, 100]}
	for w, s in sma.items():
		f[f"close_to_sma{w}"] = close / s - 1
	for span in [10, 20, 50]:
		f[f"close_to_ema{span}"] = close / close.ewm(span=span, adjust=False).mean() - 1
	f["sma_20_50_diff"] = sma[20] / sma[50] - 1
	f["sma_50_100_diff"] = sma[50] / sma[100] - 1

	# RSI (14)
	delta = close.diff()
	avg_gain = delta.clip(lower=0).rolling(14).mean()
	avg_loss = (-delta.clip(upper=0)).rolling(14).mean()
	rs = avg_gain / avg_loss.replace(0, np.nan)
	f["rsi_14"] = 100 - (100 / (1 + rs))

	# MACD, normalised by price
	macd = close.ewm(span=12, adjust=False).mean() - close.ewm(span=26, adjust=False).mean()
	macd_signal = macd.ewm(span=9, adjust=False).mean()
	f["macd"] = macd / close
	f["macd_signal"] = macd_signal / close
	f["macd_hist"] = (macd - macd_signal) / close

	# Bollinger Bands
	bb_mid = sma[20]
	bb_std = close.rolling(20).std()
	f["bb_upper_dist"] = (close - (bb_mid + 2 * bb_std)) / close
	f["bb_lower_dist"] = (close - (bb_mid - 2 * bb_std)) / close
	f["bb_width"] = (4 * bb_std) / bb_mid

	# ATR, normalised by price
	tr = pd.DataFrame({
		"hl": high - low,
		"hc": (high - close.shift(1)).abs(),
		"lc": (low - close.shift(1)).abs()
	}).max(axis=1)
	f["atr_14"] = tr.rolling(14).mean() / close

	# Realised volatility and a short/long regime ratio
	for w in [10, 20, 50]:
		f[f"vol_{w}"] = ret_1.rolling(w).std()
	f["vol_ratio_10_50"] = f["vol_10"] / f["vol_50"].replace(0, np.nan)
	f["zmom_20"] = f["logret_20"] / (f["vol_20"] * math.sqrt(20)).replace(0, np.nan)

	# Position within the recent range (0 = at the low, 1 = at the high)
	for w in [50, 100]:
		lo = low.rolling(w).min()
		hi = high.rolling(w).max()
		f[f"range_pos_{w}"] = (close - lo) / (hi - lo).replace(0, np.nan)

	if has_ohlc:
		f["candle_body"] = (close - open_) / close
		f["candle_range"] = (high - low) / close

	return f.replace([np.inf, -np.inf], np.nan)


def anchor_horizons(forecast):
	"""Distinct horizons (in candles) that each get their own direct model."""
	return sorted({max(1, math.ceil(forecast * frac)) for frac in ANCHOR_FRACTIONS})


def required_samples(forecast):
	"""Candles needed for warm-up, the target shift and at least two backtest folds."""
	return WARMUP + 2 * forecast + 400


def _model_params(n_train):
	# Shallower, more regularised trees on small samples, where depth mostly fits noise.
	small = n_train < 1500
	return dict(
		max_depth=3 if small else 4,
		min_child_weight=10 if small else 5,
		learning_rate=0.05,
		subsample=0.8,
		colsample_bytree=0.7,
		reg_alpha=0.5,
		reg_lambda=5.0,
		gamma=0.0,
		objective="reg:absoluteerror",
		tree_method="hist",
		device="cpu",
		n_jobs=-1,
		verbosity=0,
	)


def _fit_early_stopped(X, y, gap):
	"""
	Fit on X/y holding out the most recent slice as a validation set (separated
	by `gap` rows so overlapping labels cannot leak). Returns (model, n_trees).
	"""
	n = len(X)
	n_val = max(30, n // 7)
	val_start = n - n_val
	train_end = val_start - gap
	if train_end < MIN_TRAIN_ROWS:
		# Too short to hold out a validation slice: use a fixed conservative size.
		model = XGBRegressor(n_estimators=200, **_model_params(n))
		model.fit(X, y, verbose=False)
		return model, 200
	model = XGBRegressor(n_estimators=MAX_TREES, early_stopping_rounds=EARLY_STOPPING_ROUNDS,
		eval_metric="mae", **_model_params(train_end))
	model.fit(X[:train_end], y[:train_end], eval_set=[(X[val_start:], y[val_start:])], verbose=False)
	return model, int(model.best_iteration) + 1


def walk_forward_evaluate(X, y, horizon):
	"""
	Expanding-window backtest with a `horizon`-row gap between train and test.
	Scores the model's return MAE against two baselines: zero return ("price
	stays put") and drift (the training set's mean return).
	Returns a dict of skill metrics and the median early-stopped tree count.
	"""
	n = len(X)
	test_size = max(30, n // 10)
	n_splits = 4
	while n_splits >= 2 and n - n_splits * test_size - horizon < MIN_TRAIN_ROWS:
		n_splits -= 1
	if n_splits < 2:
		raise ValueError(f"Not enough data to backtest a {horizon}-candle forecast ({n} usable rows).")

	tss = TimeSeriesSplit(n_splits=n_splits, test_size=test_size, gap=horizon)
	skills, skills_naive, hits, moves, baseline_hits, trees = [], [], 0, 0, 0, []
	for train_idx, test_idx in tss.split(X):
		model, n_trees = _fit_early_stopped(X[train_idx], y[train_idx], horizon)
		trees.append(n_trees)
		y_test = y[test_idx]
		pred = model.predict(X[test_idx])
		mae_model = np.mean(np.abs(y_test - pred))
		mae_naive = np.mean(np.abs(y_test))
		mae_drift = np.mean(np.abs(y_test - np.mean(y[train_idx])))
		best_baseline = min(mae_naive, mae_drift)
		skills.append(1 - mae_model / best_baseline if best_baseline > 0 else 0.0)
		skills_naive.append(1 - mae_model / mae_naive if mae_naive > 0 else 0.0)

		# Directional accuracy on moves big enough to matter
		threshold = 0.25 * np.median(np.abs(y_test))
		moved = np.abs(y_test) > threshold
		hits += int(np.sum(np.sign(pred[moved]) == np.sign(y_test[moved])))
		moves += int(np.sum(moved))
		# Baseline: always call the training set's drift direction (knowable in advance)
		drift_sign = 1.0 if np.mean(y[train_idx]) >= 0 else -1.0
		baseline_hits += int(np.sum(np.sign(y_test[moved]) == drift_sign))

	return {
		"skill": float(np.median(skills)),
		"skill_vs_no_change": float(np.median(skills_naive)),
		"direction_accuracy": hits / moves if moves else 0.0,
		"direction_baseline": baseline_hits / moves if moves else 0.0,
		"folds": n_splits,
		"n_trees": int(np.median(trees)),
	}


def skill_label(skill):
	if skill < 0.01:
		return "No edge"
	if skill < 0.05:
		return "Weak"
	if skill < 0.15:
		return "Moderate"
	return "Strong"


def forecast_returns(df, interval, forecast):
	"""
	Train direct log-return models on a raw OHLC dataframe and forecast
	`forecast` candles ahead. Returns (path_returns, metrics) where
	path_returns[i] is the predicted log return from the last close to step i
	(path_returns[0] == 0), and metrics comes from walk_forward_evaluate.
	"""
	feats = build_features(df, has_ohlc=(interval != "m1"))
	feature_cols = list(feats.columns)
	log_close = np.log(df["Close"].astype(float))
	# Drop only the warm-up rows. Other NaNs (e.g. a volatility ratio over a
	# flat stretch) are left for XGBoost, which handles missing values natively.
	valid = feats["close_to_sma100"].notna()

	# Backtest at the full horizon: that is what the user asked about.
	y_full = (log_close.shift(-forecast) - log_close)
	rows = valid & y_full.notna()
	if rows.sum() < MIN_TRAIN_ROWS + 60:
		raise ValueError(f"Not enough data to train after feature engineering ({int(rows.sum())} rows).")
	metrics = walk_forward_evaluate(feats[rows].values, y_full[rows].values, forecast)

	# Refit each anchor horizon on all available rows, so the most recent
	# candles inform the live forecast, using the backtest's tree count.
	last_row = feats[feature_cols].iloc[[-1]].values
	if not valid.iloc[-1]:
		raise ValueError("Latest candle has incomplete features.")
	anchors = anchor_horizons(forecast)
	anchor_preds = [0.0]
	for k in anchors:
		y_k = log_close.shift(-k) - log_close
		rows_k = valid & y_k.notna()
		model = XGBRegressor(n_estimators=metrics["n_trees"], **_model_params(int(rows_k.sum())))
		model.fit(feats[rows_k].values, y_k[rows_k].values, verbose=False)
		anchor_preds.append(float(model.predict(last_row)[0]))

	# Interpolate log returns between anchors for a smooth path.
	path_returns = np.interp(np.arange(forecast + 1), [0] + anchors, anchor_preds)
	return path_returns, metrics


# ──────────────────────────────────────────────
#  Main prediction function
# ──────────────────────────────────────────────
def predict_stock(ticker, interval, forecast, render_graphs, json_data, samples=2000):
	forecast = max(1, int(forecast))
	# Long horizons need extra history for warm-up, targets and backtest folds.
	nsamples = clamp_(max(int(samples), required_samples(forecast)), 300, 16000)
	dt = get_stock_from_db(ticker, interval, limit=int(nsamples))
	df = pd.DataFrame(data=dt)

	path_returns, metrics = forecast_returns(df, interval, forecast)

	# ── Current price from json_data ──
	price = 0
	name = ""
	for stock in json_data["data"]:
		if stock["stock"] == ticker.upper():
			price = float(stock["price"])
			name = stock["name"]
			break
	if price <= 0:
		price = float(df["Close"].iloc[-1])

	# Apply the predicted returns to the live price, so the forecast starts
	# exactly at the current price with no jump.
	prediction = price * np.exp(path_returns)

	# ── Build hlvc result structure ──
	hlvc = {}
	hlvc["price"] = price
	hlvc["ticker"] = ticker
	# Backtested skill against the better of the no-change and drift baselines.
	# 0 means no better than assuming the price stays put.
	hlvc["confidence"] = clamp_(metrics["skill"], 0.0, 1.0)
	hlvc["skill"] = metrics["skill"]
	hlvc["skill_label"] = skill_label(metrics["skill"])
	hlvc["skill_vs_no_change"] = metrics["skill_vs_no_change"]
	hlvc["direction_accuracy"] = metrics["direction_accuracy"]
	hlvc["direction_baseline"] = metrics["direction_baseline"]
	hlvc["folds"] = metrics["folds"]

	hlvc["high"] = 0
	hlvc["low"] = 1e10
	hlvc["volatility"] = 0
	hlvc["actual"] = 0

	for val in prediction:
		if val > hlvc["high"]:
			hlvc["high"] = val
		if val < hlvc["low"]:
			hlvc["low"] = val
		perc = abs(float((price - val) / val) * 100) if val != 0 else 0
		aperc = float((price - val) / val) * -100 if val != 0 else 0
		if perc > hlvc["volatility"]:
			hlvc["volatility"] = perc
			hlvc["actual"] = aperc

	# Append predictions into dt["sma"] for graph compatibility
	for val in prediction:
		dt["sma"].append(val)

	# ── Timestamps (TCT is UTC; the DB dates are formatted in UTC too) ──
	period = int("".join(filter(str.isdigit, interval)))
	period_ticks = []
	utc = datetime.timezone.utc
	current_time = datetime.datetime.now(utc).timestamp()
	period_ticks.append(datetime.datetime.fromtimestamp(current_time, utc).strftime('%H:%M:%S %d/%m/%y'))

	multipliers = {"m": 60, "h": 3600, "d": 86400, "w": 604800, "n": 26355200, "y": 31536000}
	base = multipliers.get(interval[0], 60)

	for i in range(1, 9):
		ts = current_time + int(((base * (period * forecast)) / 8) * i)
		period_ticks.append(datetime.datetime.fromtimestamp(ts, utc).strftime('%H:%M:%S %d/%m/%y'))

	# Number of trailing real candles to show before the prediction,
	# tuned per interval to give useful context without overwhelming.
	trailing_candles = {
		"m1": 60, "m5": 48, "m15": 24, "m30": 16,
		"h1": 12, "h2": 12, "h4": 12, "h6": 16,
		"h12": 8, "d1": 7, "w1": 4
	}

	file = ""
	if render_graphs:
		n_trailing = trailing_candles.get(interval, 12)
		n_trailing *= 4
		# Clamp to available data
		n_trailing = min(n_trailing, len(dt["Close"]))

		# Pull trailing real close prices
		real_prices = dt["Close"][-n_trailing:]

		# The anchor index is where real data ends and predictions begin
		anchor_idx = n_trailing - 1  # last real price is at this index

		# Build the combined plot series:
		#   [0 .. anchor_idx] = real history
		#   [anchor_idx .. anchor_idx + len(prediction)] = forecast (overlaps at anchor)
		# Prediction x-coords start at the anchor so the lines connect
		pred_x = list(range(anchor_idx, anchor_idx + len(prediction)))

		# Build timestamp labels for the trailing real data
		# Use the stored dates from the DB for the history portion
		real_dates = dt["date"][-n_trailing:]

		# SMA trend line spanning real + prediction zone
		sma_avg = []
		sma_amt = 15
		sma_start = len(dt["sma"]) - n_trailing
		for f in range(n_trailing + len(prediction)):
			idx = sma_start + f
			start = max(0, idx - sma_amt + 1)
			end = min(len(dt["sma"]), idx + 1)
			count = end - start
			if count <= 0:
				sma_avg.append(sma_avg[-1] if sma_avg else price)
				continue
			sma_val = sum(float(dt["sma"][i]) for i in range(start, end))
			sma_avg.append(sma_val / count)

		# X-axis tick positions spread across the full range
		total_len = n_trailing + len(prediction) - 1  # -1 because anchor overlaps
		n_ticks = 9
		xtick_positions = [float(total_len / (n_ticks - 1)) * i for i in range(n_ticks)]

		# Build labels: first tick from real data, "Now" at anchor, rest from forecast
		xtick_labels = []
		for pos in xtick_positions:
			idx = int(round(pos))
			if idx <= anchor_idx:
				if idx < len(real_dates):
					xtick_labels.append(real_dates[idx])
				else:
					xtick_labels.append("")
			else:
				# Map to period_ticks (forecast timestamps)
				forecast_idx = idx - anchor_idx
				# Scale into period_ticks (which has 9 entries for the forecast range)
				pt_idx = int(round(forecast_idx / max(len(prediction) - 1, 1) * 8))
				pt_idx = min(pt_idx, len(period_ticks) - 1)
				xtick_labels.append(period_ticks[pt_idx])

		# Override the label nearest to the anchor with "Now"
		closest_to_anchor = min(range(len(xtick_positions)), key=lambda i: abs(xtick_positions[i] - anchor_idx))
		xtick_labels[closest_to_anchor] = "Now"

		plt.style.use("ggplot")
		fig, ax = plt.subplots(figsize=(10, 5))

		# Real price history
		ax.plot(range(n_trailing), real_prices, linewidth=1.5, alpha=0.8, color="#4CAF50", label="Real Price", zorder=2)
		ax.plot(range(n_trailing), real_prices, linewidth=8, alpha=0.06, color="#4CAF50", zorder=1)

		# Prediction line (starts from anchor point = current price)
		ax.plot(pred_x, prediction, linewidth=2, alpha=0.9, color="#2196F3", label="XGBoost", zorder=2)
		ax.plot(pred_x, prediction, linewidth=10, alpha=0.08, color="#2196F3", zorder=1)

		# Anchor point marker
		ax.plot(anchor_idx, price, marker="o", markersize=7, color="#2196F3", zorder=3)

		# Vertical divider at "Now"
		ax.axvline(x=anchor_idx, color="gray", linewidth=1, linestyle="--", alpha=0.5)

		# SMA trend spanning both zones
		ax.plot(sma_avg[:total_len + 1], label="Trend", alpha=0.7, color="#ff8a00", linewidth=1.5, linestyle="--", zorder=0, dashes=(5, 2))

		# Current price reference line
		ax.axhline(y=price, color="gray", linewidth=0.8, linestyle=":", alpha=0.4, label=f"Current (${price:.2f})")

		plt.title(name + " Price Prediction (" + interval + ", " + str(forecast) + ")")
		ax.yaxis.set_major_formatter('${x:1.2f}')
		ax.set_xticks(xtick_positions)
		ax.set_xticklabels(xtick_labels)
		plt.xticks(rotation=45, horizontalalignment="right")
		plt.legend(loc="best", fontsize="small")
		plt.tight_layout()
		plt.grid(color="black", linestyle="--", linewidth=0.5)

		if not os.path.isdir(os.getcwd() + "/graphs"):
			os.mkdir(os.getcwd() + "/graphs")

		file = BytesIO()
		plt.savefig(file, dpi=120)
		plt.close()
		file.seek(0)

	return [file, hlvc, name, period_ticks]
