import threading
import time
import traceback
import schedule
import requests
from tsl_core.analysis.predict import predict_stock as _predict_stock
from tsl_core.analysis.search import pattern_scan as _pattern_scan
from tsl_core.analysis.stochastic import get_stoch as _get_stoch
from tsl_core.analysis.stochastic import get_stoch_osc as _get_stoch_osc
from tsl_core.analysis.ulcer import get_ulcer as _get_ulcer
import tsl_core.analysis.swing as _swing
from tsl_core.datestr import update_date as _update_date
from tsl_core.db import get_stock_from_db as _get_stock_from_db
from tsl_core.db import get_tornsy_candles as _get_tornsy_candles
from tsl_core.db import load_recent as _load_recent
from tsl_core.db import backfill_pending as _backfill_pending
from tsl_core.db import has_pending_backfill as _has_pending_backfill
from tsl_core.db import update_from_tornsy as _update_from_tornsy
from tsl_core.db import get_stock_df as _get_stock_df
from tsl_core.db import suggestion_record as _suggestion_record
from tsl_core.db import suggestion_get_open as _suggestion_get_open
from tsl_core.db import suggestion_set_outcome as _suggestion_set_outcome
from tsl_core.db import suggestion_get_record as _suggestion_get_record
from tsl_core.log import write_log as _write_log

# This file is intended to where you push functions from the library parts
# and make them appear whole

# Known intervals
intervals =	["m1", "m5", "m15", "m30", "h1", "h2", "h4", "h6", "h12", "d1"]
# Quickly converts between name and ID
stock_lut = [
	"TSB",
	"TCI",
	"SYS",
	"LAG",
	"IOU",
	"GRN",
	"THS",
	"YAZ",
	"TCT",
	"CNC",
	"MSG",
	"TMI",
	"TCP",
	"IIL",
	"FHG",
	"SYM",
	"LSC",
	"PRN",
	"EWM",
	"TCM",
	"ELT",
	"HRG",
	"TGP",
	"MUN",
	"WSU",
	"IST",
	"BAG",
	"EVL",
	"MCS",
	"WLT",
	"TCC",
	"ASS",
	"CBD",
	"LOS",
	"PTS"
]

# Logging and utilities
class util:
	write_log = _write_log
	current_date = _update_date
	intervals =	intervals
	tickers = stock_lut

	def remap(val, val_min, val_max, map_min, map_max):
		return (val-val_min) / (val_max-val_min) * (map_max-map_min) + map_min
	def clamp_(val, min, max):
		if val <= min:
			return min
		elif val >= max:
			return max
		else:
			return val
	def get_torn_stock_data(api_key):
		return requests.get("https://api.torn.com/user/?selections=stocks&key=" + api_key, timeout=10)

	def lut_stock_id(name):
		# Torn stock IDs are 1-based positions in stock_lut. Unknown tickers return
		# "0" rather than len(stock_lut)+1, which pointed at a non-existent stock.
		name = str(name).upper()
		if name in stock_lut:
			return str(stock_lut.index(name) + 1)
		return "0"

	def strip_commas(value):
		return value.replace(",", "")

	# Nicked from https://schedule.readthedocs.io/en/stable/background-execution.html
	# But I don't think many will actually care.
	def run_continuously(interval=1):
		"""Continuously run, while executing pending jobs at each
		elapsed time interval.
		@return cease_continuous_run: threading. Event which can
		be set to cease continuous run. Please note that it is
		*intended behavior that run_continuously() does not run
		missed jobs*. For example, if you've registered a job that
		should run every minute and you set a continuous run
		interval of one hour then your job won't be run 60 times
		at each interval but only once.
		"""
		cease_continuous_run = threading.Event()

		class ScheduleThread(threading.Thread):
			@classmethod
			def run(cls):
				while not cease_continuous_run.is_set():
					# schedule does not catch job exceptions; without this a single
					# failed job kills the thread and all future jobs silently stop.
					try:
						schedule.run_pending()
					except Exception:
						try:
							_write_log("[ERROR] Scheduled job failed:\n" + traceback.format_exc(), _update_date())
						except Exception:
							traceback.print_exc()
					time.sleep(interval)

		# Daemon so the process can exit when the bot stops or crashes
		continuous_thread = ScheduleThread(daemon=True)
		continuous_thread.start()
		return cease_continuous_run

	stop_run_continously = run_continuously()

# Database functions
class db:
	get_stock = _get_stock_from_db
	get_stock_df = _get_stock_df
	suggestion_record = _suggestion_record
	suggestion_get_open = _suggestion_get_open
	suggestion_set_outcome = _suggestion_set_outcome
	suggestion_get_record = _suggestion_get_record
	get_tornsy_data = _get_tornsy_candles
	load_recent = _load_recent
	backfill_pending = _backfill_pending
	has_pending_backfill = _has_pending_backfill
	update_from_tornsy = _update_from_tornsy

# Analytic functions
class analysis:
	predict_stock = _predict_stock
	get_stoch_osc = _get_stoch_osc
	get_stoch = _get_stoch
	get_ulcer = _get_ulcer
	search = _pattern_scan
	swing = _swing

torn_api_error_codes = []
torn_api_error_codes.append(("Something went really, really wrong on Torn's end.", False))
torn_api_error_codes.append(("Somehow, the API key wasn't sent in this request.", False))
torn_api_error_codes.append(("Somehow, the API key is in the wrong format.", False))
torn_api_error_codes.append(("An incorrect basic type for a field was submitted.", False))
torn_api_error_codes.append(("An incorrect basic field for a selection was submitted.", False))
torn_api_error_codes.append(("Too many API requests for this key, try again in a minute.", False))
torn_api_error_codes.append(("Wrong ID for chosen field.", False))
torn_api_error_codes.append(("A requested selection is private, but how did we even manage to get here?.", False))
torn_api_error_codes.append(("IP is currently blocked. :(", False))
torn_api_error_codes.append(("Torn's API system is down. :(", False))
torn_api_error_codes.append(("The key owner is in Federal Jail.", True))
torn_api_error_codes.append(("Why are you changing keys every 60 seconds?", True))
torn_api_error_codes.append(("API cannot appear to read the key from the database, wait a few seconds and try again.", False))
torn_api_error_codes.append(("Key disabled since the key owner has been inactive for over a week.", True))
torn_api_error_codes.append(("Somehow this key's been used enough to reach the daily API calling limit.", False))
torn_api_error_codes.append(("This error is a temporary measure and is usually indicative of API testing.", False))
torn_api_error_codes.append(("This key doesn't have a high enough access level.", False))
torn_api_error_codes.append(("Torn's backend was blown out again, it wasn't me, promise! :(", False))