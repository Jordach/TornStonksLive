import requests
import json
import importlib
import pkgutil
import cryptography
import schedule
import traceback
from discord import app_commands

import tsl_config.config as config
import tsl_core.functions as tsl_lib
import tsl_bot.bot as tsl_bot

config.read_token()
config.read_admins()
config.read_user_alerts()
config.read_alerts()
config.read_channels()
config.read_suggestions()

current_day = tsl_lib.util.current_date()

# Back fill the DBs with data
def backfill_db():
	# n_times = 1200
	n_times = 12000
	for ticker in tsl_lib.stock_lut:
		tsl_lib.util.write_log("[INFO]: Downloading " + ticker + ".", current_day)
		tsl_lib.db.import_from_tornsy(ticker, tsl_lib.intervals, limit=n_times)
		tsl_lib.util.write_log("[INFO]: " + ticker + " added to DB.", current_day)

perform_backfill = True
if perform_backfill:
	backfill_db()

tornsy_api_address = "https://tornsy.com/api/stocks?interval=m1,h1,d1,w1,n1"
tornsy_data =""
try:
	tornsy_data = requests.get(tornsy_api_address, timeout=30)
except:
	raise Exception("Tornsy probably timed out - you likely have no network access.")

# Scheduled jobs run on a background thread, but anything that touches Discord or the
# shared alert lists must run on the bot's event loop. This hands `func` over to it.
def run_on_bot_loop(func, description):
	def runner():
		try:
			func(config.client)
		except Exception:
			tsl_lib.util.write_log("[WARNING] Potential problem with " + description + ":\n" + traceback.format_exc(), current_day)
	config.client.loop.call_soon_threadsafe(runner)

def get_latest_stocks():
	global current_day
	current_day = tsl_lib.util.current_date()
	global tornsy_data
	try:
		tornsy_data = requests.get(tornsy_api_address, timeout=20)
	except:
		tsl_lib.util.write_log("[WARNING] Tornsy appears to be having issues", current_day)
		return

	if tornsy_data.status_code == 200:
		config.json_data = json.loads(tornsy_data.text)
		tsl_lib.db.update_from_tornsy(config.json_data, tsl_lib.intervals)
		if config.bot_started:
			run_on_bot_loop(tsl_bot.Bot.process_stockdata, "stock alerts")
	else:
		tsl_lib.util.write_log("[WARNING] Server returned error code: " + str(tornsy_data.status_code), current_day)

# Get initial data
get_latest_stocks()

def check_volatility():
	if config.bot_started:
		run_on_bot_loop(tsl_bot.Bot.process_volatility, "volatility checks")

def check_daily_volatility():
	if config.bot_started:
		run_on_bot_loop(tsl_bot.Bot.process_daily_volatility, "volatility checks")

def check_weekly_volatility():
	if config.bot_started:
		run_on_bot_loop(tsl_bot.Bot.process_weekly_volatility, "volatility checks")

def suggests(horizon):
	# Training/scanning is CPU heavy, so it stays on the scheduler thread;
	# make_suggestions posts its results back to the bot loop thread-safely.
	if config.bot_started:
		try:
			tsl_bot.Bot.make_suggestions(config.client, horizon)
		except Exception:
			tsl_lib.util.write_log("[WARNING] Potential problem with " + horizon + " suggestions:\n" + traceback.format_exc(), current_day)

# Initiate background thread and jobs
# Suggestions run just after the daily candle closes at 00:00 TCT (UTC), so they
# always score a completed day. Weekly picks follow on Mondays.
if config.enable_suggestions:
	schedule.every().day.at("00:05", "UTC").do(suggests, "daily")
	schedule.every().monday.at("00:10", "UTC").do(suggests, "weekly")

enable_volatility = True
if enable_volatility:
	schedule.every().hour.at("00:45").do(check_volatility)
	schedule.every().hour.at("30:45").do(check_volatility)
	schedule.every().day.at("00:00:45").do(check_daily_volatility)
	schedule.every().monday.at("00:01:45").do(check_weekly_volatility)

schedule.every().minute.at(":15").do(get_latest_stocks)

config.client = tsl_bot.Bot(intents=config.intents)
# Auto-import all slash command modules so their decorators register
slash_packages = ["tsl_gold.commands"]  # add packages as needed
for package_name in slash_packages:
    package = importlib.import_module(package_name)
    for importer, modname, ispkg in pkgutil.walk_packages(
        package.__path__, prefix=package.__name__ + "."
    ):
        importlib.import_module(modname)
config.client.run(config.bot_token)
# Code written below this comment will never be executed due to async threading