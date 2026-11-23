"""import_from_tornsy against a fake Tornsy: candles match a plain minute-by-minute roll-up."""
import os
import random
import sqlite3
import tempfile
import unittest

import tsl_core.db as db

INTERVALS = list(db.INTERVAL_SECONDS)


def _history(days, seed=1):
	"""Minute rows like Tornsy's m1 ([timestamp, "price", shares]), starting mid-day, with gaps."""
	rnd = random.Random(seed)
	t0 = 1_700_000_000 // 86400 * 86400 + 37 * 60
	rows, price = [], 100.0
	for i in range(days * 1440):
		if rnd.random() < 0.02:
			continue
		price = max(1.0, price + rnd.gauss(0, 0.3))
		rows.append([t0 + i * 60, "%.2f" % price, 1])
	return rows


def _expected(rows, seconds):
	"""Candles by applying the live feed's merge one minute at a time."""
	candles = {}
	for ts, price, _ in rows:
		price = float(price)
		start = ts // seconds * seconds
		if start in candles:
			o, h, l, c = candles[start]
			candles[start] = (o, max(h, price), min(l, price), price)
		else:
			candles[start] = (price, price, price, price)
	return [(d,) + candles[d] for d in sorted(candles)]


class FakeTornsy:
	def __init__(self, rows):
		self.rows, self.calls = rows, 0

	def __call__(self, ticker, interval, limit, to="NONE", timeout=30):
		self.calls += 1
		rows = self.rows if to == "NONE" else [r for r in self.rows if r[0] <= int(to)]
		return {"data": rows[-min(int(limit), 1440):]}


class ImportFromTornsyTests(unittest.TestCase):
	def setUp(self):
		self._old_cwd = os.getcwd()
		self._tmp = tempfile.TemporaryDirectory()
		os.chdir(self._tmp.name)
		os.mkdir("db")
		self._real_fetch, self._real_time = db.get_tornsy_candles, db.time

		class NoSleep:
			sleep = staticmethod(lambda s: None)
			time = staticmethod(self._real_time.time)
		db.time = NoSleep

	def tearDown(self):
		db.get_tornsy_candles, db.time = self._real_fetch, self._real_time
		os.chdir(self._old_cwd)
		try:
			self._tmp.cleanup()
		except OSError:
			pass

	def _tables(self):
		con = sqlite3.connect(os.path.join("db", "db_tsb.db"))
		try:
			return {i: con.execute("SELECT date, open, high, low, close FROM " + i + " ORDER BY date").fetchall() for i in INTERVALS}
		finally:
			con.close()

	def _assert_candles(self, rows):
		tables = self._tables()
		for interval, seconds in db.INTERVAL_SECONDS.items():
			with self.subTest(interval=interval):
				self.assertEqual(tables[interval], _expected(rows, seconds))

	def test_fresh_import_rolls_up_every_interval(self):
		rows = _history(4)
		db.get_tornsy_candles = FakeTornsy(rows)
		seen = []
		written = db.import_from_tornsy("TSB", INTERVALS, limit=100, progress=lambda m, oldest: seen.append((m, oldest)))
		self.assertEqual(written, len(rows))
		self._assert_candles(rows)
		self.assertEqual(seen[-1], (len(rows), rows[0][0]))
		self.assertEqual([m for m, _ in seen], sorted(m for m, _ in seen))

	def test_top_up_refetches_the_last_stored_minute(self):
		rows = _history(4)
		cut = len(rows) // 2
		db.get_tornsy_candles = FakeTornsy(rows[:cut])
		db.import_from_tornsy("TSB", INTERVALS, limit=100)

		# The last stored minute was still forming; Tornsy now has its final price
		later = rows[:cut - 1] + [[rows[cut - 1][0], "500.00", 1]] + rows[cut:]
		fake = FakeTornsy(later)
		db.get_tornsy_candles = fake
		written = db.import_from_tornsy("TSB", INTERVALS, limit=100)
		self.assertEqual(written, len(rows) - cut + 1)
		self.assertLessEqual(fake.calls, 3)  # stopped at the stored data, didn't walk all history
		# Stored candles keep the first-seen price for that minute as open, like the live feed
		self._assert_candles(rows[:cut] + later[cut - 1:])

	def test_limit_zero_fetches_one_page(self):
		fake = FakeTornsy(_history(4))
		db.get_tornsy_candles = fake
		self.assertLessEqual(db.import_from_tornsy("TSB", INTERVALS, limit=0), 1440)
		self.assertEqual(fake.calls, 1)

	def test_unreachable_returns_none(self):
		db.get_tornsy_candles = lambda *a, **k: False
		self.assertIsNone(db.import_from_tornsy("TSB", INTERVALS, limit=100))
		self.assertFalse(os.path.exists(os.path.join("db", "db_tsb.db")))

	def test_bad_interval_is_rejected(self):
		with self.assertRaises(ValueError):
			db.import_from_tornsy("TSB", ["m1; DROP TABLE m1"], limit=0)


if __name__ == "__main__":
	unittest.main()
