import discord

import tsl_bot.commands.admin as cmd_admin
import tsl_bot.commands.backtest as cmd_backtest
import tsl_bot.commands.bonus as cmd_bonus
import tsl_bot.commands.candle_search as cmd_candle_search
import tsl_bot.commands.credits as cmd_credits
import tsl_bot.commands.forget as cmd_forget
import tsl_bot.commands.overview as cmd_overview
import tsl_bot.commands.paper as cmd_paper
import tsl_bot.commands.portfolio as cmd_portfolio
import tsl_bot.commands.predict as cmd_predict
import tsl_bot.commands.price_alert as cmd_price_alerts
import tsl_bot.commands.stock as cmd_stock

# Known commands with their names

commands = []
slash_cmd = []

# Tuple guide:
# ("command_name", func.here, True if the function is async, False if not, True to show in !help, False to hide)

# Hidden defaults
commands.append(("stop", cmd_admin.cmd_stop, True, False))
commands.append(("force_suggestions", cmd_admin.force_suggestions, False, False))
commands.append(("force_volatility", cmd_admin.force_volatility, False, False))
commands.append(("system_message", cmd_admin.system_message, True, False))
commands.append(("ched", cmd_bonus.ched, True, False, False))
commands.append(("chedded", cmd_bonus.chedded, True, False, False))
commands.append(("notifications", cmd_price_alerts.notifications, True, False))

# Shown Public commands
commands.append(("alerts", cmd_price_alerts.notifications, True, True))
commands.append(("backtest", cmd_backtest.backtest, True, True))
commands.append(("credits", cmd_credits.credits, True, True))
commands.append(("down", cmd_price_alerts.alerts, True, True))
commands.append(("forget", cmd_forget.forget, True, True))
commands.append(("loss", cmd_price_alerts.alerts, True, True))
commands.append(("overview", cmd_overview.overview, True, True))
commands.append(("paper_buy", cmd_paper.buy, True, True))
commands.append(("paper_sell", cmd_paper.sell, True, True))
commands.append(("portfolio", cmd_portfolio.portfolio, True, True))
commands.append(("predict", cmd_predict.predict, True, True))
commands.append(("search", cmd_candle_search.search, True, True))
commands.append(("stock", cmd_stock.stock_cmd, True, True))
commands.append(("up", cmd_price_alerts.alerts, True, True))

undo_int = 0
for item in cmd_price_alerts.undo_list:
	commands.append((item, cmd_price_alerts.undo, True, cmd_price_alerts.undo_help[undo_int]))
	undo_int += 1

# This is a special function that lists all known commands automatically
async def help(self, message, prefix):
	global commands
	registered_cmds = ""
	for cmd in commands:
		if cmd[3]:
			registered_cmds += prefix + cmd[0] + "\n"
	embed = discord.Embed(title="Help:")
	embed.color = discord.Color.purple()
	embed.add_field(name="Known Commands:", value="Run the base command to reveal the commands full arguments.\n\n```" + registered_cmds + "\n```")
	await message.channel.send(embed=embed, mention_author=False, reference=message)

commands.append(("help", help, True, False))

slash_cmd.append("help")