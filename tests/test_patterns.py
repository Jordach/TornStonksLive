"""Each pattern list only holds patterns whose TA-Lib output matches that direction.

/search and suggestion context report only positive values from BULLISH_PATTERNS and
only negative values from BEARISH_PATTERNS, so a pattern in the wrong list can never
show up. Some patterns are rare, so they're tried against two synthetic histories and
pass if either one produces them."""
import unittest

import numpy as np

try:
	from tsl_core.analysis import search as pattern_search
except ImportError:  # TA-Lib not installed
	pattern_search = None


def _plain_candles(n=200000, seed=1):
	"""Random walk with small random wicks."""
	rng = np.random.default_rng(seed)
	close = np.cumsum(rng.normal(0, 1, n)) + 1000
	open_ = close + rng.normal(0, 1, n)
	high = np.maximum(open_, close) + np.abs(rng.normal(0, 1, n))
	low = np.minimum(open_, close) - np.abs(rng.normal(0, 1, n))
	return open_, high, low, close


def _varied_candles(n=200000, seed=7):
	"""Trending stretches, gaps, tiny-to-large bodies and often no wicks at all."""
	rng = np.random.default_rng(seed)
	drift = np.repeat(rng.choice([-0.6, 0.0, 0.6], n // 50 + 1), 50)[:n]
	body = rng.normal(0, 1, n) * rng.choice([0.05, 1.0, 3.0], n, p=[0.2, 0.5, 0.3]) + drift
	gap = rng.normal(0, 1, n) * rng.choice([0.0, 2.0], n, p=[0.7, 0.3])
	# Each candle opens at the previous close plus any gap
	close = 1000 + np.cumsum(gap + body)
	open_ = close - body

	def wick():
		return np.abs(rng.normal(0, 1, n)) * rng.choice([0.0, 0.3, 2.0], n, p=[0.3, 0.4, 0.3])

	high = np.maximum(open_, close) + wick()
	low = np.minimum(open_, close) - wick()
	return open_, high, low, close


@unittest.skipIf(pattern_search is None, "TA-Lib is not installed")
class PatternDirectionTests(unittest.TestCase):
	@classmethod
	def setUpClass(cls):
		cls.histories = [_plain_candles(), _varied_candles()]

	def _extreme(self, func, pick):
		return pick(pick(func(*h)) for h in self.histories)

	def test_bullish_patterns_can_fire_bullish(self):
		for func, name in pattern_search.BULLISH_PATTERNS:
			with self.subTest(pattern=name):
				self.assertGreater(self._extreme(func, max), 0, name + " never returns a bullish value")

	def test_bearish_patterns_can_fire_bearish(self):
		for func, name in pattern_search.BEARISH_PATTERNS:
			with self.subTest(pattern=name):
				self.assertLess(self._extreme(func, min), 0, name + " never returns a bearish value")

	def test_names_unique(self):
		names = [n for _, n in pattern_search.BULLISH_PATTERNS + pattern_search.BEARISH_PATTERNS]
		for entry in pattern_search.BOTH_PATTERNS:
			names += list(entry[2:])
		self.assertEqual(len(names), len(set(names)))


if __name__ == "__main__":
	unittest.main()
