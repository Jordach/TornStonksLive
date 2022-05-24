# TornStonksLive
TornStonks, but now a Discord bot.

# Command Reference
## Help Command:
`!help`

Gives a link to this part of the README.

`!help command_name`

## Stock Command:
Displays detailed help for that command including arguments.

`!stock three_letter_stock_name`

Displays detailed stock information about the stock chosen, by default, returns stock data from 30 minutes ago.

`!stock three_letter_stock_name UNIX_timestamp`

Displays stock information at the exact minute in Torn City Time.

`!stock three_letter_stock_name m1`

Displays stock information relative to now, in minutes. Replace the 1 with any number, cannot be negative.

`!stock three_letter_stock_name h1`

Displays stock information relative to now, in hours. Replace the 1 with any number, cannot be negative. `h1` is equal to `m60`.

`!stock three_letter_stock_name d1`

Displays stock information relative to now, in days. Replace the 1 with any number, cannot be negative. `d1` is equal to `h24`.

`!stock three_letter_stock_name w1`

Displays stock information relative to now, in weeks. Replace the 1 with any number, cannot be negative. `w1` is equal to `d7`.

`!stock three_letter_stock_name n1`

Displays stock information relative to now, in months. Replace the 1 with any number, cannot be negative. `n1` is equal to `d28`, `d30` or `d31`.

`!stock three_letter_stock_name y1`

Displays stock information relative to now, in years. Replace the 1 with any number, cannot be negative. `y1` is equal to `d365`.

## Up and Down Command:

`!up three_letter_stock_name value_to_reach`
`!down three_letter_stock_name value_to_reach`

Sets up an automatic alert for when the specified stock value exceeds or falls under a specified value.

## Buy and Sell Command:

`!buy money_to_buy_shares_with three_letter_stock_name`

Shows how many shares can be bought for the current price of a stock, includes leftover change from the purchase.

`!sell num_of_shares three_letter_stock_name`

Shows how much money you'd make for selling the specified number of shares for the chosen stock, includes pre and post stock exchange tax.

# Administration Commands:
## Stop Command:

`!stop`
Stops the bot, requires your ID to be listed in `admins.conf`.