import discord
from discord import app_commands

import tsl_core.glossary as glossary
import tsl_config.config as config

client = config.client


async def term_autocomplete(interaction: discord.Interaction, current: str):
	# Same partial-text matching as the ticker fields, over titles and aliases
	return [
		app_commands.Choice(name=e["title"][:100], value=e["key"])
		for e in glossary.search(current, limit=25)
	]


def _entry_embed(entry):
	embed = discord.Embed(title="📖 " + entry["title"], description=entry["body"])
	embed.color = discord.Color.teal()
	if entry["aliases"]:
		embed.add_field(name="Also searchable as:", value=", ".join(entry["aliases"]), inline=False)
	related = [glossary.get(k) for k in entry["related"] if glossary.get(k)]
	if related:
		embed.add_field(name="Related:", value=" · ".join(r["title"] for r in related), inline=False)
	return embed


def _index_embed():
	embed = discord.Embed(title="📖 Glossary", description="Commands, chart signals, candle patterns and more. Start typing in `/glossary term:` to search; partial words work (e.g. `alert`, `boll`, `hammer`, `dip`).")
	embed.color = discord.Color.teal()
	for category in glossary.CATEGORIES:
		titles = [e["title"] for e in glossary.ENTRIES if e["category"] == category]
		if titles:
			embed.add_field(name=category + ":", value="\n".join("• " + t for t in titles), inline=False)
	return embed


@client.tree.command(name="glossary", description="Look up a command or term: /alert, chart signals, candle patterns, Buy the Dip, RSI, and more.")
@app_commands.describe(term="Start typing to search; leave blank to list every term.")
@app_commands.autocomplete(term=term_autocomplete)
async def glossary_cmd(interaction: discord.Interaction, term: str = ""):
	await interaction.response.defer(ephemeral=True)

	if not term.strip():
		embed = _index_embed()
	else:
		# Autocomplete sends the key; typed text without picking a choice is searched
		entry = glossary.get(term)
		matches = [entry] if entry else glossary.search(term, limit=10)
		if len(matches) == 1:
			embed = _entry_embed(matches[0])
		elif matches:
			embed = discord.Embed(title="📖 Several matches for \"" + term[:50] + "\"", description="\n".join("• " + e["title"] for e in matches))
			embed.color = discord.Color.teal()
			embed.set_footer(text="Pick one from the autocomplete list to see it.")
		else:
			close = glossary.suggest(term)
			embed = discord.Embed(title="📖 No entry for \"" + term[:50] + "\"")
			embed.color = discord.Color.orange()
			embed.description = ("Did you mean:\n" + "\n".join("• " + e["title"] for e in close)) if close else "Leave the term blank to list everything."

	client.set_author_interaction(interaction, embed)
	await interaction.followup.send(embed=embed, ephemeral=True)
