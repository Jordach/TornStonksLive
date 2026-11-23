import unittest

import tsl_core.benefits as benefits

ITEMS = {
	"206": {"name": "Xanax", "market_value": 850000},
	"530": {"name": "Can of Munster", "market_value": 1400000},
	"180": {"name": "Bottle of Beer", "market_value": 900},
	"366": {"name": "Erotic DVD", "market_value": 3850000},
	"370": {"name": "Drug Pack", "market_value": 4400000},
	"368": {"name": "Lawyer's Business Card", "market_value": 270000},
	"1057": {"name": "Gentleman Cache", "market_value": 4000000},
	"1115": {"name": "Denim Cache", "market_value": 800000},
	"999": {"name": "Collectible Cache", "market_value": 0},
}


class BlockMathTests(unittest.TestCase):
	def test_blocks_double(self):
		self.assertEqual(benefits.shares_for_block(100, 1), 100)
		self.assertEqual(benefits.shares_for_block(100, 3), 400)
		self.assertEqual(benefits.shares_for_blocks(100, 1), 100)
		self.assertEqual(benefits.shares_for_blocks(100, 3), 700)
		self.assertEqual(
			benefits.shares_for_blocks(350000, 5),
			sum(benefits.shares_for_block(350000, b) for b in range(1, 6)),
		)

	def test_payouts_are_whole(self):
		self.assertEqual(benefits.payouts_in(365, 7), 52)
		self.assertEqual(benefits.payouts_in(365, 31), 11)
		self.assertEqual(benefits.payouts_in(6, 7), 0)


class ParseRewardTests(unittest.TestCase):
	def test_kinds(self):
		self.assertEqual(benefits.parse_reward("$50,000,000"), {"kind": "cash", "amount": 50000000})
		self.assertEqual(benefits.parse_reward("1x Drug Pack"), {"kind": "item", "amount": 1, "name": "Drug Pack"})
		self.assertEqual(benefits.parse_reward("100 energy"), {"kind": "stat", "amount": 100, "name": "energy"})
		self.assertEqual(benefits.parse_reward("1000 happiness"), {"kind": "stat", "amount": 1000, "name": "happiness"})
		self.assertEqual(benefits.parse_reward("100 points"), {"kind": "points", "amount": 100})
		self.assertEqual(benefits.parse_reward("a 10% bank interest bonus")["kind"], "other")


class ValueRewardTests(unittest.TestCase):
	def test_cash_and_items(self):
		self.assertEqual(benefits.value_reward(benefits.parse_reward("$4,000,000"), ITEMS, None)[0], 4000000)
		self.assertEqual(benefits.value_reward(benefits.parse_reward("1x Drug Pack"), ITEMS, None)[0], 4400000)

	def test_item_name_drift(self):
		self.assertEqual(benefits.value_reward(benefits.parse_reward("1x Lawyers Business Card"), ITEMS, None)[0], 270000)

	def test_clothing_cache_is_average(self):
		self.assertEqual(benefits.value_reward(benefits.parse_reward("1x Clothing Cache"), ITEMS, None)[0], 2400000)

	def test_unpriced_item(self):
		value, basis, _ = benefits.value_reward(benefits.parse_reward("1x Random Property"), ITEMS, None)
		self.assertIsNone(value)
		self.assertIn("Random Property", basis)

	def test_happiness_ignores_cheaper_candy(self):
		items = dict(ITEMS, c={"name": "Box of Chocolate Bars", "market_value": 880})
		value, basis, refs = benefits.value_reward(benefits.parse_reward("1000 happiness"), items, None)
		self.assertAlmostEqual(value, 3850000 * 0.4)
		self.assertIn("Erotic DVD", basis)
		self.assertEqual(refs[0][0], "Box of Chocolate Bars")  # listed cheapest first

	def test_energy_valued_by_xanax(self):
		value, basis, refs = benefits.value_reward(benefits.parse_reward("100 energy"), ITEMS, 33333)
		# Xanax: 850,000 / 250 per energy; Munster 70,000; refill 33,333 * 25 / 150 = 5,555.5
		self.assertAlmostEqual(value, 340000)
		self.assertIn("Xanax", basis)
		self.assertEqual([r[0] for r in refs][0], "Xanax")
		self.assertEqual(len(refs), 3)
		self.assertAlmostEqual(refs[0][2], 0.4)

	def test_points(self):
		value, _, refs = benefits.value_reward(benefits.parse_reward("100 points"), ITEMS, 33333)
		self.assertEqual(value, 3333300)
		self.assertTrue(refs)

	def test_points_market_down(self):
		self.assertIsNone(benefits.value_reward(benefits.parse_reward("100 points"), ITEMS, None)[0])

	def test_passive(self):
		self.assertIsNone(benefits.value_reward(benefits.parse_reward("Private jet access"), ITEMS, None)[0])


class RoiTests(unittest.TestCase):
	def test_roi_rows(self):
		rows = benefits.roi(cost=1000000, payout_value=10000, blocks=2, frequency=7)
		self.assertEqual([r[0] for r in rows], [1, 3, 5, 10])
		years, payouts, earned, pct = rows[0]
		self.assertEqual(payouts, 52)
		self.assertEqual(earned, 52 * 2 * 10000)
		self.assertAlmostEqual(pct, 104.0)

	def test_break_even(self):
		# 1,000,000 / 20,000 per payout = 50 payouts of 7 days
		self.assertEqual(benefits.break_even_days(1000000, 10000, 2, 7), 350)
		self.assertIsNone(benefits.break_even_days(1000000, 0, 1, 7))

	def test_breakdown_halves_return(self):
		rows = benefits.block_breakdown(100, 3, 10.0, 1000, 31)
		self.assertEqual([r[1] for r in rows], [100, 200, 400])
		self.assertAlmostEqual(rows[0][3], rows[1][3] * 2)


if __name__ == "__main__":
	unittest.main()
