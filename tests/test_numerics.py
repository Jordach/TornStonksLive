import unittest

from tsl_core.numerics import NumericParseError, parse_float, parse_int


class ParseIntTests(unittest.TestCase):
	def test_plain_and_separators(self):
		self.assertEqual(parse_int("1000000"), 1000000)
		self.assertEqual(parse_int("1,000,000"), 1000000)
		self.assertEqual(parse_int("1_000_000"), 1000000)
		self.assertEqual(parse_int(" $2,500 "), 2500)

	def test_suffixes(self):
		self.assertEqual(parse_int("500k"), 500000)
		self.assertEqual(parse_int("1.5m"), 1500000)
		self.assertEqual(parse_int("2B"), 2000000000)
		self.assertEqual(parse_int("1t"), 10 ** 12)
		self.assertEqual(parse_int(".5k"), 500)

	def test_rejects_fractions_and_garbage(self):
		for bad in ["1.2345k", "1.5", "abc", "5kk", "", "1e6"]:
			with self.assertRaises(NumericParseError, msg=bad):
				parse_int(bad)
		with self.assertRaises(NumericParseError):
			parse_int(None)

	def test_bounds(self):
		self.assertEqual(parse_int("1", minimum=1), 1)
		with self.assertRaises(NumericParseError):
			parse_int("0", minimum=1)
		with self.assertRaises(NumericParseError):
			parse_int("2k", maximum=1000)

	def test_negative(self):
		self.assertEqual(parse_int("-5k"), -5000)


class ParseFloatTests(unittest.TestCase):
	def test_prices(self):
		self.assertAlmostEqual(parse_float("123.45"), 123.45)
		self.assertAlmostEqual(parse_float("1.2k"), 1200.0)
		self.assertAlmostEqual(parse_float("-1.23"), -1.23)

	def test_error_message_is_user_facing(self):
		with self.assertRaises(NumericParseError) as ctx:
			parse_float("lots")
		self.assertIn("lots", str(ctx.exception))


if __name__ == "__main__":
	unittest.main()
