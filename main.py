import requests
import json
import schedule

import tsl_config.config as config
import tsl_core.functions as tsl_lib
import tsl_bot.bot as tsl_bot

config.read_token()
config.read_admins()
config.read_user_alerts()
config.read_alerts()
config.read_channels()
config.read_suggestions()
config.read_suggest_json()

current_day = tsl_lib.util.current_date()

# Back fill the DBs with data
def backfill_db():
	n_times = -1
	for ticker in tsl_lib.stock_lut:
		tsl_lib.util.write_log("[INFO]: Downloading " + ticker + ".", current_day)
		tsl_lib.db.import_from_tornsy(ticker, tsl_lib.intervals, limit=n_times)
		tsl_lib.util.write_log("[INFO]: " + ticker + " added to DB.", current_day)

backfill_db()

tornsy_api_address = "https://tornsy.com/api/stocks?interval=m1,h1,d1,w1,n1"
tornsy_data =""
try:
	tornsy_data = requests.get(tornsy_api_address)
except:
	raise Exception("Tornsy probably timed out - you likely have no network access.")

def get_latest_stocks():
	global current_day
	current_day = tsl_lib.util.current_date()
	global tornsy_data
	try:
		tornsy_data = requests.get(tornsy_api_address)
	except:
		tsl_lib.util.write_log("[WARNING] Tornsy appears to be having issues", current_day)
		return

	if tornsy_data.status_code == 200:
		config.json_data = json.loads(tornsy_data.text)
		tsl_lib.db.update_from_tornsy(config.json_data, tsl_lib.intervals)
		if config.bot_started:
			tsl_bot.Bot.process_stockdata(client)
	else:
		tsl_lib.util.write_log("[WARNING] Server returned error code: " + str(tornsy_data.status_code), current_day)

# Get initial data
get_latest_stocks()

def check_volatility():
	if config.bot_started:
		try:
			tsl_bot.Bot.process_volatility(client)
		except:
			tsl_lib.util.write_log("[WARNING] Potential problem with volatiltity checks.", current_day)

def check_daily_volatility():
	if config.bot_started:
		try:
			tsl_bot.Bot.process_daily_volatility(client)
		except:
			tsl_lib.util.write_log("[WARNING] Potential problem with volatiltity checks.", current_day)

def check_weekly_volatility():
	if config.bot_started:
		try:
			tsl_bot.Bot.process_weekly_volatility(client)
		except:
			tsl_lib.util.write_log("[WARNING] Potential problem with volatiltity checks.", current_day)


def suggests():
	if config.bot_started:
		try:
			tsl_bot.Bot.process_suggestions(client)
		except:
			tsl_lib.util.write_log("[WARNING] Potential problem with suggestion predictions.", current_day)

# Initiate background thread and jobs
enable_suggestions = False
if enable_suggestions:
	schedule.every().day.at("01:01:20").do(suggests)
	schedule.every().day.at("05:01:20").do(suggests)
	schedule.every().day.at("09:01:20").do(suggests)
	schedule.every().day.at("13:01:20").do(suggests)
	schedule.every().day.at("17:01:20").do(suggests)
	schedule.every().day.at("21:01:20").do(suggests)

enable_volatility = False
if enable_volatility:
	schedule.every().hour.at("00:45").do(check_volatility)
	schedule.every().hour.at("30:45").do(check_volatility)
	schedule.every().day.at("01:00:45").do(check_daily_volatility)
	schedule.every().monday.at("01:00:45").do(check_weekly_volatility)

schedule.every().minute.at(":15").do(get_latest_stocks)

client = tsl_bot.Bot(intents=config.intents)
client.run(config.bot_token)
# Code written below this comment will never be executed