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

_backfill_running = threading.Lock()

def start_backfill():
	"""Start the background backfill thread, unless one is already running."""
	if not _backfill_running.acquire(blocking=False):
		return

	def run():
		try:
			backfill_history()
		except Exception:
			tsl_lib.util.write_log("[WARNING] Background backfill stopped:\n" + traceback.format_exc(), tsl_lib.util.current_date())
		finally:
			_backfill_running.release()
	threading.Thread(target=run, name="backfill", daemon=True).start()

def find_history_gaps():
	"""Queue holes in stored minute history (outages the backfill never covered) for backfilling."""
	state = config.backfill_state
	found = {}
	try:
		for n, ticker in enumerate(tsl_lib.stock_lut, start=1):
			state.update(scanning=True, position=n, total=len(tsl_lib.stock_lut), ticker=ticker)
			try:
				gaps = tsl_lib.db.queue_history_gaps(ticker)
			except Exception:
				tsl_lib.util.write_log("[WARNING] Gap check failed for " + ticker + ":\n" + traceback.format_exc(), tsl_lib.util.current_date())
				continue
			if gaps:
				found[ticker] = gaps
	finally:
		state.update(scanning=False, ticker=None)
	if found:
		minutes = sum((hi - lo) // 60 for gaps in found.values() for lo, hi in gaps)
		count = sum(len(gaps) for gaps in found.values())
		tsl_lib.util.write_log("[INFO] Found " + str(count) + " gap(s) in stored price history (" + "{:,}".format(minutes) + " minutes) across " + str(len(found)) + " stock(s); queued for backfill.", tsl_lib.util.current_date())

def backfill_history():
	"""Background thread: queue gaps in stored history, then fetch every pending range, retrying while Tornsy is down."""
	retry_every = 600
	skip = set()  # stocks that hit an unexpected error; retried on the next run (daily, or a restart)
	state = config.backfill_state
	find_history_gaps()
	while True:
		paused = _backfill_pass(skip)
		state["paused"] = paused
		if not paused:
			state["retry_at"] = None
			return
		state["retry_at"] = time.time() + retry_every
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
	state = config.backfill_state
	state.update(running=True, total=len(tickers), started=started, paused=[], retry_at=None)
	try:
		_backfill_stocks(tickers, skip, paused, started, report_every)
	finally:
		state.update(running=False, ticker=None, finished=time.time())
	tsl_lib.util.write_log("[INFO] Background backfill pass finished in " + _duration(time.time() - started) + ".", tsl_lib.util.current_date())
	return paused

def _backfill_stocks(tickers, skip, paused, started, report_every):
	state = config.backfill_state
	for n, ticker in enumerate(tickers, start=1):
		prefix = "[INFO] Backfill " + str(n) + "/" + str(len(tickers)) + " " + ticker + ": "
		stock_started = time.time()
		last_report = [stock_started]
		state.update(position=n, ticker=ticker, minutes=0, oldest=None, stock_started=stock_started)

		def progress(minutes, oldest):
			state.update(minutes=minutes, oldest=oldest)
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
			tsl_lib.util.write_log("[WARNING] Backfill failed for " + ticker + "; it will resume on the next run:\n" + traceback.format_exc(), tsl_lib.util.current_date())
			continue
		if written is None:
			paused.append(ticker)
			tsl_lib.util.write_log("[WARNING] Backfill paused for " + ticker + ": Tornsy isn't responding. What was fetched is saved.", tsl_lib.util.current_date())
			continue

		elapsed = time.time() - started
		remaining = len(tickers) - n
		eta = (", about " + _duration(elapsed / n * remaining) + " left") if remaining else ""
		tsl_lib.util.write_log(prefix + "saved " + "{:,}".format(written) + " minutes in " + _duration(time.time() - stock_started) + eta + ".", tsl_lib.util.current_date())

if config.features["backfill"]:
	load_recent_prices()
	start_backfill()

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

def _fetch_tornsy():
	"""Tornsy's live feed, or None (after logging why) if it can't be used."""
	global tornsy_data
	try:
		tornsy_data = requests.get(tornsy_api_address, timeout=20)
	except requests.RequestException:
		tsl_lib.util.write_log("[WARNING] Tornsy appears to be having issues", current_day)
		return None
	if tornsy_data.status_code != 200:
		tsl_lib.util.write_log("[WARNING] Tornsy returned error code: " + str(tornsy_data.status_code), current_day)
		return None
	try:
		feed = json.loads(tornsy_data.text)
	except ValueError:
		tsl_lib.util.write_log("[WARNING] Tornsy returned something that isn't JSON", current_day)
		return None
	if not feed.get("data") or "timestamp" not in feed:
		tsl_lib.util.write_log("[WARNING] Tornsy returned no stock data", current_day)
		return None
	return feed

def _fetch_torn_fallback():
	"""Emergency feed from Torn's own API with the bot's key, or None (after logging why)."""
	api_key, kind = config.get_fallback_key()
	if api_key is None:
		tsl_lib.util.write_log("[WARNING] No Torn API key stored for the emergency feed; set one with /botkey", current_day)
		return None
	# Only the previous Torn snapshot is useful for the m1 comparison; a Tornsy feed
	# from before the outage could be minutes old
	previous = config.json_data if config.live_source == "torn" else None
	try:
		return tsl_lib.torn_feed.fetch(api_key, previous)
	except requests.RequestException:
		# Don't log the exception: its message contains the URL, and so the key
		tsl_lib.util.write_log("[WARNING] Torn's API also failed to respond (" + kind + " key)", current_day)
	except (tsl_lib.torn_feed.TornFeedError, ValueError, KeyError) as err:
		tsl_lib.util.write_log("[WARNING] Torn's API fallback failed (" + kind + " key): " + str(err), current_day)
	return None

def get_latest_stocks():
	global current_day
	current_day = tsl_lib.util.current_date()

	feed, source = _fetch_tornsy(), "tornsy"
	if feed is None:
		feed, source = _fetch_torn_fallback(), "torn"
		if feed is None:
			return

	if source != config.live_source and config.live_source is not None:
		if source == "torn":
			tsl_lib.util.write_log("[WARNING] Using Torn's API for live prices until Tornsy recovers", current_day)
		else:
			tsl_lib.util.write_log("[INFO] Tornsy is back; live prices are coming from it again", current_day)
	elif source == "torn" and config.live_source is None:
		tsl_lib.util.write_log("[WARNING] Tornsy is down at startup; using Torn's API for live prices", current_day)
	config.live_source = source

	config.json_data = feed
	tsl_lib.db.update_from_tornsy(config.json_data, tsl_lib.intervals)
	if config.bot_started:
		run_on_bot_loop(tsl_bot.Bot.process_stockdata, "stock alerts")

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

# With the bot rarely restarting, also check daily for holes a live-feed outage left
# while it kept running, and fill them (a no-op if a backfill is already running)
if config.features["backfill"]:
	schedule.every().day.at("03:30", "UTC").do(start_backfill)

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