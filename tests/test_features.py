"""features.conf parsing. Importing tsl_config creates its DB and key files in the working
directory, so these tests run from a temporary folder."""
import os
import tempfile
import unittest

config = None
_old_cwd = None
_tmp = None


def setUpModule():
	global config, _old_cwd, _tmp
	_old_cwd = os.getcwd()
	_tmp = tempfile.TemporaryDirectory()
	os.chdir(_tmp.name)
	os.mkdir("logs")
	import tsl_config.config as cfg
	config = cfg


def tearDownModule():
	os.chdir(_old_cwd)
	try:
		_tmp.cleanup()
	except OSError:
		pass  # Windows may still hold the SQLite file open


class FeatureSwitchTests(unittest.TestCase):
	def setUp(self):
		if os.path.exists(config.FEATURES_PATH):
			os.remove(config.FEATURES_PATH)
		config.features.clear()
		config.features.update(config.FEATURE_DEFAULTS)

	def _write(self, text):
		with open(config.FEATURES_PATH, "w") as f:
			f.write(text)

	def test_missing_file_is_created_with_defaults(self):
		config.read_features()
		self.assertTrue(os.path.exists(config.FEATURES_PATH))
		self.assertEqual(config.features, config.FEATURE_DEFAULTS)
		self.assertFalse(config.enable_suggestions)
		# The created file reads back to the same values
		config.read_features()
		self.assertEqual(config.features, config.FEATURE_DEFAULTS)

	def test_true_false_words(self):
		self._write("# comment\nsuggestions = YES\nvolatility=on\nbackfill=0\n")
		config.read_features()
		self.assertEqual(config.features, {"suggestions": True, "volatility": True, "backfill": False})
		self.assertTrue(config.enable_suggestions)

	def test_bad_lines_are_ignored(self):
		self._write("bogus=true\nsuggestions\nvolatility=maybe\nbackfill=false\n")
		config.read_features()
		self.assertEqual(config.features, {"suggestions": False, "volatility": False, "backfill": False})


if __name__ == "__main__":
	unittest.main()
