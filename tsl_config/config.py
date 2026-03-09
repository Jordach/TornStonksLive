import json
import os
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
command_channels = {"id":[], "prefix":[], "predict":[]}
suggestion_channels = {"id":[]}
bot_admins = []
verification_keys = []
event_key = ""
client = ""

best_gain = ""
best_loss = ""
best_rand = ""
rand_not_more = False
last_pred_id = []
json_data = ""

gold_daily = ""
gold_weekly = ""
gold_monthly = ""

enable_suggestions = False

intents = discord.Intents(messages=True, guilds=True, reactions=True, dm_messages=True, dm_reactions=True, members=True, message_content=True)

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
		with open("settings.conf") as file:
			file.write("")
			raise Exception("Bot token is missing")

# DEPRECATED NOTICE:
# Will be replaced by slash commands soon
def read_channels():
	global command_channels
	with open("command_channels.conf", "r") as channel_config:
		lines = channel_config.readlines()
		for line in lines:
			# Handle comments 
			if line.strip().startswith("#"):
				continue

			data = line.strip().split(",")
			if len(data) == 3:
				command_channels["id"].append(int(data[0]))
				command_channels["prefix"].append(str(data[1]))
				command_channels["predict"].append(str(data[2]))
			else:
				tsl_lib.util.write_log("[WARNING] command_channels.conf has incorrect data, skipping the malformed line.", tsl_lib.util.current_date())

	if len(command_channels["id"]) == 0:
		with open("command_channels.conf", "w") as file:
			file.write("")
		raise Exception("No channels to send/receive commands to - command_channels.conf created.")

# DEPRECATED NOTICE:
# Will be converted to a singular Discord server and channel only for easier customised installation
# Automated suggestions:
def read_suggestions():
	global suggestion_channels
	with open("suggestion_channels.conf", "r") as suggest_config:
		lines = suggest_config.readlines()
		for line in lines:
			# Handle comments
			if line.strip().startswith("#"):
				continue

			data = line.strip().split(",")
			if len(data) == 1:
				suggestion_channels["id"].append(int(data[0]))
			else:
				tsl_lib.util.write_log("[WARNING] suggestion_channels.conf has incorrect data, skipping the malformed line.", tsl_lib.util.current_date())

	if len(suggestion_channels["id"]) == 0:
		with open("suggestion_channels.conf", "w") as file:
			file.write("")
		raise Exception("No channels to send automated analysis to - suggestion_channels.conf created.")

# DEPRECATED NOTICE:
# Will be converted to a singular Discord server and channel only for easier customised installation
# Alerts and notifications
def read_alerts():
	global alert_channels
	with open("alert_channels.conf", "r") as alert_config:
		lines = alert_config.readlines()
		for line in lines:
			# Handle comments
			if line.strip().startswith("#"):
				continue

			data = line.strip().split(",")
			if len(data) == 5:
				alert_channels["id"].append(int(data[0]))
				alert_channels["tiny"].append(int(data[1]))
				alert_channels["small"].append(int(data[2]))
				alert_channels["medium"].append(int(data[3]))
				alert_channels["large"].append(int(data[4]))
			else:
				tsl_lib.util.write_log("[WARNING] alert_channels.conf has incorrect data, skipping the malformed line.", tsl_lib.util.current_date())

	if len(alert_channels["id"]) == 0:
		with open("alert_channels.conf", "w") as file:
			file.write("")
		raise Exception("No channels to send automated notifications to - alert_channels.conf created.")

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
		return

	conn.close()

	# --- Fall back to legacy userdata.csv and migrate ---
	legacy_path = "userdata.csv"
	if not os.path.exists(legacy_path):
		tsl_lib.util.write_log("[INFO] No existing user alerts to load.", tsl_lib.util.current_date())
		return

	with open(legacy_path, "r") as file:
		lines = file.readlines()
		ln = 1
		for line in lines:
			if ln == 1:
				if line.strip() != "id,type,stock,value":
					tsl_lib.util.write_log("[WARNING] userdata.csv is in an incorrect format, skipping loading.", tsl_lib.util.current_date())
					return
				ln += 1
			else:
				data = line.strip().split(",", 3)
				if len(data) == 4:
					userdata["id"].append(int(data[0]))
					userdata["type"].append(str(data[1]))
					userdata["stock"].append(str(data[2]))
					userdata["value"].append(float(data[3]))
				else:
					tsl_lib.util.write_log("[WARNING] userdata.csv has incorrect data, skipping the malformed line.", tsl_lib.util.current_date())
				ln += 1

	# Persist the migrated data into SQLite
	if len(userdata["id"]) > 0:
		write_user_alerts()
		tsl_lib.util.write_log(
			"[MIGRATION] Migrated " + str(len(userdata["id"])) + " user alert(s) from userdata.csv -> SQLite.",
			tsl_lib.util.current_date(),
		)

def write_user_alerts():
	global userdata
	id_len = len(userdata["id"])
	ty_len = len(userdata["type"])
	st_len = len(userdata["stock"])
	vl_len = len(userdata["value"])

	if id_len != ty_len or id_len != st_len or id_len != vl_len:
		tsl_lib.util.write_log("[FATAL] userdata memory corrupted or invalid, restart bot immediately.", tsl_lib.util.current_date())
		return

	conn = _get_db_connection()
	cur = conn.cursor()
	# Replace the entire table contents atomically
	cur.execute("DELETE FROM user_alerts")
	for i in range(id_len):
		cur.execute(
			"INSERT INTO user_alerts (id, type, stock, value) VALUES (?, ?, ?, ?)",
			(userdata["id"][i], userdata["type"][i], userdata["stock"][i], userdata["value"][i]),
		)
	conn.commit()
	conn.close()

# Migrates from verify_api_keys.conf and event_key.conf on first run.
# Schema supports (discord_id, encrypted_key) pairs for future per-user storage.
# Legacy keys are stored under discord_id = "_legacy_" until associated with a user.
def read_torn_api_keys():
	global verification_keys
	global event_key
	conn = _get_db_connection()
	cur = conn.cursor()

	# --- Try loading from SQLite first ---
	cur.execute("SELECT encrypted_key FROM api_keys")
	rows = cur.fetchall()

	cur.execute("SELECT encrypted_key FROM event_keys WHERE key_name = ?", ("event_key",))
	ev_row = cur.fetchone()

	if len(rows) > 0 or ev_row is not None:
		# Decrypt verification keys
		for row in rows:
			try:
				verification_keys.append(_decrypt(row[0]))
			except Exception:
				tsl_lib.util.write_log("[WARNING] Failed to decrypt an API key – skipping.", tsl_lib.util.current_date())

		# Decrypt event key
		if ev_row is not None:
			try:
				event_key = _decrypt(ev_row[0])
			except Exception:
				tsl_lib.util.write_log("[WARNING] Failed to decrypt event key.", tsl_lib.util.current_date())

		conn.close()

		if len(verification_keys) == 0:
			raise Exception("API keys table exists in SQLite but all keys failed to decrypt.")
		if event_key == "":
			raise Exception("Event key failed to decrypt or is missing from SQLite.")

		tsl_lib.util.write_log(
			"[INFO] Loaded " + str(len(verification_keys)) + " API key(s) + event key from SQLite (encrypted).",
			tsl_lib.util.current_date(),
		)
		return

	conn.close()

	# --- Fall back to legacy .conf files and migrate ---
	# Verification keys
	legacy_keys_path = "verify_api_keys.conf"
	if os.path.exists(legacy_keys_path):
		with open(legacy_keys_path, "r") as verify_file:
			lines = verify_file.readlines()
			for line in lines:
				if line.strip().startswith("#") or line.strip() == "":
					continue
				verification_keys.append(line.strip())
	else:
		with open(legacy_keys_path, "w") as file:
			file.write("# Torn API keys go in here.")
		raise Exception("No API keys file for verifying users for TornStonks Gold module was found - verify_api_keys.conf created.")

	if len(verification_keys) == 0:
		raise Exception("verify_api_keys.conf contains no API keys.")

	# Event key
	legacy_event_path = "event_key.conf"
	if os.path.exists(legacy_event_path):
		with open(legacy_event_path, "r") as event_lines:
			lines = event_lines.readlines()
			for line in lines:
				if line.strip().startswith("#") or line.strip() == "":
					continue
				else:
					event_key = line.strip()
					break
		if event_key == "":
			raise Exception("API key missing in event_key.conf.")
	else:
		with open(legacy_event_path, "w") as file:
			file.write("# Limited access or full access API key goes here.")
		raise Exception("No API key file was found for verifying payment for TornStonks Gold module was found - event_key.conf created.")

	# --- Migrate everything into SQLite (encrypted) ---
	conn = _get_db_connection()
	cur = conn.cursor()
	for key in verification_keys:
		cur.execute(
			"INSERT OR IGNORE INTO api_keys (discord_id, encrypted_key) VALUES (?, ?)",
			("_legacy_", _encrypt(key)),
		)
	cur.execute(
		"INSERT OR REPLACE INTO event_keys (key_name, encrypted_key) VALUES (?, ?)",
		("event_key", _encrypt(event_key)),
	)
	conn.commit()
	conn.close()
	tsl_lib.util.write_log(
		"[MIGRATION] Migrated " + str(len(verification_keys)) + " API key(s) + event key from .conf -> SQLite (encrypted).",
		tsl_lib.util.current_date(),
	)