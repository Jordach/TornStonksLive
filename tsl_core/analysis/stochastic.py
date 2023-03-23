import datetime
import os
import numpy as np
import pandas as pd
from matplotlib import pyplot as plt
from matplotlib.lines import Line2D
from tsl_core.db import get_stock_from_db

def get_stoch_osc(df, k, d):
	copy = df.copy()

	high_roll = copy["High"].rolling(k).max()
	low_roll = copy["Low"].rolling(k).min()
	
	# Fast osc
	num = copy["Close"] - low_roll
	denom = high_roll - low_roll
	copy["k"] = (num / denom) * 100

	# Slow osc
	copy["d"] = copy["k"].rolling(d).mean()
	return copy

def get_stoch(ticker, interval, render_graphs=True, k=14, t=3, limit=2000, profit_perc=0.1):
	dt = get_stock_from_db(ticker, interval, limit=limit)

	df = pd.DataFrame(data=dt)

	stoch = get_stoch_osc(df, k, t)
	buy_price = []
	sell_price = []
	stoch_signal = []
	signal = 0
	sig_price = dt["Close"][0]
	perc_gain = 1
	n_buys = 0
	n_sells = 0

	for i in range(len(stoch["k"])):
		if stoch["k"][i] < 20 and stoch["d"][i] < 20 and stoch["k"][i] < stoch["d"][i]:
			if signal != 1:
				buy_price.append(dt["Close"][i])
				sell_price.append(np.nan)
				signal = 1
				sig_price = dt["Close"][i]
				stoch_signal.append(signal)
				n_buys += 1
			else:
				buy_price.append(np.nan)
				sell_price.append(np.nan)
				stoch_signal.append(0)
		elif stoch["k"][i] > 80 and stoch["d"][i] > 80 and stoch["k"][i] > stoch["d"][i]:
			if profit_perc > 0:
				if (sig_price * (1 + (profit_perc / 100))) < dt["Close"][i]:
					if signal != -1:
						buy_price.append(np.nan)
						sell_price.append(dt["Close"][i])
						signal = -1
						perc = (float((dt["Close"][i] - sig_price) / sig_price) * 100)
						perc_gain = perc_gain * (1 + perc)
						sig_price = dt["Close"][i]
						stoch_signal.append(signal)
						n_sells += 1
					else:
						buy_price.append(np.nan)
						sell_price.append(np.nan)
						stoch_signal.append(0)
				else:
					buy_price.append(np.nan)
					sell_price.append(np.nan)
					stoch_signal.append(0)
			else:
				if signal != -1:
					buy_price.append(np.nan)
					sell_price.append(dt["Close"][i])
					signal = -1
					perc = (float((dt["Close"][i] - sig_price) / sig_price) * 100)
					perc_gain = perc_gain * (1 + perc)
					sig_price = dt["Close"][i]
					stoch_signal.append(signal)
					n_sells += 1
				else:
					buy_price.append(np.nan)
					sell_price.append(np.nan)
					stoch_signal.append(0)
		else:
			buy_price.append(np.nan)
			sell_price.append(np.nan)
			stoch_signal.append(0)

	position = []
	for i in range(len(stoch_signal)):
		if stoch_signal[i] > 1:
			position.append(0)
		else:
			position.append(1)

	for i in range(len(dt["Close"])):
		if stoch_signal[i] == 1:
			position[i] = 1
		elif stoch_signal[i] == -1:
			position[i] = 0
		else:
			position[i] = position[i-1]

	# Figure out timestamps
	len_div = int(len(dt["date"])/6)
	period_ticks = []
	period_ticks.append(dt["date"][0])
	period_ticks.append(dt["date"][(len_div*1)-1])
	period_ticks.append(dt["date"][(len_div*2)-1])
	period_ticks.append(dt["date"][(len_div*3)-1])
	period_ticks.append(dt["date"][(len_div*4)-1])
	period_ticks.append(dt["date"][(len_div*5)-1])
	period_ticks.append(dt["date"][len(dt["date"])-1])

	current_time = datetime.datetime.utcnow().timestamp()
	current_time = datetime.datetime.fromtimestamp(current_time).strftime('%H:%M:%S %d/%m/%y')
	
	# Set PNG file name
	file = os.getcwd()+"/graphs/stoch "+ticker+" "+interval+" " + str(k) + ", " + str(t) + " "+str(current_time.replace("/", "-").replace(":", "-")+".png")
	
	# Render the PNG graph
	if render_graphs:
		# Make x-axis timestamps not suck
		xticks = []
		xticks.append(0)
		for i in range(1, 7):
			xticks.append(float(len(dt["date"]) / 6) * i)

		plt.style.use("ggplot")
		fig, ax = plt.subplots(nrows=2, ncols=1, sharex=True, figsize=(6,6))
		ax[0].plot(dt["Close"], color="skyblue", linewidth=0.75, label="Price")
		ax[0].plot(df.index, buy_price, marker="^", color="green", markersize=3, linewidth=0, label="Buy")
		ax[0].plot(df.index, sell_price, marker="v", color="red", markersize=3, linewidth=0, label="Sell")
		plt.title("STOCH " + ticker.upper() + " (" + interval + ")")
		ax[0].yaxis.set_major_formatter('${x:1.2f}')
		ax[1].set_ylim(-10, 110)
		ax[1].plot(stoch["k"], color="tab:blue", linewidth=0.75)
		ax[1].plot(stoch["d"], color="tab:orange", linewidth=0.75)
		ax[1].axhline(80, color="tab:red", ls="--")
		ax[1].axhline(20, color="tab:green", ls="--")
		custom_lines = [
			Line2D([0], [0], color="tab:blue", lw=2),
			Line2D([0], [0], color="tab:orange", lw=2),
			Line2D([0], [0], color="tab:red", lw=2),
			Line2D([0], [0], color="tab:green", lw=2),
		]
		ax[1].legend(custom_lines, ["%K", "%D", "Overbought", "Oversold"], loc="best")
		ax[0].set_xticks(xticks)
		ax[1].set_xticks(xticks)
		ax[1].set_xticklabels(period_ticks)
		plt.xticks(rotation=45, horizontalalignment="right")
		ax[0].legend()
		plt.tight_layout()
		ax[0].grid(color = 'black', linestyle = '--', linewidth = 0.5)
		plt.grid(color = 'black', linestyle = '--', linewidth = 0.5)
		if not os.path.isdir(os.getcwd()+"/graphs"):
			os.mkdir(os.getcwd()+"/graphs")

		plt.savefig(file)
		plt.close()
	return [file, period_ticks, n_buys, n_sells, perc_gain]