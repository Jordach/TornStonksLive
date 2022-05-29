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

Displays detailed stock information about the stock chosen, by default, returns stock data from 1 hour, 1 day, 1 week and 1 month ago.

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

`!up three_letter_stock_name percentage %`

`!down three_letter_stock_name percentage %`

Sets a relative pricing alert to it's current price.

## Buy and Sell Command:

`!buy money_to_buy_shares_with three_letter_stock_name`

Shows how many shares can be bought for the current price of a stock, includes leftover change from the purchase.

`!sell num_of_shares three_letter_stock_name`

Shows how much money you'd make for selling the specified number of shares for the chosen stock, includes pre and post stock exchange tax.

## Notifications / Alerts:

`!alerts`

`!notifications`

Displays all pending alerts and notifications. These two commands are interchangeable.

`!alerts up/down`

Displays all pending alerts that are either from the corresponding `!up` or `!down` command.

`!alerts up/down three_letter_stock_name`

Displays all pending alerts that are either from the corresponding `!up` or `!down` command and are also matching that stock ticker.

## Forget:

`!forgetme`

Deletes all of your pending alerts from the bot's knowledge.

`!forget three_letter_stock_name`

Deletes all pending alerts for the provided stock ticker.

`!forget three_letter_stock_name up/down`

Deletes all pending alerts for the provided stock ticker that are also from the respective `!up` or `!down` command.

`!forget three_letter_stock_name up/down value`

Deletes any pending alert that matches the stock ticker, `!up` and `!down` command, and also the value.

## Portfolio:

### This command only works in Direct Messages with the bot. It will send you a DM if you execute this command in any server.

`!portfolio torn_api_key`

Lists all stocks that you own with all transactions with their change in price relative to now. All transactions for that stock are ordered newest first to oldest last.

`!portfolio torn_api_key stock_ticker`

Lists all transactions for the specified ticker.

`!portfolio torn_api_key stock_ticker number_of_transactions`

Lists `number_of_transactions` of the selected stock before stopping. If you have two or more transactions, and use a it'll show the most recent transaction.

# Administration Commands:
## Stop Command:

`!stop`
Stops the bot, requires your ID to be listed in `admins.conf`.