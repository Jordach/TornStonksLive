"""Human-friendly numeric parsing for Discord inputs.

Accepts things people actually type, e.g.:
	"1000000"  "1,000,000"  "$1,000,000"  "1_000_000"  "1 000 000"
	"500k"  "1.5m"  "2B"  "1.25t"

Uses Decimal internally so "1.1b" is exactly 1,100,000,000 rather than
suffering float rounding.
"""

import re
from decimal import Decimal, InvalidOperation

SUFFIXES = {
	"k": Decimal(10) ** 3,
	"m": Decimal(10) ** 6,
	"b": Decimal(10) ** 9,
	"t": Decimal(10) ** 12,
}

_PATTERN = re.compile(r"^([+-]?)(\d+(?:\.\d+)?|\.\d+)([kmbt]?)$")


class NumericParseError(ValueError):
	"""Raised when input can't be read as a number. str(err) is user-facing."""


def _parse(text: str) -> Decimal:
	if text is None:
		raise NumericParseError("No number was given.")

	cleaned = text.strip().lower()
	cleaned = cleaned.lstrip("$")
	for sep in (",", "_", " "):
		cleaned = cleaned.replace(sep, "")

	match = _PATTERN.match(cleaned)
	if match is None:
		raise NumericParseError(
			"`" + text + "` isn't a number I understand. Try something like `1000000`, `1,000,000`, `500k`, `1.5m` or `2b`."
		)

	sign, digits, suffix = match.groups()
	try:
		value = Decimal(digits)
	except InvalidOperation:
		raise NumericParseError("`" + text + "` isn't a valid number.")

	if suffix:
		value *= SUFFIXES[suffix]
	if sign == "-":
		value = -value
	return value


def parse_int(text: str, minimum: int = None, maximum: int = None) -> int:
	"""Parse a whole number, e.g. cash or share counts. "1.5k" -> 1500, "1.2345k" -> error."""
	value = _parse(text)
	if value != value.to_integral_value():
		raise NumericParseError("`" + text + "` works out to " + format(value.normalize(), "f") + ", which isn't a whole number.")
	result = int(value)
	_check_bounds(text, result, minimum, maximum)
	return result


def parse_float(text: str, minimum: float = None, maximum: float = None) -> float:
	"""Parse a decimal number, e.g. a share price."""
	result = float(_parse(text))
	_check_bounds(text, result, minimum, maximum)
	return result


def _check_bounds(text, value, minimum, maximum):
	if minimum is not None and value < minimum:
		raise NumericParseError("`" + text + "` is too small; it must be at least " + "{:,}".format(minimum) + ".")
	if maximum is not None and value > maximum:
		raise NumericParseError("`" + text + "` is too large; it must be at most " + "{:,}".format(maximum) + ".")
