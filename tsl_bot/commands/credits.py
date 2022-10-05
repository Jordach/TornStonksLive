import discord

async def credits(self, message, prefix):
	thanks_str = ""
	with open("thanks.md", "r") as thanks:
		lines = thanks.readlines()
		for line in lines:
			thanks_str = thanks_str + line

	thanks_str = thanks_str + "\n\nThank you truly, for using TornStonks Live! :thumbsup:"

	embed = discord.Embed(title="")
	embed.color = discord.Color.purple()
	self.set_author(message, embed)
	embed.add_field(name="Many Thanks To:", value=thanks_str)

	await message.channel.send(embed=embed, mention_author=False, reference=message)