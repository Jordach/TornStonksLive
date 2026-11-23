"""Startup load and background backfill against a fake Tornsy: every interval matches a plain
minute-by-minute roll-up, whatever order the minutes were written in."""
import os
import random
import sqlite3
import tempfile
import unittest

import tsl_core.db as db

INTERVALS = list(db.INTERVAL_SECONDS)
DAY = 1440


def _history(days, seed=1):
	"""Minute rows like Tornsy's m1 ([timestamp, "price", shares]), starting mid-day, with gaps."""
	rnd = random.Random(seed)
	t0 = 1_700_000_000 // 86400 * 86400 + 37 * 60
	rows, price = [], 100.0
	for i in range(days * DAY):
		if rnd.random() < 0.02:
			continue
		price = max(1.0, price + rnd.gauss(0, 0.3))
		rows.append([t0 + i * 60, "%.2f" % price, 1])
	return rows


def _expected(ticks, seconds):
	"""Candles from applying the live feed's merge one tick at a time, in time order."""
	candles = {}
	for ts, price, _ in ticks:
		price = float(price)
		start = ts // seconds * seconds
		if start in candles:
			o, h, l, c = candles[start]
			candles[start] = (o, max(h, price), min(l, price), price)
		else:
			candles[start] = (price, price, price, price)
	return [(d,) + candles[d] for d in sorted(candles)]


class FakeTornsy:
	"""Serves `rows` as Tornsy's m1 history; `fail_after` simulates an outage."""
	def __init__(self, rows, fail_after=None):
		self.rows, self.calls, self.fail_after = rows, 0, fail_after

	def __call__(self, ticker, interval, limit, to="NONE", timeout=30):
		self.calls += 1
		if self.fail_after is not None and self.calls > self.fail_after:
			return False
		rows = self.rows if to == "NONE" else [r for r in self.rows if r[0] <= int(to)]
		return {"data": rows[-min(int(limit), DAY):]}


class BackfillTests(unittest.TestCase):
	def setUp(self):
		self._old_cwd = os.getcwd()
		self._tmp = tempfile.TemporaryDirectory()
		os.chdir(self._tmp.name)
		os.mkdir("db")
		self._real_fetch, self._real_time = db.get_tornsy_candles, db.time
		self.now = 0
		test = self

		class FakeTime:
			sleep = staticmethod(lambda s: None)
			time = staticmethod(lambda: test.now)
		db.time = FakeTime

	def tearDown(self):
		db.get_tornsy_candles, db.time = self._real_fetch, self._real_time
		os.chdir(self._old_cwd)
		try:
			self._tmp.cleanup()
		except OSError:
			pass

	def _serve(self, rows, **kw):
		"""Point the fake Tornsy at `rows`, with the clock just after the newest one."""
		fake = FakeTornsy(rows, **kw)
		db.get_tornsy_candles = fake
		self.now = rows[-1][0] + 59
		return fake

	def _pending(self):
		con = sqlite3.connect(os.path.join("db", "db_tsb.db"))
		try:
			return con.execute("SELECT lo, hi FROM backfill_pending ORDER BY hi").fetchall()
		finally:
			con.close()

	def _assert_candles(self, ticks):
		con = sqlite3.connect(os.path.join("db", "db_tsb.db"))
		try:
			for interval, seconds in db.INTERVAL_SECONDS.items():
				with self.subTest(interval=interval):
					stored = con.execute("SELECT date, open, high, low, close FROM " + interval + " ORDER BY date").fetchall()
					self.assertEqual(stored, _expected(ticks, seconds))
		finally:
			con.close()

	def test_fresh_install_loads_a_day_then_backfills_the_rest(self):
		rows = _history(10)
		self._serve(rows)
		written, pending = db.load_recent("TSB", INTERVALS)
		self.assertTrue(DAY <= written <= 2 * DAY, written)
		self.assertTrue(pending)
		self.assertTrue(db.has_pending_backfill("TSB"))
		self._assert_candles(rows[-written:])

		seen = []
		total = db.backfill_pending("TSB", INTERVALS, progress=lambda m, oldest: seen.append(m), chunk_minutes=3 * DAY)
		self.assertEqual(total, len(rows) - written)
		self.assertEqual(seen, sorted(seen))
		self.assertFalse(db.has_pending_backfill("TSB"))
		self._assert_candles(rows)

	def test_live_minutes_written_during_the_backfill_are_kept(self):
		rows = _history(5)
		self._serve(rows)
		db.load_recent("TSB", INTERVALS)

		# The live feed stores a newer minute before the background backfill runs
		live_ts = rows[-1][0] + 60
		db.update_from_tornsy({"timestamp": live_ts, "data": [{"stock": "TSB", "price": "321.00"}]}, INTERVALS)
		db.backfill_pending("TSB", INTERVALS)
		self._assert_candles(rows + [[live_ts, "321.00", 1]])

	def test_short_outage_needs_no_background_backfill(self):
		rows = _history(6)
		cut = len(rows) - 300
		self._serve(rows[:cut])
		db.load_recent("TSB", INTERVALS)
		db.backfill_pending("TSB", INTERVALS)

		# Back after ~5 hours; the last stored minute was still forming and has a final price
		later = rows[:cut - 1] + [[rows[cut - 1][0], "500.00", 1]] + rows[cut:]
		fake = self._serve(later)
		written, pending = db.load_recent("TSB", INTERVALS)
		self.assertFalse(pending)
		self.assertEqual(written, len(rows) - cut + 1)
		self.assertEqual(fake.calls, 1)
		self._assert_candles(rows[:cut] + later[cut - 1:])

	def test_long_outage_backfills_only_the_gap(self):
		rows = _history(20)
		cut = len(rows) // 2
		self._serve(rows[:cut])
		db.load_recent("TSB", INTERVALS)
		db.backfill_pending("TSB", INTERVALS)

		fake = self._serve(rows)
		newest_stored = rows[cut - 1][0]
		written, pending = db.load_recent("TSB", INTERVALS)
		self.assertTrue(pending)
		self.assertEqual(self._pending()[0][0], newest_stored)
		db.backfill_pending("TSB", INTERVALS)
		self.assertLessEqual(fake.calls, 13)  # ~10 days of gap, not all 20 days
		self._assert_candles(rows)

	def test_interrupted_backfill_resumes_where_it_stopped(self):
		rows = _history(15)
		self._serve(rows)
		db.load_recent("TSB", INTERVALS)
		first_hi = self._pending()[0][1]

		self._serve(rows, fail_after=7)
		self.assertIsNone(db.backfill_pending("TSB", INTERVALS, chunk_minutes=2 * DAY))
		resumed_hi = self._pending()[0][1]
		self.assertLess(resumed_hi, first_hi)  # committed chunks aren't fetched again

		fake = self._serve(rows)
		db.backfill_pending("TSB", INTERVALS, chunk_minutes=2 * DAY)
		self.assertLess(fake.calls, 15)
		self.assertFalse(db.has_pending_backfill("TSB"))
		self._assert_candles(rows)

	def test_tornsy_down_at_startup_leaves_everything_pending(self):
		rows = _history(4)
		self._serve(rows, fail_after=0)
		self.assertIsNone(db.load_recent("TSB", INTERVALS))
		# Open-ended: the live feed can't fill anything while Tornsy is down either
		self.assertEqual(self._pending(), [(None, None)])

		# Tornsy is back a few minutes later and the live feed has stored the newest minute
		later = rows + [[rows[-1][0] + 60 * k, "%.2f" % (90 + k), 1] for k in range(1, 6)]
		self._serve(later)
		db.update_from_tornsy({"timestamp": later[-1][0], "data": [{"stock": "TSB", "price": later[-1][1]}]}, INTERVALS)
		db.backfill_pending("TSB", INTERVALS)
		self.assertFalse(db.has_pending_backfill("TSB"))
		self._assert_candles(later)

	def test_summary_reports_first_last_and_pending(self):
		self.assertEqual(db.backfill_summary("TSB"), (None, None, []))
		self.assertFalse(os.path.exists(os.path.join("db", "db_tsb.db")))  # read-only: no file created

		rows = _history(5)
		self._serve(rows)
		written, _ = db.load_recent("TSB", INTERVALS)
		first, last, pending = db.backfill_summary("TSB")
		self.assertEqual((first, last), (rows[-written][0], rows[-1][0]))
		self.assertEqual(pending, [(None, first)])

		db.backfill_pending("TSB", INTERVALS)
		self.assertEqual(db.backfill_summary("TSB"), (rows[0][0], rows[-1][0], []))

	def _store(self, rows):
		"""Store `rows` as a complete install would have them."""
		self._serve(rows)
		db.load_recent("TSB", INTERVALS)
		db.backfill_pending("TSB", INTERVALS)

	def test_hole_in_stored_history_is_queued_and_filled(self):
		rows = _history(12)
		start = next(i for i, r in enumerate(rows) if r[0] >= rows[0][0] + 3 * 86400)
		end = next(i for i, r in enumerate(rows) if r[0] >= rows[start][0] + 2 * 86400 + 4321)
		self._store(rows[:start] + rows[end:])  # an old outage: two days missing

		self._serve(rows)  # Tornsy has them
		queued = db.queue_history_gaps("TSB")
		self.assertEqual(queued, [(rows[start - 1][0] + 60, rows[end][0])])  # short gaps (< 1h) are left alone
		db.backfill_pending("TSB", INTERVALS)
		self.assertFalse(db.has_pending_backfill("TSB"))
		self._assert_candles(rows)

	def test_hole_tornsy_lacks_is_queued_once(self):
		rows = _history(8)
		holey = rows[:3000] + rows[3200:]
		self._store(holey)
		self._serve(holey)  # Tornsy doesn't have those minutes either
		self.assertEqual(len(db.queue_history_gaps("TSB")), 1)
		db.backfill_pending("TSB", INTERVALS)
		self.assertEqual(db.queue_history_gaps("TSB"), [])  # already scanned, not queued again
		self.assertFalse(db.has_pending_backfill("TSB"))

	def test_later_hole_is_found_by_the_next_scan(self):
		rows = _history(10)
		cut = len(rows) // 2
		self._store(rows[:cut])
		self.assertEqual(db.queue_history_gaps("TSB"), [])

		# The live feed later misses two hours while the bot keeps running
		later = rows[:cut + 300]
		missed = rows[cut + 100:cut + 230]
		for ts, price, _ in rows[cut:cut + 100] + rows[cut + 230:cut + 300]:
			db.update_from_tornsy({"timestamp": ts, "data": [{"stock": "TSB", "price": price}]}, INTERVALS)
		self._serve(later)
		queued = db.queue_history_gaps("TSB")
		self.assertEqual(len(queued), 1)
		self.assertLessEqual(queued[0][0], missed[0][0])
		self.assertGreater(queued[0][1], missed[-1][0])
		db.backfill_pending("TSB", INTERVALS)
		self._assert_candles(later)

	def test_hole_already_pending_is_not_queued_twice(self):
		rows = _history(20)
		cut = len(rows) // 2
		self._store(rows[:cut])
		self._serve(rows)
		db.load_recent("TSB", INTERVALS)  # long outage: the hole is already pending
		self.assertEqual(len(self._pending()), 1)
		self.assertEqual(db.queue_history_gaps("TSB"), [])

	def test_bad_interval_is_rejected(self):
		with self.assertRaises(ValueError):
			db.load_recent("TSB", ["m1; DROP TABLE m1"])


if __name__ == "__main__":
	unittest.main()
