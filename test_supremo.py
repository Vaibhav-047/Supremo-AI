"""Unit tests for Supremo — the desktop management AI."""

import unittest
from unittest.mock import patch, MagicMock
from pathlib import Path

from supremo import Intent, Supremo, VoiceUnavailable


class SupremoTests(unittest.TestCase):
    def setUp(self):
        self.assistant = Supremo()

    # --- Parsing tests ---

    def test_parse_common_commands(self):
        self.assertEqual(self.assistant.parse("open Safari"), Intent("open", "Safari"))
        self.assertEqual(self.assistant.parse("search Python"), Intent("search", "Python"))
        self.assertEqual(self.assistant.parse("look up Python"), Intent("search", "Python"))
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

    def test_parse_open_strips_polite_prefix(self):
        self.assertEqual(
            self.assistant.parse("please open Safari"),
            Intent("open", "Safari"),
        )
        self.assertEqual(
            self.assistant.parse("could you open Safari please"),
            Intent("open", "Safari"),
        )

    def test_parse_screenshot_variants(self):
        self.assertEqual(self.assistant.parse("screenshot"), Intent("screenshot"))
        self.assertEqual(self.assistant.parse("take a screenshot"), Intent("screenshot"))
        self.assertEqual(self.assistant.parse("capture screen"), Intent("screenshot"))

    # --- Handling tests ---

    def test_open_existing_path(self):
        with patch("supremo.Path.exists", return_value=True), patch.object(
            self.assistant, "_run"
        ) as run:
            self.assistant.open_target("~/Documents")
        run.assert_called_once_with(["open", str(Path("~/Documents").expanduser())])

    def test_unknown_intent_does_not_crash(self):
        with patch.object(self.assistant, "explain_unknown") as explain:
            self.assertTrue(self.assistant.handle(Intent("unsupported", "value")))
        explain.assert_called_once_with("value")

    def test_empty_intent_keeps_session_open(self):
        self.assertTrue(self.assistant.handle(Intent("empty")))

    def test_quit_returns_false(self):
        self.assertFalse(self.assistant.handle(Intent("quit")))

    # --- Safety tests ---

    def test_run_command_blocks_risky_binaries(self):
        with patch("builtins.input") as prompt:
            self.assistant.run_command("rm -rf /tmp")
        prompt.assert_not_called()

    def test_run_command_blocks_sudo(self):
        with patch("builtins.input") as prompt:
            self.assistant.run_command("sudo apt update")
        prompt.assert_not_called()

    def test_run_command_blocks_path_with_stem(self):
        """Block 'sudo' even when called as '/usr/bin/sudo'."""
        with patch("builtins.input") as prompt:
            self.assistant.run_command("/usr/bin/sudo whoami")
        prompt.assert_not_called()

    def test_voice_cannot_run_shell_commands(self):
        """Voice input is blocked from 'run', 'listen', and 'voice_mode'."""
        for action in ("run", "listen", "voice_mode"):
            with patch("builtins.input") as prompt:
                result = self.assistant.handle(
                    Intent(action, ""), from_voice=True
                )
            self.assertTrue(result)
            prompt.assert_not_called()

    def test_voice_blocks_are_typed_only(self):
        """When not from voice, blocked actions should still work."""
        # 'run' should reach the confirmation prompt when typed
        with patch("builtins.input", return_value="n"):
            self.assistant.handle(Intent("run", "echo test"), from_voice=False)

    # --- Error handling tests ---

    def test_eof_during_run_confirmation_exits_gracefully(self):
        """EOFError at the run confirmation prompt shouldn't crash."""
        with patch("builtins.input", side_effect=EOFError):
            try:
                self.assistant.run_command("echo hello")
            except EOFError:
                self.fail("run_command should not propagate EOFError")


if __name__ == "__main__":
    unittest.main()
