"""Glossary integrity: Discord limits, links between entries, and coverage of commands and patterns."""
import glob
import os
import re
import unittest

import tsl_core.glossary as glossary

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Discord limits, with the margins tsl_gold/commands/glossary.py relies on
MAX_SINGLE_BODY = 1000
MAX_PAGE = 2000
MAX_FIELD = 1024
MAX_EMBED = 6000
MAX_CHOICE_NAME = 100


def _registered_commands():
	"""Slash command names declared in tsl_gold/commands, read from source so Discord isn't needed."""
	names = set()
	for path in glob.glob(os.path.join(ROOT, "tsl_gold", "commands", "*.py")):
		with open(path, encoding="utf-8") as f:
			src = f.read()
		names |= set(re.findall(r'tree\.command\(name="(\w+)"', src))
		names |= set(re.findall(r'app_commands\.Group\(name="(\w+)"', src))
	return names


class GlossaryStructureTests(unittest.TestCase):
	def test_keys_unique_and_lowercase(self):
		keys = [e["key"] for e in glossary.ENTRIES]
		self.assertEqual(len(keys), len(set(keys)), "duplicate glossary keys")
		for k in keys:
			self.assertEqual(k, k.lower())

	def test_entries_well_formed(self):
		for e in glossary.ENTRIES:
			with self.subTest(entry=e["key"]):
				self.assertIn(e["category"], glossary.CATEGORIES)
				self.assertLessEqual(len(e["title"]), MAX_CHOICE_NAME)
				self.assertLessEqual(len(", ".join(e["aliases"])), MAX_FIELD)
				if isinstance(e["body"], list):
					self.assertTrue(e["body"])
					for page in e["body"]:
						self.assertTrue(page.strip())
						self.assertLessEqual(len(page), MAX_PAGE)
				else:
					self.assertLessEqual(len(e["body"]), MAX_SINGLE_BODY)

	def test_related_entries_exist(self):
		for e in glossary.ENTRIES:
			for r in e["related"]:
				self.assertIsNotNone(glossary.get(r), e["key"] + " links to missing entry " + r)

	def test_index_fits_one_embed(self):
		total = 0
		fields = 0
		for category in glossary.CATEGORIES:
			value = "\n".join("• " + e["title"] for e in glossary.ENTRIES if e["category"] == category)
			if value:
				fields += 1
				total += len(category) + 1 + len(value)
				self.assertLessEqual(len(value), MAX_FIELD, category)
		self.assertLessEqual(fields, 25)
		self.assertLess(total + 300, MAX_EMBED)


class GlossarySearchTests(unittest.TestCase):
	def test_every_command_has_an_entry(self):
		admin = glossary.get("admin commands")["aliases"]
		for name in _registered_commands():
			with self.subTest(command=name):
				self.assertTrue(glossary.get("/" + name) or name in admin, "no glossary entry for /" + name)

	def test_spot_searches(self):
		cases = {
			"alert": "/alert", "/al": "/alert", "hammer": "p_hammer", "guide": "guide",
			"floor": "minimum price", "noise": "per-minute noise", "h1": "timeframes",
			"bearish kicking": "p_kicking", "credits": "/credits",
		}
		for query, key in cases.items():
			with self.subTest(query=query):
				hits = glossary.search(query, limit=3)
				self.assertTrue(hits)
				self.assertEqual(hits[0]["key"], key)

	def test_blank_search_lists_in_category_order(self):
		hits = glossary.search("", limit=500)
		order = [glossary.CATEGORIES.index(e["category"]) for e in hits]
		self.assertEqual(order, sorted(order))

	def test_close_spellings_suggested(self):
		self.assertIn("p_hammer", [e["key"] for e in glossary.suggest("hamer")])


try:
	from tsl_core.analysis import search as pattern_search
except ImportError:  # TA-Lib not installed
	pattern_search = None


@unittest.skipIf(pattern_search is None, "TA-Lib is not installed")
class GlossaryPatternCoverageTests(unittest.TestCase):
	def test_every_search_pattern_name_finds_its_entry(self):
		names = [n for _, n in pattern_search.BULLISH_PATTERNS + pattern_search.BEARISH_PATTERNS]
		for _, base, bull, bear in pattern_search.BOTH_PATTERNS:
			names += [base, bull, bear]
		for name in names:
			with self.subTest(pattern=name):
				hits = glossary.search(name, limit=1)
				self.assertTrue(hits and hits[0]["key"].startswith("p_"), name)


if __name__ == "__main__":
	unittest.main()
