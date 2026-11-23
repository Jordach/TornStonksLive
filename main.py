import datetime
import os
import threading
import time
import requests
import json
import importlib
import pkgutil
import schedule
import traceback

import tsl_config.config as config
import tsl_core.functions as tsl_lib
import tsl_bot.bot as tsl_bot

config.read_token()
config.read_admins()
config.read_user_alerts()
# Features first: they decide whether the channel files are required
config.read_features()
config.read_alerts()
config.read_suggestions()

current_day = tsl_lib.util.current_date()

# Per-stock price databases live here; a fresh install doesn't have it yet
os.makedirs("db", exist_ok=True)

def _duration(seconds):
	seconds = int(seconds)
	if seconds < 60:
		return str(seconds) + "s"
	if seconds < 3600:
		return str(seconds // 60) + "m " + str(seconds % 60) + "s"
	return str(seconds // 3600) + "h " + str(seconds % 3600 // 60) + "m"

# Price history comes from Tornsy's m1 minutes, which every other interval is built from.
# Before the bot connects, each stock gets the minutes since it was last stored, or at
# least the last day for a new install or after a longer outage, so commands have data
# straight away. Anything older that's missing (years of it for a new install) is
# fetched by a background thread while the live feed keeps adding new minutes.
# Longer gaps in daily candles are also filled by fill_daily_gaps_from_tornsy() before
# suggestions.
def load_recent_prices():
	tickers = tsl_lib.stock_lut
	started = time.time()
	for ticker in tickers:
		try:
			result = tsl_lib.db.load_recent(ticker, tsl_lib.intervals)
		except Exception:
			# One stock failing (e.g. a Tornsy hiccup) shouldn't stop the bot starting
			tsl_lib.util.write_log("[WARNING] Loading recent prices failed for " + ticker + ":\n" + traceback.format_exc(), current_day)
			continue
		if result is None:
			tsl_lib.util.write_log("[WARNING] Tornsy could not be reached for " + ticker + "; its missing prices will be fetched in the background.", current_day)
	tsl_lib.util.write_log("[INFO] Loaded recent prices for " + str(len(tickers)) + " stocks in " + _duration(time.time() - started) + ".", current_day)

def backfill_history():
	"""Background thread: fetch the minutes load_recent_prices() left pending, retrying while Tornsy is down."""
	retry_every = 600
	skip = set()  # stocks that hit an unexpected error; retried on the next start
	while True:
		paused = _backfill_pass(skip)
		if not paused:
			return
		tsl_lib.util.write_log("[INFO] Backfill will retry " + ", ".join(paused) + " in " + _duration(retry_every) + ".", tsl_lib.util.current_date())
		time.sleep(retry_every)

def _backfill_pass(skip):
	"""Backfill every stock with pending minutes. Returns the stocks paused by a Tornsy outage."""
	# A full history is ~2000 requests per stock, so report at most this often
	report_every = 15
	paused = []
	try:
		tickers = [t for t in tsl_lib.stock_lut if t not in skip and tsl_lib.db.has_pending_backfill(t)]
	except Exception:
		tsl_lib.util.write_log("[WARNING] Could not check for missing price history:\n" + traceback.format_exc(), tsl_lib.util.current_date())
		return paused
	if not tickers:
		return paused
	started = time.time()
	tsl_lib.util.write_log("[INFO] Fetching older price history for " + str(len(tickers)) + " stock(s) in the background.", tsl_lib.util.current_date())
	for n, ticker in enumerate(tickers, start=1):
		prefix = "[INFO] Backfill " + str(n) + "/" + str(len(tickers)) + " " + ticker + ": "
		stock_started = time.time()
		last_report = [stock_started]

		def progress(minutes, oldest):
			now = time.time()
			if now - last_report[0] < report_every:
				return
			last_report[0] = now
			back_to = datetime.datetime.fromtimestamp(oldest, datetime.timezone.utc).strftime("%Y-%m-%d")
			tsl_lib.util.write_log(prefix + "{:,}".format(minutes) + " minutes, back to " + back_to + " (" + _duration(now - stock_started) + ")", tsl_lib.util.current_date())

		try:
			written = tsl_lib.db.backfill_pending(ticker, tsl_lib.intervals, progress=progress)
		except Exception:
			skip.add(ticker)
			tsl_lib.util.write_log("[WARNING] Backfill failed for " + ticker + "; it will resume on the next start:\n" + traceback.format_exc(), tsl_lib.util.current_date())
			continue
		if written is None:
			paused.append(ticker)
			tsl_lib.util.write_log("[WARNING] Backfill paused for " + ticker + ": Tornsy isn't responding. What was fetched is saved.", tsl_lib.util.current_date())
			continue

		elapsed = time.time() - started
		remaining = len(tickers) - n
		eta = (", about " + _duration(elapsed / n * remaining) + " left") if remaining else ""
		tsl_lib.util.write_log(prefix + "saved " + "{:,}".format(written) + " minutes in " + _duration(time.time() - stock_started) + eta + ".", tsl_lib.util.current_date())
	tsl_lib.util.write_log("[INFO] Background backfill pass finished in " + _duration(time.time() - started) + ".", tsl_lib.util.current_date())
	return paused

if config.features["backfill"]:
	load_recent_prices()
	threading.Thread(target=backfill_history, name="backfill", daemon=True).start()

tornsy_api_address = "https://tornsy.com/api/stocks?interval=m1,h1,d1,w1,n1"
tornsy_data = None

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

# Get initial data; if Tornsy is down the bot still starts and the every-minute
# job below keeps retrying
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

# Daily/weekly volatility follow the candle close at 00:00 TCT (UTC), whatever the
# host's own time zone is.
if config.features["volatility"]:
	schedule.every().hour.at("00:45").do(check_volatility)
	schedule.every().hour.at("30:45").do(check_volatility)
	schedule.every().day.at("00:00:45", "UTC").do(check_daily_volatility)
	schedule.every().monday.at("00:01:45", "UTC").do(check_weekly_volatility)

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