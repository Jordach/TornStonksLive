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


# Discord allows 10 embeds and 6000 characters per message; stay a little under
MAX_EMBEDS_PER_MESSAGE = 10
MAX_CHARS_PER_MESSAGE = 5500


def _entry_embeds(entry):
	"""One embed per page; a plain string body is a single page."""
	pages = entry["body"] if isinstance(entry["body"], list) else [entry["body"]]
	embeds = []
	for n, page in enumerate(pages, 1):
		title = "📖 " + entry["title"]
		if len(pages) > 1:
			title += " (" + str(n) + "/" + str(len(pages)) + ")"
		embed = discord.Embed(title=title, description=page)
		embed.color = discord.Color.teal()
		embeds.append(embed)
	# Search words and related entries go at the end, after the last page
	last = embeds[-1]
	if entry["aliases"]:
		last.add_field(name="Also searchable as:", value=", ".join(entry["aliases"]), inline=False)
	related = [glossary.get(k) for k in entry["related"] if glossary.get(k)]
	if related:
		last.add_field(name="Related:", value=" · ".join(r["title"] for r in related), inline=False)
	return embeds


def _batches(embeds):
	"""Group embeds into messages that fit Discord's per-message limits."""
	batches, current, size = [], [], 0
	for embed in embeds:
		n = len(embed)
		if current and (len(current) >= MAX_EMBEDS_PER_MESSAGE or size + n > MAX_CHARS_PER_MESSAGE):
			batches.append(current)
			current, size = [], 0
		current.append(embed)
		size += n
	if current:
		batches.append(current)
	return batches


def _index_embed():
	embed = discord.Embed(title="📖 Glossary", description="New to trading? Start with **New trader's guide: start here**.\n\nCommands, chart signals, candle patterns and more. Start typing in `/glossary term:` to search; partial words work (e.g. `alert`, `boll`, `hammer`, `dip`).")
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

	embeds = None
	if not term.strip():
		embed = _index_embed()
	else:
		# Autocomplete sends the key; typed text without picking a choice is searched
		entry = glossary.get(term)
		matches = [entry] if entry else glossary.search(term, limit=10)
		if len(matches) == 1:
			embeds = _entry_embeds(matches[0])
			embed = embeds[0]
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
	# Long guide entries continue over several messages, each within Discord's limits
	for batch in _batches(embeds or [embed]):
		await interaction.followup.send(embeds=batch, ephemeral=True)
