import discord

def set_author(self, message, embed):
	if message.author.avatar:
		embed.set_author(name=message.author.display_name, icon_url=message.author.avatar.url)
	else:
		embed.set_author(name=message.author.display_name)

def set_author_interaction(self, interaction, embed):
	if interaction.user.avatar:
		embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.avatar.url)
	else:
		embed.set_author(name=interaction.user.display_name)

def set_author_notif(self, user, embed):
	if user.avatar:
		embed.set_author(name=user.name, icon_url=user.avatar.url)
	else:
		embed.set_author(name=user.name)