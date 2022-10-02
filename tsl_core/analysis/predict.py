import os
import datetime
from matplotlib import pyplot as plt
import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression
from sklearn.model_selection import train_test_split
from sklearn.svm import SVR, LinearSVR
from tsl_core.db import get_stock_from_db

# Helpers
def remap(val, val_min, val_max, map_min, map_max):
	return (val-val_min) / (val_max-val_min) * (map_max-map_min) + map_min

def clamp_(val, min, max):
	if val <= min:
		return min
	elif val >= max:
		return max
	else:
		return val

def predict_stock(ticker, interval, forecast, render_graphs, json_data, samples=2000):
	nsamples = clamp_(samples, 300, 16000)
	dt = get_stock_from_db(ticker, interval, limit=int(nsamples))

	df = pd.DataFrame(data=dt)
	# Magic bullshit - we do not question the pandas module
	df = df[["Close"]]
	df["prediction"] = df[["Close"]].shift(-(forecast+1))

	x = np.array(df.drop(["prediction"], axis=1))
	x = x[:-(forecast+1)]
	
	y = np.array(df["prediction"])
	y = y[:-(forecast+1)]
	
	test_size = 0.2
	test_size = remap(len(dt["Close"]), 1000, 16000, 0.4, 0.025)
	test_size = clamp_(test_size, 0.025, 0.2)

	x_train, x_test, y_train, y_test = train_test_split(x, y, test_size=test_size)

	# Train and setup prediction engines
	svr_rbf = SVR(kernel='rbf', C=250, gamma=0.1) 
	svr_rbf.fit(x_train, y_train)
	svm_confidence = svr_rbf.score(x_test, y_test)

	lr = LinearRegression()
	lr.fit(x_train, y_train)
	lr_confidence = lr.score(x_test, y_test)

	svr_l = LinearSVR(max_iter=12000, loss="squared_epsilon_insensitive", C=4.2, dual=False)
	svr_l.fit(x_train, y_train)
	svr_l_confidence = svr_l.score(x_test, y_test)

	x_forecast = np.array(df.drop(["prediction"], axis=1))[-(forecast+1):]
	svm_prediction = svr_rbf.predict(x_forecast)
	lr_prediction = lr.predict(x_forecast)
	svm_l_prediction = svr_l.predict(x_forecast)
	avg_confidence = (svm_confidence + lr_confidence + svr_l_confidence) / 3
	
	price = 0
	name = ""
	for stock in json_data["data"]:
		if stock["stock"] == ticker.upper():
			price = float(stock["price"])
			name = stock["name"]
			break

	# Pull prices downwards to fix mysterious invalid prices
	diff_svm = svm_prediction[0] - price
	diff_lr = lr_prediction[0] - price
	diff_svml = svm_l_prediction[0] - price

	# High, Low, average, confidence
	hlvc = {}
	hlvc["price"] = price
	hlvc["ticker"] = ticker
	hlvc["svm"] = {}
	hlvc["svm"]["high"] = 0
	hlvc["svm"]["low"] = 10000
	hlvc["svm"]["volatility"] = 0
	hlvc["svm"]["actual"] = 0
	hlvc["svm"]["confidence"] = svm_confidence

	hlvc["lr"] = {}
	hlvc["lr"]["high"] = 0
	hlvc["lr"]["low"] = 10000
	hlvc["lr"]["volatility"] = 0
	hlvc["lr"]["actual"] = 0
	hlvc["lr"]["confidence"] = lr_confidence

	hlvc["svml"] = {}
	hlvc["svml"]["high"] = 0
	hlvc["svml"]["low"] = 10000
	hlvc["svml"]["volatility"] = 0
	hlvc["svml"]["actual"] = 0
	hlvc["svml"]["confidence"] = svr_l_confidence

	hlvc["avg"] = {}
	hlvc["avg"]["high"] = 0
	hlvc["avg"]["low"] = 10000
	hlvc["avg"]["volatility"] = 0
	hlvc["avg"]["actual"] = 0
	hlvc["avg"]["confidence"] = avg_confidence

	avg_prediction = []
	# Post process and normalise values
	for key in range(0, len(svm_prediction)):
		svm_prediction[key] -= diff_svm
		lr_prediction[key] -= diff_lr
		svm_l_prediction[key] -= diff_svml
		avg = float(svm_prediction[key] + lr_prediction[key] + svm_l_prediction[key]) / 3
		avg_prediction.append(avg)
		dt["sma"].append(avg)

		# Find highs and lows for all predicts, including the average:
		svm = svm_prediction[key]
		if svm > hlvc["svm"]["high"]:
			hlvc["svm"]["high"] = svm
		if svm < hlvc["svm"]["low"]:
			hlvc["svm"]["low"] = svm
		perc = abs(float((price - svm) / svm) * 100)
		aperc = float((price - svm) / svm) * -100
		if perc > hlvc["svm"]["volatility"]:
			hlvc["svm"]["volatility"] = perc
			hlvc["svm"]["actual"] = aperc
		
		lr = lr_prediction[key]
		if lr > hlvc["lr"]["high"]:
			hlvc["lr"]["high"] = lr
		if lr < hlvc["lr"]["low"]:
			hlvc["lr"]["low"] = lr
		perc = abs(float((price - lr) / lr) * 100)
		aperc = float((price - lr) / lr) * -100
		if perc > hlvc["lr"]["volatility"]:
			hlvc["lr"]["volatility"] = perc
			hlvc["lr"]["actual"] = aperc

		svml = svm_l_prediction[key]
		if svml > hlvc["svml"]["high"]:
			hlvc["svml"]["high"] = svml
		if svml < hlvc["svml"]["low"]:
			hlvc["svml"]["low"] = svml
		perc = abs(float((price - svml) / svml) * 100)
		aperc = float((price - svml) / svml) * -100
		if perc > hlvc["svml"]["volatility"]:
			hlvc["svml"]["volatility"] = perc
			hlvc["svml"]["actual"] = aperc

		if avg > hlvc["avg"]["high"]:
			hlvc["avg"]["high"] = avg
		if avg < hlvc["avg"]["low"]:
			hlvc["avg"]["low"] = avg
		perc = abs(float((price - avg) / avg) * 100)
		aperc = float((price - avg) / avg) * -100
		if perc > hlvc["avg"]["volatility"]:
			hlvc["avg"]["volatility"] = perc
			hlvc["avg"]["actual"] = aperc

	# Figure out timestamps
	period = int(int ( ''.join(filter(str.isdigit, interval) ) ))
	period_ticks = []
	current_time = datetime.datetime.utcnow().timestamp()
	period_ticks.append(datetime.datetime.fromtimestamp(current_time).strftime('%H:%M:%S %d/%m/%y'))
	for i in range(2, 10):
		if interval[0] == "m":
			period_ticks.append(datetime.datetime.fromtimestamp(current_time + int(((60 * (period * forecast)) / 9) * i)).strftime('%H:%M:%S %d/%m/%y'))
		elif interval[0] == "h":
			period_ticks.append(datetime.datetime.fromtimestamp(current_time + int(((3600 * (period * forecast)) / 9) * i)).strftime('%H:%M:%S %d/%m/%y'))
		elif interval[0] == "d":
			period_ticks.append(datetime.datetime.fromtimestamp(current_time + int(((86400 * (period * forecast)) / 9) * i)).strftime('%H:%M:%S %d/%m/%y'))
		elif interval[0] == "w":
			period_ticks.append(datetime.datetime.fromtimestamp(current_time + int(((604800 * (period * forecast)) / 9) * i)).strftime('%H:%M:%S %d/%m/%y'))
		elif interval[0] == "n":
			period_ticks.append(datetime.datetime.fromtimestamp(current_time + int(((26355200 * (period * forecast)) / 9) * i)).strftime('%H:%M:%S %d/%m/%y'))
		elif interval[0] == "y":
			period_ticks.append(datetime.datetime.fromtimestamp(current_time + int(((31536000 * (period * forecast)) / 9) * i)).strftime('%H:%M:%S %d/%m/%y'))
	# Set PNG file name
	file = os.getcwd()+"/graphs/predict "+ticker+" "+interval+" "+str(forecast)+" "+str(period_ticks[0].replace("/", "-").replace(":", "-")+".png")
	
	# Render the PNG graph
	if render_graphs:
		# Create SMA graph line
		sma_avg = []
		sma_amt = 15
		sma_len = (len(dt["sma"])) - (forecast + sma_amt)
		sma_len_b = len(dt["Close"]) + 1
		for f in range(forecast+1):
			sma_val = 0
			for i in range(sma_len+f, sma_len_b+f):
				sma_val += float(dt["sma"][i])
			sma_avg.append(sma_val/(sma_amt))

		# Make x-axis timestamps not suck
		xticks = []
		xticks.append(0)
		for i in range(1, 9):
			xticks.append(float(forecast / 8) * i)

		plt.style.use("ggplot")
		fig, ax = plt.subplots()
		ax.plot(sma_avg, color="#ff8a00", linewidth=2.5, zorder=-10, alpha=0.3)
		ax.plot(svm_prediction, linewidth=12, alpha=0.05, color="red", zorder=-8)
		ax.plot(lr_prediction, linewidth=12, alpha=0.05, color="blue", zorder=-7)
		ax.plot(svm_l_prediction, linewidth=12, alpha=0.05, color="purple", zorder=-6)
		#ax.plot(avg_prediction, linewidth=12, alpha=0.1, color="green", zorder=-5)
		ax.plot(svm_prediction, label="SVM", alpha=0.15, linewidth=1.5, color="red", zorder=-4)
		ax.plot(lr_prediction, label="LR", alpha=0.15, linewidth=1.5, color="blue", zorder=-3)
		ax.plot(svm_l_prediction, label="SVM Linear", alpha=0.15, linewidth=1.5, color="purple", zorder=-2)
		#ax.plot(avg_prediction, label="Average", linewidth=1.5, color="green", zorder=-1)
		ax.plot(sma_avg, label="Trend", alpha=0.9, color="#ff8a00", linewidth=1.5, linestyle="--", zorder=-9, dashes=(5, 2))
		plt.title(name + " Price Prediction (" + interval + ", " + str(forecast) + ")")
		ax.yaxis.set_major_formatter('${x:1.2f}')
		ax.set_xticks(xticks)
		ax.set_xticklabels(period_ticks)
		plt.xticks(rotation=45, horizontalalignment="right")
		plt.legend()
		plt.tight_layout()
		plt.grid(color = 'black', linestyle = '--', linewidth = 0.5)
		if not os.path.isdir(os.getcwd()+"/graphs"):
			os.mkdir(os.getcwd()+"/graphs")

		plt.savefig(file)
		plt.close()
	return [file, hlvc, name, period_ticks]