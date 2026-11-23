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


class ChannelFileTests(unittest.TestCase):
	def setUp(self):
		for path in ("alert_channels.conf", "suggestion_channels.conf"):
			if os.path.exists(path):
				os.remove(path)
		for table in (config.alert_channels, config.suggestion_channels):
			for column in table.values():
				column.clear()
		config.features.update(config.FEATURE_DEFAULTS)

	def tearDown(self):
		config.features.update(config.FEATURE_DEFAULTS)

	def test_missing_files_are_created_when_features_are_off(self):
		config.read_alerts()
		config.read_suggestions()
		self.assertTrue(os.path.exists("alert_channels.conf"))
		self.assertTrue(os.path.exists("suggestion_channels.conf"))
		self.assertEqual(config.alert_channels["id"], [])
		self.assertEqual(config.suggestion_channels["id"], [])

	def test_empty_file_is_fatal_only_when_its_feature_is_on(self):
		config.features["suggestions"] = True
		with self.assertRaises(Exception):
			config.read_suggestions()
		config.features["volatility"] = True
		with self.assertRaises(Exception):
			config.read_alerts()

	def test_blank_and_malformed_lines_are_skipped(self):
		with open("alert_channels.conf", "w") as f:
			f.write("# comment\n\n1,2,3,4,5\n1,2,3\nabc,2,3,4,5\n 6, 0, 7, 8, 9 \n\n")
		with open("suggestion_channels.conf", "w") as f:
			f.write("# comment\n\n11\nnot_an_id\n12\n\n")
		config.read_alerts()
		config.read_suggestions()
		self.assertEqual(config.alert_channels["id"], [1, 6])
		self.assertEqual(config.alert_channels["tiny"], [2, 0])
		self.assertEqual(config.alert_channels["large"], [5, 9])
		self.assertEqual(config.suggestion_channels["id"], [11, 12])
		# The file's comments are left alone
		with open("suggestion_channels.conf") as f:
			self.assertTrue(f.read().startswith("# comment"))


class LegacyAlertMigrationTests(unittest.TestCase):
	def setUp(self):
		for path in ("userdata.csv", "userdata.csv.migrated"):
			if os.path.exists(path):
				os.remove(path)
		self._clear()

	def tearDown(self):
		self._clear()

	def _clear(self):
		for column in config.userdata.values():
			column.clear()
		config.write_user_alerts()

	def test_csv_is_migrated_once(self):
		with open("userdata.csv", "w") as f:
			f.write("id,type,stock,value\n123,up,iou,1.5\n")
		config.read_user_alerts()
		self.assertEqual(config.userdata["id"], [123])
		self.assertFalse(os.path.exists("userdata.csv"))
		self.assertTrue(os.path.exists("userdata.csv.migrated"))

		# The alert fires and is removed; a restart must not bring it back
		self._clear()
		config.read_user_alerts()
		self.assertEqual(config.userdata["id"], [])

	def test_empty_csv_is_retired(self):
		open("userdata.csv", "w").close()
		config.read_user_alerts()
		self.assertFalse(os.path.exists("userdata.csv"))

	def test_leftover_csv_is_retired_when_sqlite_has_alerts(self):
		config.userdata["id"].append(1)
		config.userdata["type"].append("up")
		config.userdata["stock"].append("iou")
		config.userdata["value"].append(2.0)
		config.write_user_alerts()
		for column in config.userdata.values():
			column.clear()
		with open("userdata.csv", "w") as f:
			f.write("id,type,stock,value\n999,up,iou,1.5\n")
		config.read_user_alerts()
		self.assertEqual(config.userdata["id"], [1])
		self.assertFalse(os.path.exists("userdata.csv"))


if __name__ == "__main__":
	unittest.main()
