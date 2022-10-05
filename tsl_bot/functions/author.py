import discord

def set_author(self, message, embed):
	if message.author.avatar:
		embed.set_author(name=message.author.display_name, icon_url="https://cdn.discordapp.com/avatars/"+str(message.author.id)+"/"+str(message.author.avatar)+".png")
	else:
		embed.set_author(name=message.author.display_name)

def set_author_notif(self, user, embed):
	if user.avatar:
		embed.set_author(name=user.name, icon_url="https://cdn.discordapp.com/avatars/"+str(user.id)+"/"+user.avatar+".png")
	else:
		embed.set_author(name=user.name)