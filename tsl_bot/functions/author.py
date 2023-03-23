import discord

def set_author(self, message, embed):
	if message.author.avatar:
		embed.set_author(name=message.author.display_name, icon_url=message.author.avatar.url)
	else:
		embed.set_author(name=message.author.display_name)

def set_author_notif(self, user, embed):
	if user.avatar:
		embed.set_author(name=user.name, icon_url=user.avatar.url)
	else:
		embed.set_author(name=user.name)