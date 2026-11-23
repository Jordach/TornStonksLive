import json
import os
import threading
import discord

import tsl_core.functions as tsl_lib

notstonks_png = "https://cdn.discordapp.com/attachments/315121916199305218/976306803900022814/tornnotstonks.png"
stonks_png = "https://cdn.discordapp.com/attachments/315121916199305218/976306804176863293/tornstonks.png"
bot_token = ""
bot_started = False

api_key_reason = "TornStonks Mark II"

userdata = {"id":[], "type":[], "stock":[], "value":[]}
auto_userdata = {"id":[], "type":[], "stock":[], "timescale":[], "mute":[], "param1":[], "param2":[], "param3":[], "param4":[], "param5":[], "memory":[], "delay":[]}
# Note that params 1-5 are for read/write; memory, delay is during bot operation only.

alert_channels = {"id":[], "small":[], "medium":[], "large":[], "tiny":[]}
suggestion_channels = {"id":[], "role":[]}
bot_admins = []
client = ""

# Live Tornsy feed; starts empty so commands see "no stocks yet" rather than
# crashing if the first fetch fails (the every-minute update fills it in)
json_data = {"data": []}

# Feature switches, read from features.conf by read_features()
FEATURES_PATH = "features.conf"
FEATURE_DEFAULTS = {
	# Scheduled daily/weekly swing suggestion posts (see tsl_core/analysis/swing.py)
	"suggestions": False,
	# Volatility posts to the alert channels
	"volatility": False,
	# Download any missing price history from Tornsy at startup
	"backfill": True,
}
features = dict(FEATURE_DEFAULTS)
enable_suggestions = features["suggestions"]

# Background price history backfill, updated by main.py's backfill thread and shown by
# /backfill. Times are epoch seconds.
backfill_state = {
	"scanning": False,      # checking stored history for gaps (position/total/ticker)
	"running": False,       # a pass is in progress
	"position": 0,          # stock being fetched, 1-based, of "total"
	"total": 0,
	"ticker": None,
	"minutes": 0,           # minutes fetched for that stock so far
	"oldest": None,         # oldest minute fetched for that stock so far
	"stock_started": None,
	"started": None,        # when the current or last pass started
	"finished": None,       # when the last pass finished
	"paused": [],           # stocks waiting on a Tornsy outage
	"retry_at": None,
}

# Where the live feed came from on the last successful update: "tornsy", or "torn" when
# Tornsy was down and main.py fell back to Torn's own API. None until the first update.
live_source = None

# Slash commands arrive as interactions whatever the intents, with the member (and their
# server nickname) included; DMs and channel posts are REST calls. Only guilds is needed.
intents = discord.Intents(guilds=True)

# SQLite implementation
import sqlite3

DB_PATH = "tsl_data.db"

def _get_db_connection():
	"""Return a connection to the shared SQLite database."""
	conn = sqlite3.connect(DB_PATH)
	conn.execute("PRAGMA journal_mode=WAL")
	return conn

def _init_db():
	"""Create tables if they don't already exist."""
	conn = _get_db_connection()
	cur = conn.cursor()
	cur.execute("""
		CREATE TABLE IF NOT EXISTS user_alerts (
			id       INTEGER NOT NULL,
			type     TEXT    NOT NULL,
			stock    TEXT    NOT NULL,
			value    REAL    NOT NULL
		)
	""")
	cur.execute("""
		CREATE TABLE IF NOT EXISTS api_keys (
			discord_id  TEXT NOT NULL,
			encrypted_key TEXT NOT NULL,
			PRIMARY KEY (discord_id, encrypted_key)
		)
	""")
	cur.execute("""
		CREATE TABLE IF NOT EXISTS event_keys (
			key_name       TEXT NOT NULL PRIMARY KEY,
			encrypted_key  TEXT NOT NULL
		)
	""")
	cur.execute("""
		CREATE TABLE IF NOT EXISTS user_keys (
			discord_id     TEXT NOT NULL PRIMARY KEY,
			encrypted_key  TEXT NOT NULL
		)
	""")
	conn.commit()
	conn.close()

# Ensure tables exist on import
_init_db()

# Encryption helpers – Fernet with a persistent key file
ENCRYPTION_KEY_PATH = "encryption.key"
from cryptography.fernet import Fernet

def _load_or_create_fernet():
	"""Load (or generate) a Fernet key and return a Fernet instance."""
	if os.path.exists(ENCRYPTION_KEY_PATH):
		with open(ENCRYPTION_KEY_PATH, "rb") as f:
			key = f.read().strip()
	else:
		key = Fernet.generate_key()
		with open(ENCRYPTION_KEY_PATH, "wb") as f:
			f.write(key)
		tsl_lib.util.write_log(
			"[INFO] Generated new encryption key at " + ENCRYPTION_KEY_PATH,
			tsl_lib.util.current_date(),
		)
	return Fernet(key)

_fernet = _load_or_create_fernet()

def _encrypt(plaintext: str) -> str:
	"""Encrypt a string and return a base-64 token string."""
	return _fernet.encrypt(plaintext.encode("utf-8")).decode("utf-8")

def _decrypt(token: str) -> str:
	"""Decrypt a Fernet token string back to plaintext."""
	return _fernet.decrypt(token.encode("utf-8")).decode("utf-8")

def read_token():
	global bot_token
	with open("settings.conf", "r") as system_config:
		config_lines = system_config.readlines()
		count = 0
		for line in config_lines:
			count += 1
			if count == 1:
				bot_token = line.strip()
				
	if bot_token == "":
		# (Previously opened the file read-only and wrote to it, which raised
		# io.UnsupportedOperation instead of this message.)
		raise Exception("Bot token is missing - put it on the first line of settings.conf")

_TRUE_WORDS = {"true", "yes", "on", "1"}
_FALSE_WORDS = {"false", "no", "off", "0"}

def read_features():
	"""Load feature switches (name=true/false per line) from features.conf, creating it with defaults if missing."""
	global enable_suggestions
	if not os.path.exists(FEATURES_PATH):
		with open(FEATURES_PATH, "w") as file:
			file.write("# TornStonks Live feature switches: name=true or name=false, one per line.\n")
			for name, value in FEATURE_DEFAULTS.items():
				file.write(name + "=" + ("true" if value else "false") + "\n")
		tsl_lib.util.write_log("[INFO] Created " + FEATURES_PATH + " with default feature switches.", tsl_lib.util.current_date())
	else:
		with open(FEATURES_PATH, "r") as file:
			for line in file:
				line = line.strip()
				if line == "" or line.startswith("#"):
					continue
				name, sep, value = line.partition("=")
				name, value = name.strip().lower(), value.strip().lower()
				if not sep or name not in FEATURE_DEFAULTS or value not in _TRUE_WORDS | _FALSE_WORDS:
					tsl_lib.util.write_log("[WARNING] " + FEATURES_PATH + ": ignoring unrecognised line: " + line, tsl_lib.util.current_date())
					continue
				features[name] = value in _TRUE_WORDS
	enable_suggestions = features["suggestions"]
	tsl_lib.util.write_log(
		"[INFO] Features: " + ", ".join(name + "=" + ("on" if on else "off") for name, on in features.items()),
		tsl_lib.util.current_date(),
	)

def _read_id_rows(path, columns, template):
	"""
	Read comma-separated integer IDs, `columns` per line (an int, or a tuple of allowed
	counts), from `path`. A missing file is
	created holding `template` (comment lines). Blank lines and # comments are skipped;
	malformed lines are logged and skipped.
	"""
	if not os.path.exists(path):
		with open(path, "w") as file:
			file.write(template)
		tsl_lib.util.write_log("[INFO] Created " + path + "; add your channel IDs to it.", tsl_lib.util.current_date())
		return []

	allowed = columns if isinstance(columns, tuple) else (columns,)
	rows = []
	with open(path, "r") as file:
		for number, line in enumerate(file, start=1):
			line = line.strip()
			if line == "" or line.startswith("#"):
				continue
			data = [part.strip() for part in line.split(",")]
			try:
				if len(data) not in allowed:
					raise ValueError
				rows.append([int(part) for part in data])
			except ValueError:
				tsl_lib.util.write_log("[WARNING] " + path + " line " + str(number) + " is malformed, skipping it: " + line, tsl_lib.util.current_date())
	return rows

# Call read_features() first: whether an empty file is fatal depends on the feature switches.
def read_suggestions():
	for row in _read_id_rows(
		"suggestion_channels.conf", (1, 2),
		"# One line per channel for the suggestion and volatility posts: channel_id[,role_id]\n"
		"# The role is pinged on volatility posts only; leave it off or use 0 for no ping.\n",
	):
		suggestion_channels["id"].append(row[0])
		suggestion_channels["role"].append(row[1] if len(row) == 2 else 0)

	if len(suggestion_channels["id"]) == 0:
		if features["suggestions"]:
			raise Exception("suggestions=true in features.conf but suggestion_channels.conf has no channel IDs.")
		if features["volatility"]:
			raise Exception("volatility=true in features.conf but suggestion_channels.conf has no channel IDs.")
		tsl_lib.util.write_log("[INFO] No suggestion channels configured.", tsl_lib.util.current_date())

def read_alerts():
	for channel_id, tiny, small, medium, large in _read_id_rows(
		"alert_channels.conf", 5,
		"# One line per channel: channel_id,tiny_role_id,small_role_id,medium_role_id,large_role_id\n"
		"# Use 0 for tiny_role_id to skip trades under $150bn.\n",
	):
		alert_channels["id"].append(channel_id)
		alert_channels["tiny"].append(tiny)
		alert_channels["small"].append(small)
		alert_channels["medium"].append(medium)
		alert_channels["large"].append(large)

	if len(alert_channels["id"]) == 0:
		tsl_lib.util.write_log("[WARNING] No alert channels configured; large trade pings will not be posted.", tsl_lib.util.current_date())

# Read admins.json
def read_admins():
	global bot_admins
	json_path = "admins.json"

	# --- Try the new JSON format first ---
	if os.path.exists(json_path):
		with open(json_path, "r") as f:
			data = json.load(f)
		bot_admins = [int(uid) for uid in data.get("admins", [])]
		if len(bot_admins) == 0:
			raise Exception("admins.json exists but contains no admin IDs.")
		tsl_lib.util.write_log("[INFO] Loaded " + str(len(bot_admins)) + " admin(s) from admins.json", tsl_lib.util.current_date())
		return

	# --- Fall back to legacy admins.conf and migrate ---
	legacy_path = "admins.conf"
	if os.path.exists(legacy_path):
		with open(legacy_path, "r") as admin_config:
			lines = admin_config.readlines()
			for line in lines:
				if line.strip().startswith("#") or line.strip() == "":
					continue
				bot_admins.append(int(line.strip()))

		if len(bot_admins) == 0:
			raise Exception("No admin IDs found in admins.conf – cannot migrate.")

		# Write the new JSON file
		with open(json_path, "w") as f:
			json.dump({"admins": bot_admins}, f, indent=2)
		tsl_lib.util.write_log(
			"[MIGRATION] Migrated " + str(len(bot_admins)) + " admin(s) from admins.conf -> admins.json",
			tsl_lib.util.current_date(),
		)
		return

	# --- Neither file exists ---
	with open(json_path, "w") as f:
		json.dump({"admins": []}, f, indent=2)
	raise Exception("No admin config found – admins.json created. Add admin Discord IDs to it.")

# User alerts
def read_user_alerts():
	global userdata
	conn = _get_db_connection()
	cur = conn.cursor()

	# Check whether the SQLite table already has data
	cur.execute("SELECT COUNT(*) FROM user_alerts")
	count = cur.fetchone()[0]

	if count > 0:
		# Load from SQLite
		cur.execute("SELECT id, type, stock, value FROM user_alerts")
		for row in cur.fetchall():
			userdata["id"].append(int(row[0]))
			userdata["type"].append(str(row[1]))
			userdata["stock"].append(str(row[2]))
			userdata["value"].append(float(row[3]))
		conn.close()
		tsl_lib.util.write_log(
			"[INFO] Loaded " + str(count) + " user alert(s) from SQLite.",
			tsl_lib.util.current_date(),
		)
		# Already migrated on an earlier run; retire any leftover CSV
		if os.path.exists("userdata.csv"):
			_retire_legacy_alerts("userdata.csv")
		return

	conn.close()

	# --- Fall back to legacy userdata.csv and migrate ---
	# The CSV is retired once migrated. An empty alerts table is normal (every alert
	# has fired or been cleared), so reading the CSV again would bring old alerts back.
	legacy_path = "userdata.csv"
	if not os.path.exists(legacy_path):
		tsl_lib.util.write_log("[INFO] No existing user alerts to load.", tsl_lib.util.current_date())
		return

	with open(legacy_path, "r") as file:
		lines = file.readlines()
	# (Renamed only after closing it: Windows can't rename an open file)
	if len(lines) == 0:
		_retire_legacy_alerts(legacy_path)
		tsl_lib.util.write_log("[INFO] No existing user alerts to load.", tsl_lib.util.current_date())
		return

	if lines[0].strip() != "id,type,stock,value":
		# Left in place: an unrecognised file may be something else, so don't retire it
		tsl_lib.util.write_log("[WARNING] userdata.csv is in an incorrect format, skipping loading.", tsl_lib.util.current_date())
		return
	for line in lines[1:]:
		data = line.strip().split(",", 3)
		if len(data) == 4:
			userdata["id"].append(int(data[0]))
			userdata["type"].append(str(data[1]))
			userdata["stock"].append(str(data[2]))
			userdata["value"].append(float(data[3]))
		else:
			tsl_lib.util.write_log("[WARNING] userdata.csv has incorrect data, skipping the malformed line.", tsl_lib.util.current_date())

	# Persist the migrated data into SQLite
	if len(userdata["id"]) > 0:
		write_user_alerts()
		tsl_lib.util.write_log(
			"[MIGRATION] Migrated " + str(len(userdata["id"])) + " user alert(s) from userdata.csv -> SQLite.",
			tsl_lib.util.current_date(),
		)
	_retire_legacy_alerts(legacy_path)

def _retire_legacy_alerts(legacy_path):
	"""Rename userdata.csv so it is never migrated twice."""
	retired_path = legacy_path + ".migrated"
	os.replace(legacy_path, retired_path)
	tsl_lib.util.write_log("[MIGRATION] Renamed " + legacy_path + " to " + retired_path + "; it will not be read again.", tsl_lib.util.current_date())

# userdata is only mutated on the bot's event loop. Saving can happen on a worker
# thread, so callers take a snapshot on the loop first and the worker writes that.
_user_alerts_write_lock = threading.Lock()
_user_alerts_generation = 0
_user_alerts_written_generation = 0

def snapshot_user_alerts():
	"""Copy userdata into a list of rows plus a generation number. Returns None if corrupted."""
	global _user_alerts_generation
	id_len = len(userdata["id"])
	if id_len != len(userdata["type"]) or id_len != len(userdata["stock"]) or id_len != len(userdata["value"]):
		tsl_lib.util.write_log("[FATAL] userdata memory corrupted or invalid, restart bot immediately.", tsl_lib.util.current_date())
		return None
	_user_alerts_generation += 1
	rows = list(zip(userdata["id"], userdata["type"], userdata["stock"], userdata["value"]))
	return (_user_alerts_generation, rows)

def write_user_alerts(snapshot=None):
	global _user_alerts_written_generation
	if snapshot is None:
		snapshot = snapshot_user_alerts()
	if snapshot is None:
		return
	generation, rows = snapshot

	with _user_alerts_write_lock:
		# A newer snapshot has already been saved; writing this one would undo it
		if generation <= _user_alerts_written_generation:
			return
		conn = _get_db_connection()
		cur = conn.cursor()
		# Replace the entire table contents atomically
		cur.execute("DELETE FROM user_alerts")
		cur.executemany("INSERT INTO user_alerts (id, type, stock, value) VALUES (?, ?, ?, ?)", rows)
		conn.commit()
		conn.close()
		_user_alerts_written_generation = generation

def save_user_key(discord_id: str, api_key: str):
	"""Store (or replace) a user's personal Torn API key, encrypted."""
	conn = _get_db_connection()
	cur = conn.cursor()
	cur.execute(
		"INSERT OR REPLACE INTO user_keys (discord_id, encrypted_key) VALUES (?, ?)",
		(discord_id, _encrypt(api_key)),
	)
	conn.commit()
	conn.close()
	tsl_lib.util.write_log(
		"[INFO] Saved personal API key for Discord user " + discord_id,
		tsl_lib.util.current_date(),
	)
 
def get_user_key(discord_id: str):
	"""Retrieve a user's decrypted personal API key, or None if not set."""
	conn = _get_db_connection()
	cur = conn.cursor()
	cur.execute(
		"SELECT encrypted_key FROM user_keys WHERE discord_id = ?",
		(discord_id,),
	)
	row = cur.fetchone()
	conn.close()
	if row is None:
		return None
	try:
		return _decrypt(row[0])
	except Exception:
		tsl_lib.util.write_log(
			"[WARNING] Failed to decrypt personal API key for " + discord_id,
			tsl_lib.util.current_date(),
		)
		return None
 
def get_public_key():
	"""The bot's own public-access Torn API key (api_keys table), decrypted, or None if missing."""
	conn = _get_db_connection()
	cur = conn.cursor()
	cur.execute("SELECT encrypted_key FROM api_keys LIMIT 1")
	row = cur.fetchone()
	conn.close()
	if row is None:
		return None
	try:
		return _decrypt(row[0])
	except Exception:
		tsl_lib.util.write_log("[WARNING] Failed to decrypt the public Torn API key.", tsl_lib.util.current_date())
		return None

def get_event_key():
	"""The bot's "TSL Events" limited-access Torn API key (event_keys table), decrypted, or None if missing."""
	conn = _get_db_connection()
	cur = conn.cursor()
	cur.execute("SELECT encrypted_key FROM event_keys WHERE key_name = ?", (EVENT_KEY_NAME,))
	row = cur.fetchone()
	conn.close()
	if row is None:
		return None
	try:
		return _decrypt(row[0])
	except Exception:
		tsl_lib.util.write_log("[WARNING] Failed to decrypt the events Torn API key.", tsl_lib.util.current_date())
		return None

# The bot's own keys, as opposed to users' /apikey keys. The public key's single row has
# always used this discord_id, and the events key this key_name.
PUBLIC_KEY_OWNER = "_legacy_"
EVENT_KEY_NAME = "event_key"
BOT_KEY_KINDS = ("public", "event")

def set_bot_key(kind: str, api_key: str):
	"""Store (or replace) one of the bot's own Torn API keys, encrypted. kind is "public" or "event"."""
	conn = _get_db_connection()
	cur = conn.cursor()
	if kind == "public":
		# api_keys' primary key includes the key itself, so clear the old row first
		cur.execute("DELETE FROM api_keys")
		cur.execute("INSERT INTO api_keys (discord_id, encrypted_key) VALUES (?, ?)", (PUBLIC_KEY_OWNER, _encrypt(api_key)))
	elif kind == "event":
		cur.execute("INSERT OR REPLACE INTO event_keys (key_name, encrypted_key) VALUES (?, ?)", (EVENT_KEY_NAME, _encrypt(api_key)))
	else:
		conn.close()
		raise ValueError("Unknown bot key kind: " + str(kind))
	conn.commit()
	conn.close()

def remove_bot_key(kind: str) -> bool:
	"""Delete one of the bot's own Torn API keys. Returns True if one was stored."""
	conn = _get_db_connection()
	cur = conn.cursor()
	if kind == "public":
		cur.execute("DELETE FROM api_keys")
	elif kind == "event":
		cur.execute("DELETE FROM event_keys WHERE key_name = ?", (EVENT_KEY_NAME,))
	else:
		conn.close()
		raise ValueError("Unknown bot key kind: " + str(kind))
	deleted = cur.rowcount > 0
	conn.commit()
	conn.close()
	return deleted

def get_bot_key(kind: str):
	"""Decrypted bot key of the given kind, or None."""
	return get_public_key() if kind == "public" else get_event_key()

def get_fallback_key():
	"""Key for the emergency Torn feed: the public key, else the events key. (key, kind) or (None, None)."""
	for kind in BOT_KEY_KINDS:
		key = get_bot_key(kind)
		if key:
			return key, kind
	return None, None

def has_user_key(discord_id: str) -> bool:
	"""Check whether a user has a personal API key stored."""
	conn = _get_db_connection()
	cur = conn.cursor()
	cur.execute(
		"SELECT 1 FROM user_keys WHERE discord_id = ? LIMIT 1",
		(discord_id,),
	)
	exists = cur.fetchone() is not None
	conn.close()
	return exists
 
def remove_user_key(discord_id: str) -> bool:
	"""Remove a user's personal API key. Returns True if a key was deleted."""
	conn = _get_db_connection()
	cur = conn.cursor()
	cur.execute(
		"DELETE FROM user_keys WHERE discord_id = ?",
		(discord_id,),
	)
	deleted = cur.rowcount > 0
	conn.commit()
	conn.close()
	if deleted:
		tsl_lib.util.write_log(
			"[INFO] Removed personal API key for Discord user " + discord_id,
			tsl_lib.util.current_date(),
		)
	return deleted