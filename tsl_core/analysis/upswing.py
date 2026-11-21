"""
Longer-term upswing detection for automated suggestions.

Rather than forecasting a price path, this asks a narrower question that can be
checked afterwards: "from today's daily close, will this stock be at least
X% higher at the close N days from now?" Training on the close rather than an
intraday spike keeps the gain honest - it has to stick. One classifier is trained per horizon, pooled
across every stock's d1 history so it has enough examples to learn from.

Horizons:
	daily  - +0.5% after 3 days
	weekly - +1.0% after 7 days

Every model also scores itself on a held-out final year it never trained on,
so the bot can quote an honest track record (precision of the top picks vs
the base rate of the target simply happening) instead of a bare confidence.
"""
import threading
import time
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import talib
from xgboost import XGBClassifier

from tsl_core.db import get_stock_df, fill_daily_gaps_from_tornsy

# Horizon definitions. Torn trades 24/7, so days are calendar days.
# min_lift: a pick must be at least this many times more likely than the base rate.
# Tuned on the holdout year - lower floods the weekly list, higher starves the daily one.
HORIZONS = {
	"daily":  {"days": 3, "threshold": 0.005, "min_lift": 1.5, "label": "Daily",  "desc": "+0.5% after 3 days"},
	"weekly": {"days": 7, "threshold": 0.010, "min_lift": 2.0, "label": "Weekly", "desc": "+1.0% after 7 days"},
}

# Need enough completed history for the slowest indicator (SMA100) plus a buffer
MIN_HISTORY_DAYS = 130
# Final stretch of history used to grade the model before the production fit
HOLDOUT_DAYS = 365

_MODEL_PARAMS = dict(
	n_estimators=300,
	max_depth=3,
	learning_rate=0.03,
	subsample=0.8,
	colsample_bytree=0.8,
	min_child_weight=20,
	verbosity=0,
	n_jobs=-1,
)

FEATURES = [
	"ret1", "ret3", "ret5", "ret10", "ret20", "ret60",
	"sma10", "sma20", "sma50", "sma100",
	"rsi7", "rsi14", "stoch_k", "stoch_d", "macd_hist",
	"bb_pos", "bb_width", "atr", "vol20", "range1",
	"dd20", "du20", "dow",
	"w_ret1", "w_ret4", "w_rsi", "w_sma10",
]


class StaleDataError(RuntimeError):
	pass


def _today_start():
	now = int(datetime.now(timezone.utc).timestamp())
	return now - (now % 86400)


def load_daily(ticker):
	"""Completed daily candles for a ticker, indexed by UTC day (TCT)."""
	df = get_stock_df(ticker, "d1")
	# The current day's candle is still forming; using it would mismatch training
	df = df[df["date"] < _today_start()]
	df.index = pd.to_datetime(df["date"], unit="s")
	return df


def build_features(df):
	"""Technical features computed only from data available at each day's close."""
	c, h, l = df["close"], df["high"], df["low"]
	f = pd.DataFrame(index=df.index)

	for n in [1, 3, 5, 10, 20, 60]:
		f["ret" + str(n)] = c.pct_change(n)
	for n in [10, 20, 50, 100]:
		f["sma" + str(n)] = c / c.rolling(n).mean() - 1

	f["rsi7"] = talib.RSI(c, 7)
	f["rsi14"] = talib.RSI(c, 14)
	k, d = talib.STOCH(h, l, c, 14, 3, 0, 3, 0)
	f["stoch_k"] = k
	f["stoch_d"] = d
	_, _, hist = talib.MACD(c)
	f["macd_hist"] = hist / c
	upper, mid, lower = talib.BBANDS(c, 20)
	f["bb_pos"] = (c - lower) / (upper - lower)
	f["bb_width"] = (upper - lower) / mid
	f["atr"] = talib.ATR(h, l, c, 14) / c
	f["vol20"] = c.pct_change().rolling(20).std()
	f["range1"] = (h - l) / c
	f["dd20"] = c / h.rolling(20).max() - 1
	f["du20"] = c / l.rolling(20).min() - 1
	f["dow"] = df.index.dayofweek

	# Weekly context. Bars are Monday-Sunday and only become visible once the
	# week has closed, so a Wednesday never sees the rest of its own week.
	wk = df.resample("W-MON", label="left", closed="left").agg({"close": "last"})
	wf = pd.DataFrame(index=wk.index)
	wf["w_ret1"] = wk["close"].pct_change(1)
	wf["w_ret4"] = wk["close"].pct_change(4)
	wf["w_rsi"] = talib.RSI(wk["close"], 14)
	wf["w_sma10"] = wk["close"] / wk["close"].rolling(10).mean() - 1
	wf.index = wf.index + pd.Timedelta(days=7)
	f = f.join(wf.reindex(f.index, method="ffill"))
	return f


def build_labels(df, days):
	"""
	Forward close return over `days`, and the best high reached within that window.
	Shifts happen on a gap-free calendar, so a missing day yields NaN instead of
	silently comparing against a close from weeks later.
	"""
	cal = df[["close", "high"]].asfreq("D")
	fwd_close = cal["close"].shift(-days) / cal["close"] - 1
	# min_periods=days: any missing day inside the window voids the label
	fwd_high = cal["high"][::-1].rolling(days, min_periods=days).max()[::-1].shift(-1) / cal["close"] - 1
	return fwd_close.reindex(df.index), fwd_high.reindex(df.index)


def build_features_segmented(df):
	"""
	Indicators assume consecutive candles, so compute them separately for each
	unbroken run of days. Runs too short to warm up the indicators come out NaN
	and get dropped rather than bridging a gap with misleading values.
	"""
	segment = (df.index.to_series().diff() > pd.Timedelta(days=1)).cumsum()
	parts = [build_features(part) for _, part in df.groupby(segment) if len(part) >= MIN_HISTORY_DAYS]
	if not parts:
		return pd.DataFrame(columns=FEATURES)
	return pd.concat(parts)


def build_dataset(tickers):
	frames = []
	for ticker in tickers:
		try:
			df = load_daily(ticker)
		except Exception:
			continue
		if len(df) < MIN_HISTORY_DAYS:
			continue
		f = build_features_segmented(df)
		if len(f) == 0:
			continue
		f["ticker"] = ticker.upper()
		f["close"] = df["close"]
		for name, hz in HORIZONS.items():
			fwd_close, fwd_high = build_labels(df, hz["days"])
			f["y_" + name] = fwd_close
			f["yh_" + name] = fwd_high
		frames.append(f)
	if not frames:
		raise RuntimeError("No stock history available to build the suggestion dataset.")
	data = pd.concat(frames)
	return data.dropna(subset=["sma100", "ret60"])


def _top_n_per_day(frame, n, col="p"):
	return frame.groupby(level=0, group_keys=False).apply(lambda g: g.nlargest(n, col))


def evaluate_holdout(data, horizon, min_lift=None):
	"""
	Train on everything before the final HOLDOUT_DAYS, then score the unseen
	final stretch the same way the bot would pick. Returns summary statistics.
	"""
	hz = HORIZONS[horizon]
	if min_lift is None:
		min_lift = hz["min_lift"]
	y_col = "y_" + horizon
	labelled = data.dropna(subset=[y_col])
	cutoff = labelled.index.max() - pd.Timedelta(days=HOLDOUT_DAYS)
	# Purge a horizon's worth of days so training labels can't peek into the test window
	train = labelled[labelled.index < cutoff - pd.Timedelta(days=hz["days"] + 1)]
	test = labelled[labelled.index >= cutoff]
	if len(train) == 0 or len(test) == 0:
		return None

	model = XGBClassifier(**_MODEL_PARAMS)
	model.fit(train[FEATURES], (train[y_col] >= hz["threshold"]).astype(int))
	test = test.assign(p=model.predict_proba(test[FEATURES])[:, 1])
	test = test.assign(hit=(test[y_col] >= hz["threshold"]).astype(int))

	base_rate = float(test["hit"].mean())
	top = _top_n_per_day(test, 3)
	picks = test[test["p"] >= base_rate * min_lift]
	n_days = test.index.nunique()
	return {
		"from": test.index.min().strftime("%d/%m/%y"),
		"to": test.index.max().strftime("%d/%m/%y"),
		"base_rate": base_rate,
		"base_avg_return": float(test[y_col].mean()),
		"top3_precision": float(top["hit"].mean()),
		"top3_avg_return": float(top[y_col].mean()),
		"top3_win_rate": float((top[y_col] > 0).mean()),
		"top3_touch_rate": float((top["yh_" + horizon] >= hz["threshold"]).mean()),
		"lift_picks_per_day": len(picks) / n_days if n_days else 0.0,
		"lift_precision": float(picks["hit"].mean()) if len(picks) else float("nan"),
		"lift_avg_return": float(picks[y_col].mean()) if len(picks) else float("nan"),
	}


class _ModelCache:
	"""Trains each horizon's model at most once per completed day."""
	def __init__(self):
		self._lock = threading.Lock()
		self._day = None
		self._data = None
		self._models = {}
		self._stats = {}

	def get(self, tickers):
		with self._lock:
			today = _today_start()
			if self._day != today or self._data is None:
				for ticker in tickers:
					try:
						fill_daily_gaps_from_tornsy(ticker)
					except Exception:
						pass  # Train on whatever local history exists
					time.sleep(0.05)
				self._data = build_dataset(tickers)
				self._models = {}
				self._stats = {}
				self._day = today

			for name, hz in HORIZONS.items():
				if name in self._models:
					continue
				y_col = "y_" + name
				labelled = self._data.dropna(subset=[y_col])
				model = XGBClassifier(**_MODEL_PARAMS)
				model.fit(labelled[FEATURES], (labelled[y_col] >= hz["threshold"]).astype(int))
				self._models[name] = model
				self._stats[name] = evaluate_holdout(self._data, name)
			return self._data, self._models, self._stats

	def invalidate(self):
		with self._lock:
			self._day = None


_cache = _ModelCache()


def _signal_notes(row):
	"""Short human-readable context for why a stock looks set up."""
	notes = []
	if row["rsi14"] < 35:
		notes.append("RSI oversold (" + "{:.0f}".format(row["rsi14"]) + ")")
	elif row["rsi14"] > 65:
		notes.append("RSI strong (" + "{:.0f}".format(row["rsi14"]) + ")")
	if row["bb_pos"] < 0.15:
		notes.append("near lower Bollinger band")
	if row["dd20"] < -0.03:
		notes.append("{:.1f}".format(row["dd20"] * 100) + "% off 20d high")
	if row["macd_hist"] > 0 and row["ret3"] < 0:
		notes.append("MACD positive on a dip")
	if row["sma50"] > 0 and row["sma20"] < 0:
		notes.append("pullback within uptrend")
	if row["w_rsi"] < 40:
		notes.append("weekly RSI low (" + "{:.0f}".format(row["w_rsi"]) + ")")
	if not notes:
		notes.append("mixed indicators, model composite")
	return ", ".join(notes[:3])


def scan(horizon, tickers, top_n=3, min_lift=None):
	"""
	Rank every stock by its chance of reaching the horizon's target from the
	latest completed daily close.

	Returns a dict with the picks (passing min_lift), the full ranking, the
	base rate for context and the model's holdout statistics.
	"""
	if horizon not in HORIZONS:
		raise ValueError("Unknown horizon: " + repr(horizon))
	hz = HORIZONS[horizon]
	if min_lift is None:
		min_lift = hz["min_lift"]
	data, models, stats = _cache.get(tickers)

	latest_day = data.index.max()
	# Features for yesterday's close need an unbroken run of recent history; if the
	# gap fill failed the newest usable row could be months old, so refuse instead
	if int(latest_day.timestamp()) < _today_start() - 86400:
		_cache.invalidate()
		raise StaleDataError("Latest usable daily candle is " + latest_day.strftime("%d/%m/%y") + "; daily history needs repairing before suggestions can run.")
	latest = data[data.index == latest_day].dropna(subset=FEATURES).copy()
	latest["p"] = models[horizon].predict_proba(latest[FEATURES])[:, 1]
	latest = latest.sort_values("p", ascending=False)

	hz_stats = stats.get(horizon)
	labelled = data.dropna(subset=["y_" + horizon])
	base_rate = hz_stats["base_rate"] if hz_stats else float((labelled["y_" + horizon] >= hz["threshold"]).mean())

	ranking = []
	for day, row in latest.iterrows():
		ranking.append({
			"ticker": row["ticker"],
			"probability": float(row["p"]),
			"lift": float(row["p"]) / base_rate if base_rate > 0 else 0.0,
			"close": float(row["close"]),
			"target": float(row["close"]) * (1 + hz["threshold"]),
			"atr_pct": float(row["atr"]) * 100,
			"rsi": float(row["rsi14"]),
			"notes": _signal_notes(row),
		})

	picks = [r for r in ranking if r["lift"] >= min_lift][:top_n]
	return {
		"horizon": horizon,
		"as_of": int(latest_day.timestamp()),
		"expires": int(latest_day.timestamp()) + 86400 * (hz["days"] + 1),
		"base_rate": base_rate,
		"min_lift": min_lift,
		"picks": picks,
		"ranking": ranking,
		"stats": hz_stats,
	}


def outcome(ticker, as_of, horizon, entry, target):
	"""
	Grade a past suggestion once its window has fully closed.
	Returns None while still open, else (closed_at_target, touched_target,
	return_at_expiry, best_high_return).
	"""
	hz = HORIZONS[horizon]
	start = as_of + 86400
	end = as_of + 86400 * hz["days"]
	if _today_start() <= end:
		return None
	df = get_stock_df(ticker, "d1")
	window = df[(df["date"] >= start) & (df["date"] <= end)]
	if len(window) == 0:
		return None
	best = float(window["high"].max())
	final = float(window["close"].iloc[-1])
	return (final >= target, best >= target, final / entry - 1, best / entry - 1)
