import datetime
import os
from matplotlib import pyplot as plt
from matplotlib.lines import Line2D
import ta
import pandas as pd
from tsl_core.db import get_stock_from_db


def get_ulcer(ticker, interval, render_graphs=True, limit=2000, window=14):
	dt = get_stock_from_db(ticker, interval, limit=limit+window)
	df = pd.DataFrame(data=dt)
	dt_orig = get_stock_from_db(ticker, interval, limit=limit)

	ulcer = ta.volatility.UlcerIndex(close=df["Close"], window=window)
	# All of this to strip out the NaNs and normalise data, Python pls
	ulcer_data = ulcer.ulcer_index()
	ulcer_data = ulcer_data.dropna()
	ulist = ulcer_data.values.tolist()

	# Figure out timestamps
	len_div = int(len(dt_orig["date"])/6)
	period_ticks = []
	period_ticks.append(dt_orig["date"][0])
	period_ticks.append(dt_orig["date"][(len_div*1)-1-window])
	period_ticks.append(dt_orig["date"][(len_div*2)-1-window])
	period_ticks.append(dt_orig["date"][(len_div*3)-1-window])
	period_ticks.append(dt_orig["date"][(len_div*4)-1-window])
	period_ticks.append(dt_orig["date"][(len_div*5)-1-window])
	period_ticks.append(dt_orig["date"][len(dt_orig["date"])-1-window])

	current_time = datetime.datetime.utcnow().timestamp()
	current_time = datetime.datetime.fromtimestamp(current_time).strftime('%H:%M:%S %d/%m/%y')
	
	# Set PNG file name
	file = os.getcwd()+"/graphs/ulcer "+ticker+" "+interval+" " + str(window) + " "+str(current_time.replace("/", "-").replace(":", "-")+".png")
	
	# Render the PNG graph
	if render_graphs:
		# Make x-axis timestamps not suck
		xticks = []
		xticks.append(0)
		for i in range(1, 7):
			xticks.append(float(len(dt_orig["date"]) / 6) * i)

		plt.style.use("ggplot")
		fig, ax = plt.subplots(nrows=2, ncols=1, sharex=True, figsize=(6,6))
		ax[0].plot(dt_orig["Close"], color="skyblue", linewidth=0.75, label="Price")
		plt.title("Ulcer Index " + ticker.upper() + " (" + interval + ")")
		ax[0].yaxis.set_major_formatter('${x:1.2f}')
		ax[1].plot(ulist, color="tab:orange", linewidth=0.75)
		custom_lines = [
			Line2D([0], [0], color="tab:orange", lw=2),
		]
		ax[1].legend(custom_lines, ["Ulcer Index"], loc="best")
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
	return [file, period_ticks]