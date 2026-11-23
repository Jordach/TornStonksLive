"""features.conf parsing. Importing tsl_config creates its DB and key files in the working
directory, so these tests run from a temporary folder."""
import os
import tempfile
import types
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
		config.features["suggestions"] = False
		config.features["volatility"] = True
		with self.assertRaises(Exception):
			config.read_suggestions()
		# Alert channels are never required
		config.read_alerts()

	def test_blank_and_malformed_lines_are_skipped(self):
		with open("alert_channels.conf", "w") as f:
			f.write("# comment\n\n1,2,3,4,5\n1,2,3\nabc,2,3,4,5\n 6, 0, 7, 8, 9 \n\n")
		with open("suggestion_channels.conf", "w") as f:
			f.write("# comment\n\n11\nnot_an_id\n12, 99\n13,0\n1,2,3\n\n")
		config.read_alerts()
		config.read_suggestions()
		self.assertEqual(config.alert_channels["id"], [1, 6])
		self.assertEqual(config.alert_channels["tiny"], [2, 0])
		self.assertEqual(config.alert_channels["large"], [5, 9])
		self.assertEqual(config.suggestion_channels["id"], [11, 12, 13])
		self.assertEqual(config.suggestion_channels["role"], [0, 99, 0])
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


def _interaction(channel_id, guild_id=1, parent_id=None):
	channel = types.SimpleNamespace(id=channel_id)
	if parent_id is not None:
		channel.parent_id = parent_id
	return types.SimpleNamespace(guild_id=guild_id, channel_id=channel_id, channel=channel)


class ReadCommandChannelsTests(unittest.TestCase):
	path = "command_channels_test.conf"

	def tearDown(self):
		if os.path.exists(self.path):
			os.remove(self.path)
		config.command_channels.clear()

	def _read(self, text):
		with open(self.path, "w") as f:
			f.write(text)
		config.read_command_channels(self.path)
		return list(config.command_channels)

	def test_plain_and_legacy_lines(self):
		self.assertEqual(self._read("# TSL\n1088569857437601895,!,channel\n\n123\n"), [1088569857437601895, 123])

	def test_malformed_lines_skipped(self):
		self.assertEqual(self._read("abc\n456, x\n"), [456])

	def test_rereading_replaces(self):
		self._read("1\n")
		self.assertEqual(self._read("2\n"), [2])

	def test_missing_file_created_empty(self):
		config.read_command_channels(self.path)
		self.assertEqual(config.command_channels, [])
		self.assertTrue(os.path.exists(self.path))
		with open(self.path) as f:
			self.assertTrue(all(line.startswith("#") for line in f if line.strip()))


class PrivateReplyTests(unittest.TestCase):
	def setUp(self):
		config.command_channels[:] = [100, 200]

	def tearDown(self):
		config.command_channels.clear()

	def test_command_channel_is_public(self):
		self.assertFalse(config.private_reply(_interaction(100)))

	def test_other_channel_is_private(self):
		self.assertTrue(config.private_reply(_interaction(300)))

	def test_thread_follows_its_parent(self):
		self.assertFalse(config.private_reply(_interaction(999, parent_id=200)))
		self.assertTrue(config.private_reply(_interaction(999, parent_id=300)))

	def _dm(self, discord_context):
		import discord
		interaction = _interaction(300, guild_id=None)
		interaction.context = discord.app_commands.AppCommandContext._from_value([discord_context])
		return interaction

	def test_bot_dm_counts_as_command_channel(self):
		# Discord's interaction context 1 is BOT_DM
		self.assertFalse(config.private_reply(self._dm(1)))
		self.assertFalse(config.private_reply(_interaction(300, guild_id=None)))  # no context sent

	def test_bot_dm_without_context_field(self):
		import discord
		interaction = _interaction(300, guild_id=None)
		interaction.context = discord.app_commands.AppCommandContext()
		self.assertFalse(config.private_reply(interaction))

	def test_group_dm_is_private(self):
		# Context 2 is PRIVATE_CHANNEL: group DMs and DMs between users, seen by others
		self.assertTrue(config.private_reply(self._dm(2)))

	def test_no_channels_configured_means_no_restriction(self):
		config.command_channels.clear()
		self.assertFalse(config.private_reply(_interaction(300)))


if __name__ == "__main__":
	unittest.main()
