import pandas as pd
import talib

from tsl_core.analysis.stochastic import get_stoch_osc
from tsl_core.db import get_stock_from_db

#  Candlestick Pattern Definitions
#  Each entry: (talib_func, display_name, direction)
#  direction: "bullish", "bearish", or "both"
#  "both" patterns emit positive values for bull
#  and negative values for bear signals.

BULLISH_PATTERNS = [
	(talib.CDLHAMMER,           "Hammer"),
	(talib.CDLINVERTEDHAMMER,   "Inverted Hammer"),
	(talib.CDLPIERCING,         "Piercing"),
	(talib.CDLMORNINGSTAR,      "Morningstar"),
	(talib.CDL3WHITESOLDIERS,   "Three White Soldiers"),
	(talib.CDLONNECK,           "On-Neck"),
	(talib.CDLMORNINGDOJISTAR,  "Morning Doji Star"),
	(talib.CDLBREAKAWAY,        "Breakaway"),
	(talib.CDLMATHOLD,          "Mat Hold"),
	(talib.CDLHOMINGPIGEON,     "Homing Pigeon"),
	(talib.CDLUNIQUE3RIVER,     "Unique Three River"),
	(talib.CDLKICKING,          "Kicking"),
	(talib.CDLLADDERBOTTOM,     "Ladder Bottom"),
	(talib.CDLABANDONEDBABY,    "Abandoned Baby"),
	(talib.CDLTRISTAR,          "Tri-Star"),
	(talib.CDLSTICKSANDWICH,    "Stick Sandwich"),
]

BEARISH_PATTERNS = [
	(talib.CDLHANGINGMAN,       "Hanging Man"),
	(talib.CDLSHOOTINGSTAR,     "Shooting Star"),
	(talib.CDLEVENINGSTAR,      "Eveningstar"),
	(talib.CDL3BLACKCROWS,      "Three Black Crows"),
	(talib.CDLDARKCLOUDCOVER,   "Dark Cloud Cover"),
	(talib.CDLEVENINGDOJISTAR,  "Evening Doji Star"),
	(talib.CDLADVANCEBLOCK,     "Advance Block"),
	(talib.CDL2CROWS,           "Two Crows"),
	(talib.CDL3STARSINSOUTH,    "Three Stars in South"),
	(talib.CDLIDENTICAL3CROWS,  "Identical Three Crows"),
]

# These patterns fire both bullish (positive) and bearish (negative) signals
BOTH_PATTERNS = [
	(talib.CDL3INSIDE,          "Three Inside",       "Three Inside Up",      "Three Inside Down"),
	(talib.CDL3OUTSIDE,         "Three Outside",      "Three Outside Up",     "Three Outside Down"),
	(talib.CDLHARAMI,           "Harami",             "Bullish Harami",       "Bearish Harami"),
	(talib.CDLHARAMICROSS,      "Harami Cross",       "Bullish Harami Cross", "Bearish Harami Cross"),
	(talib.CDLMARUBOZU,         "Marubozu",           "White Marubozu",       "Black Marubozu"),
	(talib.CDLCOUNTERATTACK,    "Counterattack",      "Bullish Counterattack","Bearish Counterattack"),
	(talib.CDLENGULFING,        "Engulfing",          "Bullish Engulfing",    "Bearish Engulfing"),
	(talib.CDLDOJI,             "Doji",               "Bullish Doji",         "Bearish Doji"),
	(talib.CDLSPINNINGTOP,      "Spinning Top",       "Bullish Spinning Top", "Bearish Spinning Top"),
	(talib.CDLBELTHOLD,         "Belt Hold",          "Bullish Belt Hold",    "Bearish Belt Hold"),
	(talib.CDLTASUKIGAP,        "Tasuki Gap",         "Upside Tasuki Gap",    "Downside Tasuki Gap"),
	(talib.CDLSEPARATINGLINES,  "Separating Lines",   "Bull Separating Lines","Bear Separating Lines"),
]

# Valid intervals for pattern scanning
SCAN_INTERVALS = ["h1", "h2", "h4", "h6", "h12", "d1"]


def _append_str(p):
	if p == 0:
		return "two candles ago."
	elif p == 1:
		return "previous candle."
	else:
		return "current candle."


def _format_signal(value, pos, name, bull):
	"""Format a single pattern signal into a display string."""
	if bull:
		if value > 100:
			return "\n📈 " + name + " confirmed at " + _append_str(pos)
		elif value > 0:
			return "\n📈 " + name + " at " + _append_str(pos)
	else:
		if value < -100:
			return "\n📉 " + name + " confirmed at " + _append_str(pos)
		elif value < 0:
			return "\n📉 " + name + " at " + _append_str(pos)
	return ""


def pattern_scan(ticker, interval, mode, json_data, all_mode=False):
	"""
	Scan a stock for candlestick patterns and oscillator conditions.

	Parameters
	----------
	ticker : str
		Stock ticker (lowercase).
	interval : str
		Candle interval (h1, h2, h4, h6, h12, d1).
	mode : str
		"bullish", "bearish", "osc", or "all".
	json_data : dict
		Live stock data from Tornsy feed.
	all_mode : bool
		When True, prefixes results with the stock name and returns
		None instead of False when no patterns are found.

	Returns
	-------
	str or False
		Formatted result string, or False/None if nothing found.
	"""
	if interval not in SCAN_INTERVALS:
		return False

	try:
		dt = get_stock_from_db(ticker, interval, limit=60)
		df = pd.DataFrame(data=dt)
		if len(df) < 3:
			return False
	except Exception:
		return False

	mode_l = mode.lower()
	scan_bull = mode_l in ["all", "bullish"]
	scan_bear = mode_l in ["all", "bearish"]
	scan_osc  = mode_l in ["all", "osc"]

	# Compute pattern columns
	o, h, l, c = df.Open, df.High, df.Low, df.Close
	pattern_cols = {}  # col_name -> (display_name, is_bullish)

	if scan_bull:
		for func, name in BULLISH_PATTERNS:
			col = "bull_" + name.lower().replace(" ", "_")
			df[col] = func(o, h, l, c)
			pattern_cols[col] = (name, True)

	if scan_bear:
		for func, name in BEARISH_PATTERNS:
			col = "bear_" + name.lower().replace(" ", "_")
			df[col] = func(o, h, l, c)
			pattern_cols[col] = (name, False)

	if scan_bull or scan_bear:
		for entry in BOTH_PATTERNS:
			func, base_name, bull_name, bear_name = entry
			col = "both_" + base_name.lower().replace(" ", "_")
			df[col] = func(o, h, l, c)
			if scan_bull:
				pattern_cols[col + "_bull"] = (bull_name, True)
			if scan_bear:
				pattern_cols[col + "_bear"] = (bear_name, False)

	# Build status string
	status_string = ""
	stock_name = ""
	if all_mode:
		for stock in json_data["data"]:
			if stock["stock"] == ticker.upper():
				status_string = "__" + stock["name"] + "__"
				stock_name = status_string
				break

	# Scan the last 3 candles
	start = len(df.Close) - 3
	end = len(df.Close)
	for i in range(start, end):
		pos = i - end + 3

		for col, (display_name, is_bull) in pattern_cols.items():
			# "both" patterns share a single column; the _bull/_bear
			# suffix is only in our key — strip it to get the real column
			real_col = col
			if col.endswith("_bull") or col.endswith("_bear"):
				real_col = col.rsplit("_", 1)[0]
			status_string += _format_signal(df[real_col].iloc[i], pos, display_name, is_bull)

	# Oscillator section
	if scan_osc:
		oversol = "\n📈"
		overbuy = "\n📉"

		# RSI
		rsi = talib.RSI(c, timeperiod=14)
		r_val = rsi.iloc[-1]
		rsi_str = " RSI: " + "{:.2f}".format(r_val) + ", "
		if r_val < 30:
			status_string += oversol + rsi_str + "Bullish/Oversold Position."
		elif r_val > 70:
			status_string += overbuy + rsi_str + "Bearish/Overbought Position."

		# Stochastic
		stoch = get_stoch_osc(df, 14, 3)
		k_val = stoch["k"].iloc[-1]
		d_val = stoch["d"].iloc[-1]
		sto_str = " STOCH: %K " + "{:.2f}".format(k_val) + ", %D " + "{:.2f}".format(d_val) + ", "

		if k_val < 20 and d_val < 20:
			if k_val < d_val:
				status_string += oversol + sto_str + "Bullish/Oversold Position."
		elif k_val > 80 and d_val > 80:
			if k_val > d_val:
				status_string += overbuy + sto_str + "Bearish/Overbought Position."

		# MACD crossover
		ema_12 = c.ewm(span=12, adjust=False).mean()
		ema_26 = c.ewm(span=26, adjust=False).mean()
		macd_line = ema_12 - ema_26
		signal_line = macd_line.ewm(span=9, adjust=False).mean()

		# Check for a fresh crossover in the last 2 candles
		if len(macd_line) >= 2:
			prev_diff = macd_line.iloc[-2] - signal_line.iloc[-2]
			curr_diff = macd_line.iloc[-1] - signal_line.iloc[-1]
			macd_val = "{:.4f}".format(macd_line.iloc[-1])
			sig_val = "{:.4f}".format(signal_line.iloc[-1])
			if prev_diff <= 0 and curr_diff > 0:
				status_string += oversol + " MACD Bullish Crossover (MACD: " + macd_val + ", Signal: " + sig_val + ")."
			elif prev_diff >= 0 and curr_diff < 0:
				status_string += overbuy + " MACD Bearish Crossover (MACD: " + macd_val + ", Signal: " + sig_val + ")."

	# Return
	if status_string not in ["", stock_name]:
		if all_mode:
			return status_string + "\n\n"
		else:
			return status_string
	else:
		if all_mode:
			return None
		return False