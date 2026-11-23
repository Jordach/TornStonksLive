"""
Stock benefit block maths and valuation, used by /benefit.

Works from Torn API data, so new stocks or changed rewards need no code change:
	stocks  - torn/?selections=stocks, each with benefit {type, frequency, requirement, description}
	items   - torn/?selections=items, {id: {name, market_value, ...}}
	points  - the cheapest points market price per point (market/?selections=pointsmarket)

Benefit blocks double: block 1 needs the stock's requirement in shares, block 2
twice that again, block n requirement * 2^(n-1). Holding n blocks therefore takes
requirement * (2^n - 1) shares and pays the reward n times per period. Passive
benefits don't stack, so only the first block counts.
"""
import math
import re

ROI_YEARS = (1, 3, 5, 10)
DAYS_PER_YEAR = 365
MAX_BLOCKS = 20

# Torn's points refill restores a full energy bar (150 with donator status) for 25 points
REFILL_POINTS = 25
REFILL_ENERGY = 150

# Rewards with no single market item behind them
# Clothing Cache: TCC hands out one of these at random, so it's valued at their average
CLOTHING_CACHES = (
	"Gentleman Cache", "Elegant Cache", "Naughty Cache", "Elderly Cache",
	"Denim Cache", "Wannabe Cache", "Cutesy Cache",
)

# What intangible rewards are compared against: (item name, amount the item gives,
# Cannabis's 8-12 nerve taken as 10). The first item of each is the yardstick the
# reward is valued by: the usual way to buy that stat in bulk. Cheap candy and
# alcohol are limited by booster cooldown, so they'd undervalue the reward; they're
# still listed for comparison.
STAT_REFERENCES = {
	"energy": (("Xanax", 250), ("Can of Munster", 20), ("Can of Taurine Elite", 30)),
	"nerve": (("Cannabis", 10), ("Bottle of Beer", 1), ("Bottle of Moonshine", 5)),
	"happiness": (("Erotic DVD", 2500), ("Box of Chocolate Bars", 25), ("Pixie Sticks", 150)),
}


def shares_for_block(requirement, block):
	"""Shares the given block (1-based) adds on top of the blocks before it."""
	return requirement * 2 ** (block - 1)


def shares_for_blocks(requirement, blocks):
	"""Total shares needed to hold `blocks` benefit blocks."""
	return requirement * (2 ** blocks - 1)


def parse_reward(description):
	"""
	Read a Torn benefit description into what it pays.
	Returns a dict with kind = cash | item | stat | points | other, plus amount and
	(for item/stat) name.
	"""
	text = description.strip()
	m = re.fullmatch(r"\$([\d,]+)", text)
	if m:
		return {"kind": "cash", "amount": int(m.group(1).replace(",", ""))}
	m = re.fullmatch(r"(\d+)x (.+)", text)
	if m:
		return {"kind": "item", "amount": int(m.group(1)), "name": m.group(2).strip()}
	m = re.fullmatch(r"([\d,]+) (energy|nerve|happiness|happy)", text, re.IGNORECASE)
	if m:
		stat = m.group(2).lower()
		return {"kind": "stat", "amount": int(m.group(1).replace(",", "")), "name": "happiness" if stat == "happy" else stat}
	m = re.fullmatch(r"([\d,]+) points?", text, re.IGNORECASE)
	if m:
		return {"kind": "points", "amount": int(m.group(1).replace(",", ""))}
	return {"kind": "other", "amount": 0}


def _item_prices(items):
	"""Map lower-cased item name -> market value, skipping items with no market price."""
	prices = {}
	for item in items.values():
		value = item.get("market_value") or 0
		if value > 0:
			prices[item["name"].lower()] = value
	return prices


def _item_value(name, prices):
	"""Market value of one of the named item, or None when it has no market price."""
	key = name.lower()
	if key == "clothing cache":
		values = [prices[c.lower()] for c in CLOTHING_CACHES if c.lower() in prices]
		return sum(values) / len(values) if values else None
	if key in prices:
		return prices[key]
	# Torn's wording drifts slightly between the stock page and the item list
	# (hyphens, apostrophes), so fall back to comparing letters only
	squash = lambda s: re.sub(r"[^a-z0-9]", "", s)
	target = squash(key)
	for item_name, value in prices.items():
		if squash(item_name) == target:
			return value
	return None


def stat_references(stat, amount, prices, point_price):
	"""
	What `amount` of a stat costs bought another way. Returns a list of
	(label, value of the whole amount, how many of that item it equals), cheapest first.
	"""
	refs = []
	for name, gives in STAT_REFERENCES.get(stat, ()):
		value = _item_value(name, prices)
		if value:
			refs.append((name, value / gives * amount, amount / gives))
	if stat == "energy" and point_price:
		per_energy = point_price * REFILL_POINTS / REFILL_ENERGY
		refs.append(("Energy refill (" + str(REFILL_POINTS) + " points)", per_energy * amount, amount / REFILL_ENERGY))
	refs.sort(key=lambda r: r[1])
	return refs


def value_reward(reward, items, point_price):
	"""
	Cash value of one payout, plus how it was valued.
	Returns (value or None, basis text, references) where references is the
	stat_references list for intangible rewards (else empty).
	"""
	prices = _item_prices(items)
	kind = reward["kind"]
	if kind == "cash":
		return reward["amount"], "cash", []
	if kind == "item":
		each = _item_value(reward["name"], prices)
		if each is None:
			return None, "no market price for " + reward["name"], []
		basis = "average of the clothing caches' market values" if reward["name"].lower() == "clothing cache" else "market value"
		return each * reward["amount"], basis, []
	if kind == "points":
		if not point_price:
			return None, "points market unavailable", []
		refs = []
		energy = reward["amount"] / REFILL_POINTS * REFILL_ENERGY
		for label, value, count in stat_references("energy", energy, prices, None):
			refs.append((label, value, count))
		return point_price * reward["amount"], "cheapest points market listing", refs
	if kind == "stat":
		refs = stat_references(reward["name"], reward["amount"], prices, point_price)
		if not refs:
			return None, "no reference prices for " + reward["name"], []
		yardstick = STAT_REFERENCES[reward["name"]][0][0]
		label, value, count = next((r for r in refs if r[0] == yardstick), refs[0])
		return value, "worth " + format_count(count) + "× " + label, refs
	return None, "no direct payout", []


def format_count(value):
	"""1 -> "1", 0.4 -> "0.4", 12.345 -> "12.35"."""
	return "{:,.2f}".format(value).rstrip("0").rstrip(".")


def payouts_in(days, frequency):
	"""Whole payouts received when holding for `days`, paid every `frequency` days."""
	return int(days // frequency)


def roi(cost, payout_value, blocks, frequency, years=ROI_YEARS):
	"""
	Dividend returns for each holding period.
	Returns a list of (years, payouts, earned, earned as % of cost).
	"""
	rows = []
	for y in years:
		n = payouts_in(y * DAYS_PER_YEAR, frequency)
		earned = n * blocks * payout_value
		rows.append((y, n, earned, earned / cost * 100 if cost else 0.0))
	return rows


def break_even_days(cost, payout_value, blocks, frequency):
	"""Days of holding until the payouts add up to the cost (whole payouts), or None."""
	per_payout = payout_value * blocks
	if per_payout <= 0:
		return None
	return math.ceil(cost / per_payout) * frequency


def block_breakdown(requirement, blocks, price, payout_value, frequency):
	"""
	Each block's own cost and return, showing how doubling shrinks the return of later blocks.
	Returns a list of (block, shares it adds, its cost, its 1-year return % or None).
	"""
	rows = []
	yearly = payouts_in(DAYS_PER_YEAR, frequency) * payout_value if payout_value else None
	for b in range(1, blocks + 1):
		shares = shares_for_block(requirement, b)
		cost = shares * price
		rows.append((b, shares, cost, yearly / cost * 100 if (yearly is not None and cost) else None))
	return rows
