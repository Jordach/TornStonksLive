import json
import os
import discord

import tsl_core.functions as tsl_lib

notstonks_png = "https://cdn.discordapp.com/attachments/315121916199305218/976306803900022814/tornnotstonks.png"
stonks_png = "https://cdn.discordapp.com/attachments/315121916199305218/976306804176863293/tornstonks.png"
bot_token = ""
bot_started = False

userdata = {"id":[], "type":[], "stock":[], "value":[]}
auto_userdata = {"id":[], "type":[], "stock":[], "timescale":[], "mute":[], "param1":[], "param2":[], "param3":[], "param4":[], "param5":[], "memory":[], "delay":[]}
# Note that params 1-5 are for read/write; memory, delay is during bot operation only.

alert_channels = {"id":[], "small":[], "medium":[], "large":[], "tiny":[]}
command_channels = {"id":[], "prefix":[], "predict":[]}
suggestion_channels = {"id":[]}
bot_admins = []

best_gain = ""
best_loss = ""
best_rand = ""
rand_not_more = False
last_pred_id = []
json_data = ""

enable_suggestions = False

intents = discord.Intents(messages=True, guilds=True, reactions=True, dm_messages=True, dm_reactions=True, members=True)
# Add this line to intents with discord.py >= 2.0
#message_content=True

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

# Read admins out
def read_admins():
	global bot_admins
	with open("admins.conf", "r") as admin_config:
		lines = admin_config.readlines()
		for line in lines:
			# Handle comments
			if line.strip().startswith("#"):
				continue

			bot_admins.append(int(line.strip()))

	if len(bot_admins) == 0:
		with open("admins.conf", "w") as file:
			file.write("")
		raise Exception("No admin config file to control admin features - admins.conf created.")

# User alerts
def read_user_alerts():
	global userdata
	with open("userdata.csv", "r") as file:
		lines = file.readlines()
		ln = 1
		global userdata
		for line in lines:
			if ln == 1:
				# Ignore malformed files entirely (even though they'd probably work otherwise)
				if line.strip() != "id,type,stock,value":
					tsl_lib.util.write_log("[WARNING] userdata.csv is in an incorrect format, skipping loading.", tsl_lib.util.current_date())
					return
				ln+=1
			else:
				data = line.strip().split(",",3)
				if len(data) == 4:
					userdata["id"].append(int(data[0]))
					userdata["type"].append((str(data[1])))
					userdata["stock"].append(str(data[2]))
					userdata["value"].append(float(data[3]))
				else:
					tsl_lib.util.write_log("[WARNING] userdata has incorrect data, skipping the malformed line.", tsl_lib.util.current_date())

def write_user_alerts():
	global userdata
	id = len(userdata["id"])
	ty = len(userdata["type"])
	st = len(userdata["stock"])
	vl = len(userdata["value"])
	
	if id == ty and id == st and id == vl:
		with open("userdata.csv", "w") as file:
			out = "id,type,stock,value\n"
			for item in range(0, len(userdata["id"])):
				out = out + str(userdata["id"][item]) + ","
				out = out + str(userdata["type"][item]) + ","
				out = out + str(userdata["stock"][item]) + "," 
				out = out + str(userdata["value"][item])
				if item != len(userdata["id"]) - 1:
					out = out + "\n"
			file.write(out)
	else:
		tsl_lib.util.write_log("[FATAL] userdata memory corrupted or invalid, restart bot immediately.", tsl_lib.util.current_date())

def read_suggest_json():
	global best_gain
	global best_loss
	global best_rand
	if os.path.exists("best_gain.json"):
		with open("best_gain.json") as file:
			best_gain = json.load(file)
	else:
		tsl_lib.util.write_log("[WARNING] best_gain.json not found - ignoring", tsl_lib.util.current_date())

	if os.path.exists("best_loss.json"):
		with open("best_loss.json") as file:
			best_loss = json.load(file)
	else:
		tsl_lib.util.write_log("[WARNING] best_loss.json not found - ignoring", tsl_lib.util.current_date())

	if os.path.exists("best_rand.json"):
		with open("best_rand.json") as file:
			best_rand = json.load(file)
	else:
		tsl_lib.util.write_log("[WARNING] best_rand.json not found - ignoring", tsl_lib.util.current_date())