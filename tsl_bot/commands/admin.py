import discord
import tsl_core.functions as tsl_lib
import tsl_config.config as config

client = config.client

from discord_slash import SlashContext
from discord_slash.utils.manage_commands import create_option
from discord_slash.model import SlashCommandOptionType

# async def cmd_stop(self, message, prefix):
# 	if int(message.author.id) in config.bot_admins:
# 		config.write_user_alerts()
# 		tsl_lib.util.stop_run_continously.set()
# 		await self.close()
# 		return
# 	else:
# 		embed = discord.Embed(title=":no_entry_sign: Permission Required :no_entry_sign:")
# 		embed.color = discord.Color.red()
# 		self.set_author(message, embed)
# 		embed.add_field(name="Details:", value="You are not authorised to stop the bot.")
# 		await message.channel.send(embed=embed, mention_author=False, reference=message)


@client.tree.command(name="stop", description="Stops the bot.")
async def cmd_stop(ctx: SlashContext, confirm: str):
    if int(ctx.author_id) in config.bot_admins:
        if confirm == "yes":
            config.write_user_alerts()
            tsl_lib.util.stop_run_continously.set()
            await ctx.send("Bot stopped successfully.")
            await ctx.bot.close()
        else:
            await ctx.send("Command cancelled.")
    else:
        embed = discord.Embed(
            title=":no_entry_sign: Permission Required :no_entry_sign:"
        )
        embed.color = discord.Color.red()
        embed.add_field(
            name="Details:", value="You are not authorised to stop the bot."
        )
        await ctx.send(embed=embed)


# def force_suggestions(self, message, prefix):
# 	if int(message.author.id) in config.bot_admins:
# 		print("Suggestions forced.")
# 		self.process_suggestions()


@client.tree.command(
    name="forcesuggestions",
    description="Forces the bot to process new stock suggestions.",
)
async def force_suggestions(ctx: SlashContext):
    if int(ctx.author_id) in config.bot_admins:
        print("Suggestions forced.")
        ctx.bot.process_suggestions()
        await ctx.send("New stock suggestions have been processed.")
    else:
        embed = discord.Embed(
            title=":no_entry_sign: Permission Required :no_entry_sign:"
        )
        embed.color = discord.Color.red()
        embed.add_field(
            name="Details:", value="You are not authorised to use this command."
        )
        await ctx.send(embed=embed)


# def force_volatility(self, message, prefix):
# 	if int(message.author.id) in config.bot_admins:
# 		print("Volatility forced.")
# 		self.process_volatility()


@client.tree.command(
    name="forcevolatility",
    description="Forces the bot to calculate the volatility of all tracked stocks.",
)
async def force_volatility(ctx: SlashContext):
    if int(ctx.author_id) in config.bot_admins:
        print("Volatility forced.")
        ctx.bot.process_volatility()
        await ctx.send("Volatility of all tracked stocks has been calculated.")
    else:
        embed = discord.Embed(
            title=":no_entry_sign: Permission Required :no_entry_sign:"
        )
        embed.color = discord.Color.red()
        embed.add_field(
            name="Details:", value="You are not authorised to use this command."
        )
        await ctx.send(embed=embed)


# async def system_message(self, message, prefix):
# 	if int(message.author.id) in config.bot_admins:
# 		new_msg = message.content.replace(prefix+"system_message ", "")
# 		for key in range(0, len(config.alert_channels["id"])):
# 			channel = await self.fetch_channel(config.alert_channels["id"][key])
# 			await channel.send(new_msg)


@client.tree.command(
    name="systemmessage", description="Sends a message to all alert channels."
)
async def system_message(ctx: SlashContext, message: str):
    if int(ctx.author_id) in config.bot_admins:
        for channel_id in config.alert_channels["id"]:
            channel = await ctx.bot.fetch_channel(channel_id)
            await channel.send(message)
        await ctx.send("Message sent to all alert channels.")
    else:
        embed = discord.Embed(
            title=":no_entry_sign: Permission Required :no_entry_sign:"
        )
        embed.color = discord.Color.red()
        embed.add_field(
            name="Details:", value="You are not authorised to use this command."
        )
        await ctx.send(embed=embed)


# async def sync_commands(self, message, prefix):
# 	if int(message.author.id) in config.bot_admins:
# 		await config.client.tree.sync()
# 		print("Synced slash command tree to Discord.")


@client.tree.command(
    name="synccommands", description="Syncs the bot's slash commands to Discord."
)
async def sync_commands(ctx: SlashContext):
    if int(ctx.author_id) in config.bot_admins:
        await config.client.tree.sync()
        await ctx.send("Synced slash command tree to Discord.")
    else:
        embed = discord.Embed(
            title=":no_entry_sign: Permission Required :no_entry_sign:"
        )
        embed.color = discord.Color.red()
        embed.add_field(
            name="Details:", value="You are not authorised to use this command."
        )
        await ctx.send(embed=embed)
