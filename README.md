# TornStonks Live

A Discord bot for the [Torn City](https://www.torn.com) stock market: live prices, price alerts by
DM, chart pattern scans, forecasts, and daily TA-backed stock picks with a public track record.
It's free for everyone.

Price data comes from [Tornsy](https://tornsy.com) every minute and is kept in a local SQLite
history, one database per stock.

## Commands

Every command is a slash command. `/glossary` explains each one (and every term the bot uses) inside
Discord, and its **New trader's guide** is the best place for new players to start.

| Command | What it does |
| --- | --- |
| `/stock` | A stock's price, shares and investors, optionally compared with a timeframe (`h1`, `d1`, `w1`, `n1`) or a unix timestamp. |
| `/overview` | Scan every stock for the biggest movers, or those near recent lows or highs. |
| `/search` | Candle patterns and RSI / Stochastic / MACD readings on one stock, or `ALL`. |
| `/suggest` | Today's Upswing and Buy the Dip picks, the full ranking, or the track record of past picks. |
| `/predict` | An XGBoost price forecast chart. |
| `/alert` | DM me when a stock goes up to, down to, or falls below a price (or a % from now). |
| `/notifications` | List your pending alerts. |
| `/forget` · `/undo` · `/clear` | Remove alerts for a stock, your last alert, or all of them. |
| `/paper buy` · `/paper sell` | Shares a sum of cash buys, or what shares sell for after Torn's 0.1% fee. |
| `/benefit` | Shares and cost for a number of a stock's benefit blocks, what the reward is worth (energy/nerve/happy/points compared with items) and its return over 1, 3, 5 and 10 years. |
| `/portfolio` | Your real Torn holdings and how each purchase is doing (needs `/apikey`). |
| `/apikey` | Save, replace, check or remove your Torn API key (stored encrypted). |
| `/glossary` | Search commands and terms; includes the new trader's guide. |
| `/credits` | The people who've helped the bot along. |

Admin-only: `/stop` (shut down), `/sync` (push the command list to Discord) and
`/force_suggestions` (run the daily/weekly suggestion post now, as a preview or live).

Number fields accept shorthand: `500k`, `1.5m`, `2b`, `1,000,000`.

## Running the bot

### Install

With conda (recommended, since TA-Lib is easiest to install this way):

```
conda env create -f environment.yaml
conda activate TSL
```

Or with pip, after installing the [TA-Lib C library](https://ta-lib.org/install/):

```
pip install -r requirements.txt
```

The bot needs no privileged intents: in the [Discord developer portal](https://discord.com/developers/applications),
**Server Members**, **Presence** and **Message Content** can all stay off.

### Configure

Create these files next to `main.py`:

| File | Contents |
| --- | --- |
| `settings.conf` | The bot token on the first line (see `settings_example.conf`). |
| `admins.json` | `{"admins": [your_discord_id, ...]}` for the admin commands. |
| `alert_channels.conf` | One line per channel: `channel_id,tiny_role_id,small_role_id,medium_role_id,large_role_id` for large-trade (whale) pings. Trades of $150bn+ ping the small role, $450bn+ add medium, $750bn+ add large; smaller trades ping the tiny role, or nothing if it's `0`. |
| `suggestion_channels.conf` | One line per channel: `channel_id` or `channel_id,role_id` for the suggestion (upswing / buy the dip) and volatility posts. The role, if given and not `0`, is pinged on volatility posts only; suggestion posts don't ping. |
| `command_channels.conf` | One channel ID per line (lines like `channel_id,!,channel` from older installs still work). Command replies are public in these channels and their threads, and private (only the user sees them) in every other server channel, whatever a command's own options say. With none listed, replies are public everywhere. A DM with the bot counts as a command channel (only the user sees it); group DMs do not. |

The channel files are created empty if missing. An empty one only stops startup when the feature
that needs it is on: `suggestions=true` and `volatility=true` both need `suggestion_channels.conf`.
Without alert channels, large-trade pings are simply not posted.
| `features.conf` | Created on first run. Switches, one per line: `suggestions=true/false` (scheduled suggestion posts, default off), `volatility=true/false` (volatility posts, default off), `backfill=true/false` (catch up on missed price history from Tornsy, default on; see below). |

Lines starting with `#` are comments. `encryption.key` (for stored API keys), `tsl_data.db`, and the
`db/` and `logs/` folders are created automatically. Keep `encryption.key` safe and out of version
control; without it, saved API keys can't be read.

### Start

```
python main.py
```

The first time, and after adding or changing commands, run `/sync` in Discord so the command list
updates.

Price history is built from Tornsy's one-minute prices; every other timeframe is derived from them.
With `backfill=true`, startup first loads the minutes missed since the bot last ran (at least the last
day on a new install), which takes a few seconds, then the bot connects. Anything older that's
missing is fetched in the background while live prices keep arriving. On a new install that's
several years of history, a few hours in all; progress is logged per stock. An interrupted backfill
resumes where it stopped on the next start, and a Tornsy outage is retried every 10 minutes.
Stored history is also checked for holes of an hour or more (say, an outage the live feed missed
while the bot kept running), at startup and daily at 03:30 UTC, and any found are filled the same way.
`/backfill` shows the progress and each stock's first and last stored minute.

## Tests

```
python -m unittest discover -s tests -t .
```

The pattern tests need TA-Lib and are skipped without it.

## Project layout

- `main.py`: startup, the every-minute Tornsy update, and scheduled jobs.
- `tsl_gold/commands/`: the slash commands (loaded automatically).
- `tsl_bot/`: the Discord client, alert DMs, whale pings, volatility and suggestion posts.
- `tsl_core/`: price databases, analysis (patterns, swing picks, forecasts), the glossary text and helpers.
- `tsl_config/`: config files, feature switches and encrypted key storage.
