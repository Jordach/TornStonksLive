import unittest

import tsl_core.torn_feed as torn_feed


def torn_response(tsb_price=1012.345, tsb_shares=5000, tsb_investors=40):
	"""Shaped like api.torn.com/torn/?selections=stocks (v1)."""
	return {"stocks": {
		"2": {"stock_id": 2, "name": "Torn City Investments", "acronym": "TCI", "current_price": 980.5,
			"market_cap": 9805000, "total_shares": 10000, "investors": 12, "benefit": {}},
		"1": {"stock_id": 1, "name": "Torn & Shanghai Banking", "acronym": "TSB", "current_price": tsb_price,
			"market_cap": 1, "total_shares": tsb_shares, "investors": tsb_investors, "benefit": {}},
	}}


class TornFeedTests(unittest.TestCase):
	def test_shape_matches_tornsy(self):
		feed = torn_feed.to_tornsy_format(torn_response(), now=1700000059)
		self.assertEqual(feed["timestamp"], 1700000040)  # floored to the minute
		self.assertEqual([d["stock"] for d in feed["data"]], ["TSB", "TCI"])  # by stock id
		tsb = feed["data"][0]
		self.assertEqual(tsb["name"], "Torn & Shanghai Banking")
		self.assertEqual(tsb["price"], "1012.35")  # Tornsy sends prices as strings
		self.assertEqual(float(tsb["price"]), 1012.35)
		self.assertEqual(tsb["total_shares"], 5000)
		self.assertEqual(tsb["investors"], 40)

	def test_first_minute_has_no_change(self):
		# No previous snapshot: m1 repeats now, so whale alerts see no movement
		tsb = torn_feed.to_tornsy_format(torn_response(), now=0)["data"][0]
		self.assertEqual(tsb["interval"]["m1"]["total_shares"], tsb["total_shares"])
		self.assertEqual(tsb["interval"]["m1"]["investors"], tsb["investors"])

	def test_m1_comes_from_previous_snapshot(self):
		first = torn_feed.to_tornsy_format(torn_response(), now=0)
		second = torn_feed.to_tornsy_format(torn_response(tsb_price=1100, tsb_shares=9000, tsb_investors=45), first, now=60)
		tsb = second["data"][0]
		self.assertEqual(tsb["interval"]["m1"], {"price": "1012.35", "total_shares": 5000, "investors": 40})
		self.assertEqual(tsb["total_shares"], 9000)

	def test_errors(self):
		with self.assertRaises(torn_feed.TornFeedError):
			torn_feed.to_tornsy_format({"error": {"code": 2, "error": "Incorrect key"}})
		with self.assertRaises(torn_feed.TornFeedError):
			torn_feed.to_tornsy_format({"stocks": {}})

	def test_feeds_the_whale_check_fields(self):
		# Every field process_stockdata reads must be present and parse
		for d in torn_feed.to_tornsy_format(torn_response(), now=0)["data"]:
			float(d["price"]); float(d["total_shares"]); int(d["investors"])
			float(d["interval"]["m1"]["total_shares"]); int(d["interval"]["m1"]["investors"])


if __name__ == "__main__":
	unittest.main()
