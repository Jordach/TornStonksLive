from tsl_core.analysis.predict import predict_stock as _predict_stock
from tsl_core.analysis.search import pattern_scan as _pattern_scan
from tsl_core.analysis.stochastic import get_stoch as _get_stoch
from tsl_core.analysis.stochastic import get_stoch_osc as _get_stoch_osc
from tsl_core.analysis.ulcer import get_ulcer as _get_ulcer
from tsl_core.datestr import update_date as _update_date
from tsl_core.db import get_stock_from_db as _get_stock_from_db
from tsl_core.db import get_tornsy_candles as _get_tornsy_candles
from tsl_core.db import import_from_tornsy as _import_from_tornsy
from tsl_core.db import update_from_tornsy as _update_from_tornsy
from tsl_core.log import write_log as _write_log

# This file is intended to where you push functions from the library parts
# and make them appear whole

# Logging and utilities
class util:
	write_log = _write_log
	current_date = _update_date

	def remap(val, val_min, val_max, map_min, map_max):
		return (val-val_min) / (val_max-val_min) * (map_max-map_min) + map_min
	def clamp_(val, min, max):
		if val <= min:
			return min
		elif val >= max:
			return max
		else:
			return val

# Database functions
class db:
	get_stock = _get_stock_from_db
	get_tornsy_data = _get_tornsy_candles
	import_from_tornsy = _import_from_tornsy
	update_from_tornsy = _update_from_tornsy

# Analytic functions
class analysis:
	predict_stock = _predict_stock
	get_stoch_osc = _get_stoch_osc
	get_stoch = _get_stoch
	get_ulcer = _get_ulcer
	search = _pattern_scan