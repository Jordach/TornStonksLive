"""
Emergency live feed from Torn's own API, used when Tornsy can't be reached.

Torn's torn/?selections=stocks gives the current price, shares and investors for every
stock, which is all the every-minute update needs. It's reshaped into Tornsy's
/api/stocks format so the rest of the bot can't tell the difference, except that the
only past interval is the previous minute (remembered from the last Torn snapshot),
which is what the whale alerts compare against.
"""
import json
import time

import requests

TORN_STOCKS_URL = "https://api.torn.com/torn/?selections=stocks&key="


class TornFeedError(Exception):
	"""Torn's API answered, but not with stock data (bad key, rate limit, ...)."""


def to_tornsy_format(torn_json, previous=None, now=None):
	"""
	Convert a torn/?selections=stocks response into Tornsy's /api/stocks shape.

	previous: the result of the last call (a Tornsy-shaped dict), so interval.m1 holds
	the previous minute's shares and investors. Without it, m1 repeats the current values,
	so the first fallback minute never looks like a huge buy or sell.
	"""
	if now is None:
		now = time.time()
	if "error" in torn_json:
		err = torn_json["error"]
		raise TornFeedError("Torn API error " + str(err.get("code", "?")) + ": " + str(err.get("error", "unknown")))
	stocks = torn_json.get("stocks")
	if not stocks:
		raise TornFeedError("Torn's API returned no stocks.")

	before = {}
	if previous:
		for entry in previous.get("data", []):
			before[entry["stock"]] = entry

	data = []
	for stock in sorted(stocks.values(), key=lambda s: int(s.get("stock_id", 0))):
		ticker = str(stock["acronym"]).upper()
		price = "{:.2f}".format(float(stock["current_price"]))
		shares = int(stock.get("total_shares", 0))
		investors = int(stock.get("investors", 0))
		last = before.get(ticker)
		data.append({
			"stock": ticker,
			"name": stock.get("name", ticker),
			"price": price,
			"total_shares": shares,
			"investors": investors,
			"marketcap": int(stock.get("market_cap", 0)),
			"interval": {
				"m1": {
					"price": last["price"] if last else price,
					"total_shares": last["total_shares"] if last else shares,
					"investors": last["investors"] if last else investors,
				},
			},
		})

	return {"timestamp": int(now // 60 * 60), "data": data, "source": "torn"}


def fetch(api_key, previous=None, timeout=20):
	"""Live stocks from Torn in Tornsy's shape. Raises requests.RequestException or TornFeedError."""
	req = requests.get(TORN_STOCKS_URL + api_key, timeout=timeout)
	if req.status_code != 200:
		raise TornFeedError("Torn's API returned HTTP " + str(req.status_code) + ".")
	return to_tornsy_format(json.loads(req.text), previous)
