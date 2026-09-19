import unittest
from unittest.mock import patch
from pathlib import Path

from super import Intent, Supremo


class SupremoTests(unittest.TestCase):
    def setUp(self):
        self.assistant = Supremo()

    def test_parse_common_commands(self):
        self.assertEqual(self.assistant.parse(
            "open Safari"), Intent("open", "Safari"))
        self.assertEqual(self.assistant.parse(
            "search Python"), Intent("search", "Python"))
        self.assertEqual(self.assistant.parse(
            "look up Python"), Intent("search", "Python"))
        self.assertEqual(self.assistant.parse("quit"), Intent("quit"))

    def test_parse_polite_and_new_commands(self):
        self.assertEqual(
            self.assistant.parse("please open Safari"),
            Intent("open", "Safari"),
        )
        self.assertEqual(
            self.assistant.parse("what time is it?"),
            Intent("time"),
        )
        self.assertEqual(self.assistant.parse("battery"), Intent("battery"))
        self.assertEqual(
            self.assistant.parse("say hello there"),
            Intent("say", "hello there"),
        )
        self.assertEqual(self.assistant.parse(""), Intent("empty"))

    def test_open_existing_path(self):
        with patch("super.Path.exists", return_value=True), patch.object(
            self.assistant, "_run"
        ) as run:
            self.assistant.open_target("~/Documents")
        run.assert_called_once_with(
            ["open", str(Path("~/Documents").expanduser())])

    def test_unknown_intent_does_not_crash(self):
        with patch.object(self.assistant, "explain_unknown") as explain:
            self.assertTrue(self.assistant.handle(
                Intent("unsupported", "value")))
        explain.assert_called_once_with("value")

    def test_run_command_blocks_risky_binaries(self):
        with patch("builtins.input") as prompt:
            self.assistant.run_command("rm -rf /tmp")
        prompt.assert_not_called()

    def test_empty_intent_keeps_session_open(self):
        self.assertTrue(self.assistant.handle(Intent("empty")))


if __name__ == "__main__":
    unittest.main()
