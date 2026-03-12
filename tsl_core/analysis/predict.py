import os
import datetime
from matplotlib import pyplot as plt
import numpy as np
import pandas as pd
from scipy.signal import savgol_filter
from sklearn.preprocessing import StandardScaler
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
#  Denoising
#  Torn stock prices are composites of multiple
#  unknown real stocks with per-minute synthetic
#  noise injected. We smooth before computing
#  indicators so they reflect the real underlying
#  composite trend rather than artificial jitter.
# ──────────────────────────────────────────────
def get_smoothing_window(interval):
	"""
	Return an appropriate Savitzky-Golay window size based on the
	data interval. Shorter intervals have more noise and need
	heavier smoothing; longer intervals are already cleaner.
	"""
	windows = {
		"m1": 6, "m5": 5, "m15": 4, "m30": 3,
		"h1": 3, "h2": 3, "h4": 2, "h6": 2,
		"h12": 2, "d1": 2, "w1": 1
	}
	return windows.get(interval, 11)

def denoise_ohlc(df, interval):
	"""
	Apply Savitzky-Golay smoothing to OHLC columns to strip
	Torn's synthetic per-minute noise. Preserves the original
	raw Close as 'Close_raw' for reference.
	"""
	window = get_smoothing_window(interval)
	# Window must be odd and >= polyorder+1
	if window % 2 == 0:
		window += 1
	# Need at least window data points
	if len(df) < window:
		return df

	df["Close_raw"] = df["Close"].copy()
	for col in ["Open", "High", "Low", "Close"]:
		df[col] = savgol_filter(df[col], window_length=window, polyorder=2)
	return df


# ──────────────────────────────────────────────
#  Feature Engineering
#  Biased toward longer windows to ride above the
#  noise floor. Short-period indicators (ROC-1,
#  SMA-5) are omitted since they mostly capture
#  synthetic jitter rather than real signal.
# ──────────────────────────────────────────────
def build_features(df):
	"""
	Build technical-indicator features from OHLC data.
	Returns the dataframe with new columns appended.
	"""
	close = df["Close"]
	high = df["High"]
	low = df["Low"]
	open_ = df["Open"]

	# Simple Moving Averages (longer windows only)
	for window in [10, 20, 50, 100]:
		df[f"sma_{window}"] = close.rolling(window).mean()

	# Exponential Moving Averages (longer spans)
	for span in [10, 20, 50]:
		df[f"ema_{span}"] = close.ewm(span=span, adjust=False).mean()

	# Rate of Change (skip 1-period, too noisy)
	for period in [5, 10, 20]:
		df[f"roc_{period}"] = close.pct_change(period)

	# RSI (14-period is already a good noise-resistant window)
	delta = close.diff()
	gain = delta.clip(lower=0)
	loss = -delta.clip(upper=0)
	avg_gain = gain.rolling(14).mean()
	avg_loss = loss.rolling(14).mean()
	rs = avg_gain / avg_loss.replace(0, np.nan)
	df["rsi_14"] = 100 - (100 / (1 + rs))

	# MACD (12/26/9 are standard and work well post-denoise)
	ema_12 = close.ewm(span=12, adjust=False).mean()
	ema_26 = close.ewm(span=26, adjust=False).mean()
	df["macd"] = ema_12 - ema_26
	df["macd_signal"] = df["macd"].ewm(span=9, adjust=False).mean()
	df["macd_hist"] = df["macd"] - df["macd_signal"]

	# Bollinger Bands (distance from bands, normalised)
	bb_mid = close.rolling(20).mean()
	bb_std = close.rolling(20).std()
	df["bb_upper_dist"] = (close - (bb_mid + 2 * bb_std)) / close
	df["bb_lower_dist"] = (close - (bb_mid - 2 * bb_std)) / close
	df["bb_width"] = (4 * bb_std) / bb_mid

	# ATR (Average True Range)
	tr = pd.DataFrame({
		"hl": high - low,
		"hc": (high - close.shift(1)).abs(),
		"lc": (low - close.shift(1)).abs()
	}).max(axis=1)
	df["atr_14"] = tr.rolling(14).mean()

	# Price relative to moving averages (normalised)
	df["close_to_sma20"] = (close - df["sma_20"]) / df["sma_20"]
	df["close_to_sma50"] = (close - df["sma_50"]) / df["sma_50"]
	df["close_to_sma100"] = (close - df["sma_100"]) / df["sma_100"]

	# SMA crossover signals (trend direction)
	df["sma_20_50_diff"] = (df["sma_20"] - df["sma_50"]) / df["sma_50"]
	df["sma_50_100_diff"] = (df["sma_50"] - df["sma_100"]) / df["sma_100"]

	# Candle body and range info (normalised)
	df["candle_body"] = (close - open_) / close
	df["candle_range"] = (high - low) / close

	# Noise estimate: difference between raw and smoothed close
	# gives the model a sense of current noise magnitude
	if "Close_raw" in df.columns:
		df["noise_magnitude"] = (df["Close_raw"] - close).abs() / close

	return df


def get_feature_columns(df):
	"""Return the list of feature column names (everything we engineered)."""
	exclude = {"date", "Open", "High", "Low", "Close", "Close_raw", "sma", "target"}
	return [c for c in df.columns if c not in exclude]


# ──────────────────────────────────────────────
#  Multi-step recursive forecasting
# ──────────────────────────────────────────────
def recursive_forecast(model, scaler, last_row_features, forecast_steps, df_history, feature_cols, interval):
	"""
	Predict `forecast_steps` into the future by feeding each prediction
	back as the next close price and re-computing features.
	
	Applies EMA smoothing to the output to prevent synthetic noise
	patterns from compounding across recursive steps.
	"""
	hist = df_history.copy()
	predictions = []

	for _ in range(forecast_steps):
		row_scaled = scaler.transform(last_row_features.values.reshape(1, -1))
		pred = model.predict(row_scaled)[0]
		predictions.append(pred)

		# Append the prediction as a new row and rebuild features
		new_row = hist.iloc[-1].copy()
		new_row["Open"] = hist["Close"].iloc[-1]
		new_row["High"] = pred * 1.001
		new_row["Low"] = pred * 0.999
		new_row["Close"] = pred
		new_row["sma"] = pred
		if "Close_raw" in hist.columns:
			new_row["Close_raw"] = pred

		hist = pd.concat([hist, pd.DataFrame([new_row])], ignore_index=True)
		# Re-denoise the extended history to keep indicators clean
		hist = denoise_ohlc(hist, interval)
		hist = build_features(hist)
		last_row_features = hist[feature_cols].iloc[-1]

	# Smooth the final forecast with EMA to remove step-to-step jitter
	predictions = np.array(predictions)
	smooth_span = max(3, len(predictions) // 10)
	smoothed = pd.Series(predictions).ewm(span=smooth_span, adjust=False).mean().values

	return smoothed


# ──────────────────────────────────────────────
#  Main prediction function
# ──────────────────────────────────────────────
def predict_stock(ticker, interval, forecast, render_graphs, json_data, samples=2000):
	nsamples = clamp_(samples, 300, 16000)
	dt = get_stock_from_db(ticker, interval, limit=int(nsamples))

	df = pd.DataFrame(data=dt)

	# ── Denoise: strip Torn's synthetic per-minute noise ──
	df = denoise_ohlc(df, interval)

	# ── Feature engineering ──
	df = build_features(df)

	# Target: the close price `forecast` steps ahead
	df["target"] = df["Close"].shift(-forecast)

	# Drop rows with NaN from indicator warm-up and target shift
	feature_cols = get_feature_columns(df)
	df_clean = df.dropna(subset=feature_cols + ["target"]).copy()

	if len(df_clean) < 100:
		raise ValueError(f"Not enough data to train after feature engineering ({len(df_clean)} rows).")

	X = df_clean[feature_cols].values
	y = df_clean["target"].values

	# ── Chronological split (no data leakage) ──
	split_ratio = 0.85
	split_idx = int(len(X) * split_ratio)
	X_train, X_test = X[:split_idx], X[split_idx:]
	y_train, y_test = y[:split_idx], y[split_idx:]

	# ── Feature scaling ──
	scaler = StandardScaler()
	X_train_s = scaler.fit_transform(X_train)
	X_test_s = scaler.transform(X_test)

	# ── XGBoost ──
	# Higher regularization (alpha/lambda) to resist fitting noise patterns
	# Lower max_depth to prevent memorising noise-driven splits
	model = XGBRegressor(
		n_estimators=600,
		max_depth=5,
		learning_rate=0.04,
		subsample=0.75,
		colsample_bytree=0.7,
		reg_alpha=0.5,
		reg_lambda=2.0,
		min_child_weight=5,
		gamma=0.1,
		objective="reg:squarederror",
		n_jobs=-1,
		verbosity=0
	)
	model.fit(
		X_train_s, y_train,
		eval_set=[(X_test_s, y_test)],
		verbose=False
	)

	# ── Confidence: MAPE-based (0% = useless, 100% = perfect) ──
	# R² can go arbitrarily negative and is meaningless to end users.
	# Instead we use Mean Absolute Percentage Error on the test set:
	#   confidence = clamp(1 - MAPE, 0, 1) * 100
	# A MAPE of 0% error → 100% confidence, 100%+ error → 0% confidence.
	y_pred_test = model.predict(X_test_s)
	nonzero_mask = y_test != 0
	if nonzero_mask.sum() > 0:
		mape = np.mean(np.abs((y_test[nonzero_mask] - y_pred_test[nonzero_mask]) / y_test[nonzero_mask]))
	else:
		mape = 1.0
	confidence = clamp_(1.0 - mape, 0.0, 1.0)

	# ── Multi-step recursive forecast ──
	# Use the tail of the full (non-cleaned) df so indicators are current
	df_full = pd.DataFrame(data=dt)
	df_full = denoise_ohlc(df_full, interval)
	df_full = build_features(df_full)
	last_features = df_full[feature_cols].iloc[-1]
	prediction = recursive_forecast(
		model, scaler, last_features, forecast + 1, df_full, feature_cols, interval
	)

	# ── Current price from json_data ──
	price = 0
	name = ""
	for stock in json_data["data"]:
		if stock["stock"] == ticker.upper():
			price = float(stock["price"])
			name = stock["name"]
			break

	# ── Anchor predictions to the current known price ──
	# Prepend the real price so the forecast line starts from
	# a known point instead of the model's first blind guess.
	prediction = np.insert(prediction, 0, price)

	# ── Build hlvc result structure ──
	hlvc = {}
	hlvc["price"] = price
	hlvc["ticker"] = ticker
	hlvc["confidence"] = confidence

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

	# ── Timestamps ──
	period = int("".join(filter(str.isdigit, interval)))
	period_ticks = []
	current_time = datetime.datetime.utcnow().timestamp()
	current_time_str = datetime.datetime.fromtimestamp(current_time).strftime('%H:%M:%S %d/%m/%y')
	period_ticks.append(current_time_str)

	multipliers = {"m": 60, "h": 3600, "d": 86400, "w": 604800, "n": 26355200, "y": 31536000}
	base = multipliers.get(interval[0], 60)

	for i in range(2, 10):
		ts = current_time + int(((base * (period * forecast)) / 9) * i)
		period_ticks.append(datetime.datetime.fromtimestamp(ts).strftime('%H:%M:%S %d/%m/%y'))

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