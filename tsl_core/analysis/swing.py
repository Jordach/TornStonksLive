"""
Longer-term swing detection for automated suggestions.

Two kinds of pick, each asking a question that can be checked afterwards:

	up  (Upswing)     - "from today's daily close, will this stock close at least
	                    X% higher N days from now?" A pick also needs at least a
	                    couple of leading technical signals agreeing (momentum
	                    turning up from oversold, a stochastic cross, ...), so it
	                    is flagged *before* the move rather than after it.
	dip (Buy the dip) - "will it dip X% within N days and then recover to X%
	                    above today's close?" These are stocks expected to drop
	                    soon but not stay down: set a buy order at the dip price
	                    and hold for the recovery.

Horizons:
	daily  - 0.5% moves: upswing after 3 days; dip within 3 days, recovered by day 14
	weekly - 1.0% moves: upswing after 7 days; dip within 7 days, recovered by day 30

One classifier is trained per horizon and kind, pooled across every stock's d1
history. Every model also scores itself on a held-out final year it never
trained on, using the same rules the bot picks with, so the posts can quote an
honest track record instead of a bare confidence.
"""
import math
import threading
import time
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import talib
from xgboost import XGBClassifier

from tsl_core.analysis.search import BULLISH_PATTERNS, BEARISH_PATTERNS
from tsl_core.db import get_stock_df, fill_daily_gaps_from_tornsy

# Horizon definitions. Torn trades 24/7, so days are calendar days.
HORIZONS = {
	"daily":  {"days": 3, "recover_days": 14, "threshold": 0.005, "label": "Daily"},
	"weekly": {"days": 7, "recover_days": 30, "threshold": 0.010, "label": "Weekly"},
}

# min_lift: a pick must be at least this many times more likely than the base
# rate. min_signals: upswings also need this many leading TA signals agreeing.
# Tuned on the holdout year (Nov 25 - Nov 26) for roughly one pick a day:
#   daily up   2+ signals: 42% hit vs 22% base, +0.43% avg (no TA filter: 39%, +0.36%)
#   weekly up  1+ signal:  34% hit vs 15% base, +0.65% avg (2+ halved picks, no gain)
#   daily dip  filled 29%; +0.99% from buy zone at day 14, 82% in profit (any-stock dip: +0.22%, 58%)
#   weekly dip filled 23%; +0.88% from buy zone at day 30, 73% in profit (any-stock dip: +0.47%, 63%)
DIRECTIONS = {
	"up":  {"label": "Upswing",     "icon": "📈", "min_lift": {"daily": 1.5,  "weekly": 2.0}, "min_signals": {"daily": 2, "weekly": 1}},
	"dip": {"label": "Buy the Dip", "icon": "📉", "min_lift": {"daily": 1.75, "weekly": 2.25}},
}

# Leading signals counted towards an upswing's TA support. Each was checked on
# its own against the holdout year and beats the base rate; candle patterns and
# plain MACD crossovers didn't, so they are shown as context but not counted.
BULL_SIGNALS = {
	"b_rsi_turn":    "RSI turning up from oversold",
	"b_stoch_cross": "stochastic bullish cross",
	"b_macd_turn":   "MACD momentum turning up",
	"b_lower_band":  "at the lower Bollinger band",
	"b_divergence":  "bullish RSI divergence",
}
# Short-term weakness signs shown on dip picks (the mirror of the above)
BEAR_SIGNALS = {
	"s_rsi_turn":    "RSI rolling over from overbought",
	"s_stoch_cross": "stochastic bearish cross",
	"s_macd_turn":   "MACD momentum fading",
	"s_upper_band":  "at the upper Bollinger band",
	"s_divergence":  "bearish RSI divergence",
}


def describe(horizon, direction):
	"""One-line target description for a horizon and kind of pick."""
	hz = HORIZONS[horizon]
	pct = "{:.1f}".format(hz["threshold"] * 100) + "%"
	if direction == "up":
		return "close +" + pct + " after " + str(hz["days"]) + " days"
	return "dip " + pct + " within " + str(hz["days"]) + " days, then close +" + pct + " above today by day " + str(hz["recover_days"])


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
	rsi = talib.RSI(c, 14)
	f["rsi14"] = rsi
	k, d = talib.STOCH(h, l, c, 14, 3, 0, 3, 0)
	f["stoch_k"] = k
	f["stoch_d"] = d
	_, _, hist = talib.MACD(c)
	f["macd_hist"] = hist / c
	upper, mid, lower = talib.BBANDS(c, 20)
	bb_pos = (c - lower) / (upper - lower)
	f["bb_pos"] = bb_pos
	f["bb_width"] = (upper - lower) / mid
	f["atr"] = talib.ATR(h, l, c, 14) / c
	f["vol20"] = c.pct_change().rolling(20).std()
	f["range1"] = (h - l) / c
	f["dd20"] = c / h.rolling(20).max() - 1
	f["du20"] = c / l.rolling(20).min() - 1
	f["dow"] = df.index.dayofweek

	# Leading TA signals (flags, not model inputs). "Within the last two days"
	# for crosses so a signal from yesterday's close still counts this morning.
	def crossed(a, b):
		return (a > b) & (a.shift(1) <= b.shift(1))
	f["b_rsi_turn"] = ((rsi < 40) & (rsi > rsi.shift(1))).astype(int)
	f["b_stoch_cross"] = ((crossed(k, d) & (d < 30)) | (crossed(k, d).shift(1, fill_value=False) & (d.shift(1) < 30))).astype(int)
	f["b_macd_turn"] = ((hist < 0) & (hist > hist.shift(1)) & (hist.shift(1) > hist.shift(2))).astype(int)
	f["b_lower_band"] = (bb_pos < 0.2).astype(int)
	f["b_divergence"] = ((c < c.rolling(10).min().shift(1) * 1.002) & (rsi > rsi.rolling(10).min().shift(1))).astype(int)
	f["s_rsi_turn"] = ((rsi > 60) & (rsi < rsi.shift(1))).astype(int)
	f["s_stoch_cross"] = ((crossed(d, k) & (d > 70)) | (crossed(d, k).shift(1, fill_value=False) & (d.shift(1) > 70))).astype(int)
	f["s_macd_turn"] = ((hist > 0) & (hist < hist.shift(1)) & (hist.shift(1) < hist.shift(2))).astype(int)
	f["s_upper_band"] = (bb_pos > 0.8).astype(int)
	f["s_divergence"] = ((c > c.rolling(10).max().shift(1) * 0.998) & (rsi < rsi.rolling(10).max().shift(1))).astype(int)
	f["bull_score"] = f[list(BULL_SIGNALS)].sum(axis=1)
	f["uptrend"] = ((c > c.rolling(100).mean()) & (c.rolling(50).mean() > c.rolling(100).mean())).astype(int)

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


def build_labels(df, days, recover_days):
	"""
	Forward close return over `days`, the best high / worst low within that
	window, and the close return at `recover_days`. Shifts happen on a gap-free
	calendar, so a missing day yields NaN instead of silently comparing against
	a close from weeks later.
	"""
	cal = df[["close", "high", "low"]].asfreq("D")
	fwd_close = cal["close"].shift(-days) / cal["close"] - 1
	# min_periods=days: any missing day inside the window voids the label
	fwd_high = cal["high"][::-1].rolling(days, min_periods=days).max()[::-1].shift(-1) / cal["close"] - 1
	fwd_low = cal["low"][::-1].rolling(days, min_periods=days).min()[::-1].shift(-1) / cal["close"] - 1
	fwd_recover = cal["close"].shift(-recover_days) / cal["close"] - 1
	return tuple(s.reindex(df.index) for s in (fwd_close, fwd_high, fwd_low, fwd_recover))


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
			fwd_close, fwd_high, fwd_low, fwd_recover = build_labels(df, hz["days"], hz["recover_days"])
			f["y_" + name] = fwd_close
			f["yh_" + name] = fwd_high
			f["yl_" + name] = fwd_low
			f["yr_" + name] = fwd_recover
		frames.append(f)
	if not frames:
		raise RuntimeError("No stock history available to build the suggestion dataset.")
	data = pd.concat(frames)
	return data.dropna(subset=["sma100", "ret60"])


def _label_cols(horizon, direction):
	"""Columns that must be known before a row can be used for training."""
	if direction == "up":
		return ["y_" + horizon]
	return ["yl_" + horizon, "yr_" + horizon]


def _hits(frame, horizon, direction):
	thr = HORIZONS[horizon]["threshold"]
	if direction == "up":
		return (frame["y_" + horizon] >= thr).astype(int)
	return ((frame["yl_" + horizon] <= -thr) & (frame["yr_" + horizon] >= thr)).astype(int)


def _qualifies(frame, horizon, direction, base_rate, min_lift):
	"""The bot's picking rule, applied to rows that already have a probability `p`."""
	ok = frame["p"] >= base_rate * min_lift
	if direction == "up":
		ok &= frame["bull_score"] >= DIRECTIONS["up"]["min_signals"][horizon]
	return ok


def _dip_entry_returns(frame, horizon):
	"""Return at the recovery day for rows whose dip filled, measured from the buy zone."""
	thr = HORIZONS[horizon]["threshold"]
	filled = frame[frame["yl_" + horizon] <= -thr]
	return filled, (1 + filled["yr_" + horizon]) / (1 - thr) - 1


def evaluate_holdout(data, horizon, direction, min_lift=None):
	"""
	Train on everything before the final HOLDOUT_DAYS, then apply the bot's
	exact picking rule to the unseen final stretch. Returns summary statistics.
	"""
	hz = HORIZONS[horizon]
	if min_lift is None:
		min_lift = DIRECTIONS[direction]["min_lift"][horizon]
	labelled = data.dropna(subset=_label_cols(horizon, direction))
	cutoff = labelled.index.max() - pd.Timedelta(days=HOLDOUT_DAYS)
	# Purge the label window so training labels can't peek into the test period
	purge = (hz["days"] if direction == "up" else hz["recover_days"]) + 1
	train = labelled[labelled.index < cutoff - pd.Timedelta(days=purge)]
	test = labelled[labelled.index >= cutoff]
	if len(train) == 0 or len(test) == 0:
		return None

	model = XGBClassifier(**_MODEL_PARAMS)
	model.fit(train[FEATURES], _hits(train, horizon, direction))
	test = test.assign(p=model.predict_proba(test[FEATURES])[:, 1], hit=_hits(test, horizon, direction))
	base_rate = float(test["hit"].mean())
	picks = test[_qualifies(test, horizon, direction, base_rate, min_lift)]
	n_days = test.index.nunique()

	stats = {
		"from": test.index.min().strftime("%d/%m/%y"),
		"to": test.index.max().strftime("%d/%m/%y"),
		"base_rate": base_rate,
		"picks_per_day": len(picks) / n_days if n_days else 0.0,
		"n_picks": len(picks),
		"precision": float(picks["hit"].mean()) if len(picks) else float("nan"),
	}
	if direction == "up":
		y_col = "y_" + horizon
		stats.update({
			"avg_return": float(picks[y_col].mean()) if len(picks) else float("nan"),
			"base_avg_return": float(test[y_col].mean()),
			"closed_higher": float((picks[y_col] > 0).mean()) if len(picks) else float("nan"),
		})
	else:
		filled, rets = _dip_entry_returns(picks, horizon)
		all_filled, all_rets = _dip_entry_returns(test, horizon)
		stats.update({
			"fill_rate": len(filled) / len(picks) if len(picks) else float("nan"),
			"dip_return": float(rets.mean()) if len(rets) else float("nan"),
			"dip_win_rate": float((rets > 0).mean()) if len(rets) else float("nan"),
			"base_dip_return": float(all_rets.mean()) if len(all_rets) else float("nan"),
			"base_dip_win_rate": float((all_rets > 0).mean()) if len(all_rets) else float("nan"),
		})
	return stats


class _ModelCache:
	"""Trains each horizon/kind model at most once per completed day."""
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

			for horizon in HORIZONS:
				for direction in DIRECTIONS:
					key = (horizon, direction)
					if key in self._models:
						continue
					labelled = self._data.dropna(subset=_label_cols(horizon, direction))
					model = XGBClassifier(**_MODEL_PARAMS)
					model.fit(labelled[FEATURES], _hits(labelled, horizon, direction))
					self._models[key] = model
					self._stats[key] = evaluate_holdout(self._data, horizon, direction)
			return self._data, self._models, self._stats

	def invalidate(self):
		with self._lock:
			self._day = None


_cache = _ModelCache()


def _recent_patterns(ticker, bullish):
	"""Named candle patterns on the last three completed daily candles (context only)."""
	try:
		df = load_daily(ticker).iloc[-60:]
	except Exception:
		return []
	o, h, l, c = df["open"], df["high"], df["low"], df["close"]
	names = []
	for func, name in (BULLISH_PATTERNS if bullish else BEARISH_PATTERNS):
		vals = func(o, h, l, c)
		if (vals.iloc[-3:] != 0).any():
			names.append(name)
	return names


def _evidence(row, ticker, direction):
	"""(signals counted, context notes) explaining a pick in plain words."""
	if direction == "up":
		signals = [label for col, label in BULL_SIGNALS.items() if row[col] == 1]
		if row["b_rsi_turn"] == 1:
			signals[0] = "RSI turning up from " + "{:.0f}".format(row["rsi14"])
		context = []
		if row["uptrend"] == 1:
			context.append("long-term uptrend")
		if row["dd20"] < -0.03:
			context.append("{:.1f}".format(row["dd20"] * 100) + "% below 20d high")
		context += _recent_patterns(ticker, True)[:2]
	else:
		signals = [label for col, label in BEAR_SIGNALS.items() if row[col] == 1]
		signals += _recent_patterns(ticker, False)[:2]
		# The dip model leans on volatility and short-term position more than on
		# classic bearish triggers, so always show those numbers
		rsi7 = row["rsi7"]
		mood = " (oversold)" if rsi7 < 30 else (" (overbought)" if rsi7 > 70 else "")
		context = [
			"{:.1f}".format(abs(row["sma20"]) * 100) + "% " + ("below" if row["sma20"] < 0 else "above") + " its 20-day average",
			"short-term RSI " + "{:.0f}".format(rsi7) + mood,
			"long-term uptrend intact" if row["uptrend"] == 1 else ("above its 100-day average" if row["sma100"] > 0 else "below its 100-day average"),
			"typically moves ±" + "{:.2f}".format(row["atr"] * 100) + "% a day",
		]
	return signals, context


def scan(horizon, direction, tickers, top_n=3, min_lift=None):
	"""
	Rank every stock by its chance of the horizon's move from the latest
	completed daily close. Returns the picks (passing the bot's rule), the full
	ranking, the base rate for context and the model's holdout statistics.
	"""
	if horizon not in HORIZONS:
		raise ValueError("Unknown horizon: " + repr(horizon))
	if direction not in DIRECTIONS:
		raise ValueError("Unknown direction: " + repr(direction))
	hz = HORIZONS[horizon]
	thr = hz["threshold"]
	if min_lift is None:
		min_lift = DIRECTIONS[direction]["min_lift"][horizon]
	data, models, stats = _cache.get(tickers)

	latest_day = data.index.max()
	# Features for yesterday's close need an unbroken run of recent history; if the
	# gap fill failed the newest usable row could be months old, so refuse instead
	if int(latest_day.timestamp()) < _today_start() - 86400:
		_cache.invalidate()
		raise StaleDataError("Latest usable daily candle is " + latest_day.strftime("%d/%m/%y") + "; daily history needs repairing before suggestions can run.")
	latest = data[data.index == latest_day].dropna(subset=FEATURES).copy()
	latest["p"] = models[(horizon, direction)].predict_proba(latest[FEATURES])[:, 1]
	latest = latest.sort_values("p", ascending=False)

	dir_stats = stats.get((horizon, direction))
	if dir_stats:
		base_rate = dir_stats["base_rate"]
	else:
		base_rate = float(_hits(data.dropna(subset=_label_cols(horizon, direction)), horizon, direction).mean())
	latest["qualifies"] = _qualifies(latest, horizon, direction, base_rate, min_lift)

	as_of = int(latest_day.timestamp())
	ranking = []
	for _, row in latest.iterrows():
		close = float(row["close"])
		entry = {
			"ticker": row["ticker"],
			"probability": float(row["p"]),
			"lift": float(row["p"]) / base_rate if base_rate > 0 else 0.0,
			"qualifies": bool(row["qualifies"]),
			"close": close,
			"atr_pct": float(row["atr"]) * 100,
			"bull_score": int(row["bull_score"]),
			"_row": row,
		}
		if direction == "up":
			entry["target"] = close * (1 + thr)
		else:
			entry["buy_zone"] = close * (1 - thr)
			entry["target"] = close * (1 + thr)
		ranking.append(entry)

	min_signals = DIRECTIONS[direction].get("min_signals", {}).get(horizon, 0)
	picks = [r for r in ranking if r["qualifies"]][:top_n]
	# Near misses, so quiet days still show what is closest and why it fell short
	watchlist = [r for r in ranking if not r["qualifies"]][:2]
	for r in watchlist:
		short = []
		if r["lift"] < min_lift:
			short.append("chance is " + "{:.2f}".format(math.floor(r["lift"] * 100) / 100) + "× a random stock's, needs " + "{:.2f}".format(min_lift) + "×")
		if direction == "up" and r["bull_score"] < min_signals:
			short.append("only " + str(r["bull_score"]) + " of the " + str(min_signals) + " required chart signals")
		r["shortfall"] = short
	shown = {id(r) for r in picks + watchlist}
	# Pattern lookups re-read the DB, so only explain the stocks actually shown
	for r in ranking:
		row = r.pop("_row")
		if id(r) in shown:
			r["signals"], r["context"] = _evidence(row, r["ticker"], direction)

	return {
		"horizon": horizon,
		"direction": direction,
		"as_of": as_of,
		# Upswings resolve after `days`; dips run until the recovery day
		"expires": as_of + 86400 * ((hz["days"] if direction == "up" else hz["recover_days"]) + 1),
		"dip_deadline": as_of + 86400 * (hz["days"] + 1),
		"base_rate": base_rate,
		"min_lift": min_lift,
		"min_signals": min_signals,
		# Closing days the targets are measured on (the candle dated that day)
		"target_day": as_of + 86400 * hz["days"],
		"recover_day": as_of + 86400 * hz["recover_days"],
		"picks": picks,
		"watchlist": watchlist,
		"ranking": ranking,
		"stats": dir_stats,
	}


def outcome(ticker, as_of, horizon, direction, entry, target):
	"""
	Grade a past suggestion once its window has fully closed. Returns None
	while still open, else (closed_hit, touched_hit, final_return, best_return).

	up:  closed_hit = closed at/above target after `days`; touched_hit = high
	     reached it; returns are from the entry close.
	dip: `target` is the buy zone. touched_hit = the dip filled within `days`;
	     closed_hit = filled and closed at/above entry*(1+threshold) on the
	     recovery day; returns are from the buy zone (or from the entry close
	     when it never dipped, to show what waiting cost).
	"""
	if direction not in DIRECTIONS:
		return None
	hz = HORIZONS[horizon]
	start = as_of + 86400
	end = as_of + 86400 * (hz["days"] if direction == "up" else hz["recover_days"])
	if _today_start() <= end:
		return None
	df = get_stock_df(ticker, "d1")
	window = df[(df["date"] >= start) & (df["date"] <= end)]
	if len(window) == 0:
		return None
	final = float(window["close"].iloc[-1])

	if direction == "up":
		best = float(window["high"].max())
		return (final >= target, best >= target, final / entry - 1, best / entry - 1)

	dip_window = window[window["date"] <= as_of + 86400 * hz["days"]]
	filled = len(dip_window) > 0 and float(dip_window["low"].min()) <= target
	if not filled:
		return (False, False, final / entry - 1, float(window["high"].max()) / entry - 1)
	fill_day = int(dip_window[dip_window["low"] <= target]["date"].iloc[0])
	after = window[window["date"] >= fill_day]
	recovered = final >= entry * (1 + hz["threshold"])
	return (recovered, True, final / target - 1, float(after["high"].max()) / target - 1)
