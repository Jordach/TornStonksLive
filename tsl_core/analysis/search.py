import pandas as pd
import talib

from tsl_core.analysis.stochastic import get_stoch_osc
from tsl_core.db import get_stock_from_db

def append_str(p):
	if p == 0:
		return "two candles ago."
	elif p == 1:
		return "previous candle."
	else:
		return "current candle."

def bull_bear(value, pos, name, bull):
	bullish = "📈"
	bearish = "📉"
	
	name_str = "\n"
	if bull:
		if value > 100: # Confirmation
			name_str += bullish + " " + name + " confirmed at "
			return name_str + append_str(pos)
		elif value > 0:
			name_str += bullish + " " + name + " at "
			return name_str + append_str(pos)
		else:
			return ""
	else:
		if value < -100: # Confirmation
			name_str += bearish + " " + name + " confirmed at "
			return name_str + append_str(pos)
		elif value < 0:
			name_str += bearish + " " + name + " at "
			return name_str + append_str(pos)
		else:
			return ""

def pattern_scan(ticker, interval, mode, json_data, all_mode=False):
	if interval not in ["h1", "h2", "h4", "h6", "h12", "d1"]:
		return False

	dt = get_stock_from_db(ticker, interval, limit=60)
	df = pd.DataFrame(data=dt)
 
	# Bullish scans
	if mode.lower() in ["all", "bullish"]:
		df["hammer"] = talib.CDLHAMMER(df.Open, df.High, df.Low, df.Close)
		df["ihammer"] = talib.CDLINVERTEDHAMMER(df.Open, df.High, df.Low, df.Close)
		df["engulfing"] = talib.CDLENGULFING(df.Open, df.High, df.Low, df.Close)
		df["piercing"] = talib.CDLPIERCING(df.Open, df.High, df.Low, df.Close)
		df["morning"] = talib.CDLMORNINGSTAR(df.Open, df.High, df.Low, df.Close)
		df["soldier"] = talib.CDL3WHITESOLDIERS(df.Open, df.High, df.Low, df.Close)
		df["onneck"] = talib.CDLONNECK(df.Open, df.High, df.Low, df.Close)

	# Bearish scans
	if mode.lower() in ["all", "bearish"]:
		df["hanging"] = talib.CDLHANGINGMAN(df.Open, df.High, df.Low, df.Close)
		df["shooting"] = talib.CDLSHOOTINGSTAR(df.Open, df.High, df.Low, df.Close)
		df["evening"] = talib.CDLEVENINGSTAR(df.Open, df.High, df.Low, df.Close)
		df["crows"] = talib.CDL3BLACKCROWS(df.Open, df.High, df.Low, df.Close)
		df["cloud"] = talib.CDLDARKCLOUDCOVER(df.Open, df.High, df.Low, df.Close)

	# Contains both bearish and bullish signals
	if mode.lower() in ["all", "bearish", "bullish"]:
		df["inside"] = talib.CDL3INSIDE(df.Open, df.High, df.Low, df.Close)
		df["outside"] = talib.CDL3OUTSIDE(df.Open, df.High, df.Low, df.Close)
		df["harami"] = talib.CDLHARAMI(df.Open, df.High, df.Low, df.Close)
		df["marubozu"] = talib.CDLMARUBOZU(df.Open, df.High, df.Low, df.Close)
		df["counter"] = talib.CDLCOUNTERATTACK(df.Open, df.High, df.Low, df.Close)

	status_string = ""
	stock_name = ""
	if all_mode:
		for stock in json_data["data"]:
			if stock["stock"] == ticker.upper():
				status_string = "__" + stock["name"] + "__"
				stock_name = "__" + stock["name"] + "__"
				break

	start = len(df.Close)-3
	end = len(df.Close)
	for i in range(start, end):
		pos = i-end+3
		if mode.lower() in ["all", "bullish"]:
			status_string += bull_bear(df.hammer[i], pos, "Hammer", True)
			status_string += bull_bear(df.ihammer[i], pos, "Inverted Hammer", True)
			status_string += bull_bear(df.engulfing[i], pos, "Engulfing Hammer", True)
			status_string += bull_bear(df.piercing[i], pos, "Piercing", True)
			status_string += bull_bear(df.morning[i], pos, "Morningstar", True)
			status_string += bull_bear(df.soldier[i], pos, "Three White Soldiers", True)
			status_string += bull_bear(df.onneck[i], pos, "On-Neck", True)
			status_string += bull_bear(df.inside[i], pos, "Three Inside Up", True)
			status_string += bull_bear(df.outside[i], pos, "Three Outside Up", True)
			status_string += bull_bear(df.harami[i], pos, "Bullish Harami", True)
			status_string += bull_bear(df.marubozu[i], pos, "White Marubozu", True)
			status_string += bull_bear(df.counter[i], pos, "Bullish Counterattack", True)
		
		if mode.lower() in ["all", "bearish"]:
			status_string += bull_bear(df.hanging[i], pos, "Hanging Man", False)
			status_string += bull_bear(df.shooting[i], pos, "Shooting Star", False)
			status_string += bull_bear(df.evening[i], pos, "Eveningstar", False)
			status_string += bull_bear(df.crows[i], pos, "Three Black Crows", False)
			status_string += bull_bear(df.cloud[i], pos, "Dark Cloud Cover", False)
			status_string += bull_bear(df.inside[i], pos, "Three Inside Down", False)
			status_string += bull_bear(df.outside[i], pos, "Three Outside Down", False)
			status_string += bull_bear(df.harami[i], pos, "Bearish Harami", False)
			status_string += bull_bear(df.marubozu[i], pos, "Black Marubozu", False)
			status_string += bull_bear(df.counter[i], pos, "Bearish Counterattack", False)

	if mode.lower() in ["all", "osc"]:
		oversol = "\n📈"
		overbuy = "\n📉"

		rsi = talib.RSI(df.Close, timeperiod=14)
		stoch = get_stoch_osc(df, 14, 3)

		r_pos = len(rsi)-1
		rsi_str = " RSI: " + "{:.2f}".format(rsi[r_pos]) + ", "
		if rsi[r_pos] < 30:
			status_string += oversol + rsi_str + "Oversold Position."
		elif rsi[r_pos] > 70:
			status_string += overbuy + rsi_str + "Overbought Position."

		k_pos = len(stoch["k"])-1
		d_pos = len(stoch["d"])-1
		sto_str = " STOCH: %K " + "{:.2f}".format(stoch["k"][k_pos]) + ", %D " + "{:.2f}".format(stoch["d"][d_pos]) + ", "
		
		if stoch["k"][k_pos] < 20 and stoch["d"][d_pos] < 20:
			if stoch["k"][k_pos] < stoch["d"][d_pos]:
				status_string += oversol + sto_str + "Oversold Position."
		elif stoch["k"][k_pos] > 80 and stoch["d"][d_pos] > 80:
			if stoch["k"][k_pos] > stoch["d"][d_pos]:
				status_string += overbuy + sto_str + "Overbought Position."

	# Prevent displaying of not found entries where the string hasn't been edited at all
	if status_string not in ["", stock_name]:
		if all_mode:	
			return status_string + "\n\n"
		else:
			return status_string
	else:
		return False