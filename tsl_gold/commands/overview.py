import discord
from discord import app_commands

import tsl_core.functions as tsl_lib
import tsl_config.config as config

client = config.client

async def timeframe_autocomplete(interaction: discord.Interaction, current: str):
    # Filter out m1 — too noisy for an overview scan
    allowed = [t for t in tsl_lib.intervals if t != "m1"]
    return [
        app_commands.Choice(name=t, value=t)
        for t in allowed
        if current.lower() in t.lower()
    ][:25]

@client.tree.command(name="overview", description="Scan all stocks for biggest movers, period lows, or period highs.")
@app_commands.describe(
    mode="Type of Analysis",
    timeframe="Time Range (m1, m5, h1, d1, ...)",
    candles="Number of intervals to check"
)
@app_commands.choices(mode=[
    app_commands.Choice(name="Movers (Largest Price Change)", value="movers"),
    app_commands.Choice(name="Near Recent Lows", value="lows"),
    app_commands.Choice(name="Near Recent Highs", value="highs"),
])
@app_commands.autocomplete(timeframe=timeframe_autocomplete)
async def overview(interaction: discord.Interaction, mode: str, timeframe: str = "d1", candles: int = 7):
    await interaction.response.defer()

    # Validate inputs
    if timeframe not in tsl_lib.intervals or timeframe == "m1":
        embed = discord.Embed(title=":no_entry_sign: Invalid Timeframe :no_entry_sign:")
        embed.color = discord.Color.red()
        embed.add_field(name="Details:", value="Supported intervals:\n`m5 m15 m30 h1 h2 h4 h6 h12 d1`")
        client.set_author_interaction(interaction, embed)
        await interaction.followup.send(embed=embed)
        return

    if candles < 2:
        candles = 2
    elif candles > 4000:
        candles = 4000

    # Build a lookup of current prices from the live Tornsy feed
    current_prices = {}
    stock_names = {}
    for data in config.json_data["data"]:
        current_prices[data["stock"]] = float(data["price"])
        stock_names[data["stock"]] = data["name"]

    # Scan every stock
    results = []
    for ticker in tsl_lib.stock_lut:
        if ticker == "TCSE":
            continue

        current = current_prices.get(ticker)
        if current is None or current == 0:
            continue

        try:
            dt = tsl_lib.db.get_stock(ticker.lower(), timeframe, limit=candles)
        except Exception:
            continue

        # Need at least 2 candles to do anything useful
        if len(dt["Close"]) < 2:
            continue

        if mode == "movers":
            period_open = dt["Close"][0]
            if period_open == 0:
                continue
            pct = ((current - period_open) / period_open) * 100
            results.append((ticker, current, period_open, pct))

        elif mode == "lows":
            period_low = min(dt["Low"])
            if period_low == 0:
                continue
            pct_above_low = ((current - period_low) / period_low) * 100
            results.append((ticker, current, period_low, pct_above_low))

        elif mode == "highs":
            period_high = max(dt["High"])
            if period_high == 0:
                continue
            pct_below_high = ((current - period_high) / period_high) * 100
            results.append((ticker, current, period_high, pct_below_high))

    if len(results) == 0:
        embed = discord.Embed(title=":warning: No Data :warning:")
        embed.color = discord.Color.orange()
        embed.add_field(name="Details:", value="Could not retrieve enough stock data for this scan. The local databases may still be populating.")
        client.set_author_interaction(interaction, embed)
        await interaction.followup.send(embed=embed)
        return

    # Sort n slice
    if mode == "movers":
        # Biggest absolute % change first
        results.sort(key=lambda r: abs(r[3]), reverse=True)
    elif mode == "lows":
        # Closest to their period low first (smallest % above)
        results.sort(key=lambda r: r[3])
    elif mode == "highs":
        # Closest to their period high first (least negative %)
        results.sort(key=lambda r: abs(r[3]))

    top = results[:8]

    # Build embed
    period_label = f"{timeframe}; from {candles} intervals ago:"

    if mode == "movers":
        title = f":bar_chart: Top Movers {period_label}"
        embed_lines = []
        for ticker, cur_price, ref_price, pct in top:
            arrow = ":chart_with_upwards_trend:" if pct >= 0 else ":chart_with_downwards_trend:"
            name = stock_names.get(ticker, ticker)
            embed_lines.append(
                f"{arrow} **{ticker}** ({name})\n"
                f"Now: ${cur_price:,.2f}\nWas: ${ref_price:,.2f} ({pct:+.2f}%)"
            )

    elif mode == "lows":
        title = f":small_red_triangle_down: Near Recent Lows: {period_label}"
        embed_lines = []
        for ticker, cur_price, low_price, pct in top:
            name = stock_names.get(ticker, ticker)
            embed_lines.append(
                f":small_red_triangle_down: **{ticker}** ({name})\n"
                f"Now: ${cur_price:,.2f}\nLow: ${low_price:,.2f} ({pct:+.2f}%)"
            )

    elif mode == "highs":
        title = f":small_red_triangle: Near Recent Highs: {period_label}"
        embed_lines = []
        for ticker, cur_price, high_price, pct in top:
            name = stock_names.get(ticker, ticker)
            embed_lines.append(
                f":small_red_triangle: **{ticker}** ({name})\n"
                f"Now: ${cur_price:,.2f}\nHigh: ${high_price:,.2f} ({pct:+.2f}%)"
            )

    embed_str = "\n\n".join(embed_lines)

    embed = discord.Embed(title=title)
    embed.color = discord.Color.blue()
    embed.add_field(name=f"Top Stocks Sorted by % Change:", value=embed_str, inline=False)
    client.set_author_interaction(interaction, embed)
    await interaction.followup.send(embed=embed)