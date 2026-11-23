"""Every slash command reply must respect the private-reply rule (see
tsl_config.config.private_reply). Parses the command sources; nothing is imported."""
import ast
import os
import unittest

COMMANDS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tsl_gold", "commands")


def _chain(node):
	"""Dotted name of an attribute chain, e.g. interaction.followup.send."""
	parts = []
	while isinstance(node, ast.Attribute):
		parts.append(node.attr)
		node = node.value
	if isinstance(node, ast.Name):
		parts.append(node.id)
	return ".".join(reversed(parts))


class CommandRepliesRespectPrivacyTests(unittest.TestCase):
	"""Every slash command reply must decide its visibility: ephemeral=True, or
	ephemeral=config.private_reply(interaction). No reply may bypass that by posting to
	the channel directly, except /force_suggestions' "This Channel", which is only
	reachable in a command channel."""

	REPLY_CALLS = ("interaction.response.defer", "interaction.response.send_message", "interaction.followup.send")
	CHANNEL_POST_ALLOWED = {"admin.py": 1}

	def test_replies_set_ephemeral(self):
		problems = []
		channel_posts = {}
		for name in sorted(os.listdir(COMMANDS_DIR)):
			if not name.endswith(".py"):
				continue
			with open(os.path.join(COMMANDS_DIR, name), encoding="utf-8") as f:
				tree = ast.parse(f.read(), name)
			for node in ast.walk(tree):
				if not isinstance(node, ast.Call):
					continue
				chain = _chain(node.func)
				if chain in self.REPLY_CALLS and not any(k.arg == "ephemeral" for k in node.keywords):
					problems.append(name + ":" + str(node.lineno) + " " + chain + "() has no ephemeral=")
				if chain == "interaction.channel.send":
					channel_posts[name] = channel_posts.get(name, 0) + 1
		self.assertEqual(problems, [])
		self.assertEqual(channel_posts, self.CHANNEL_POST_ALLOWED)


if __name__ == "__main__":
	unittest.main()
