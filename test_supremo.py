"""Unit tests for Supremo — the desktop management AI."""

import os
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

    def test_parse_close_command(self):
        self.assertEqual(self.assistant.parse("close Safari"), Intent("close", "Safari"))
        self.assertEqual(self.assistant.parse("terminate chrome"), Intent("close", "chrome"))
        self.assertEqual(self.assistant.parse("close finder"), Intent("close", "finder"))

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

    def test_close_uses_alias_and_osascript(self):
        with patch.object(self.assistant, "_run") as run:
            self.assistant.close_target("safari")
        run.assert_called_once_with(
            ["osascript", "-e", 'tell application "Safari" to quit']
        )

    def test_close_unknown_app_uses_raw_name(self):
        with patch.object(self.assistant, "_run") as run:
            self.assistant.close_target("MyCoolApp")
        run.assert_called_once_with(
            ["osascript", "-e", 'tell application "MyCoolApp" to quit']
        )

    def test_close_empty_is_noop(self):
        with patch.object(self.assistant, "_run") as run:
            self.assistant.close_target("")
        run.assert_not_called()

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

    def test_parse_chatgpt_command(self):
        """'chatgpt <query>' should return a chatgpt intent."""
        self.assertEqual(
            self.assistant.parse("chatgpt what is AI"),
            Intent("chatgpt", "what is AI"),
        )

    def test_parse_ask_chatgpt_command(self):
        """'ask chatgpt <query>' should return a chatgpt intent."""
        self.assertEqual(
            self.assistant.parse("ask chatgpt what is Python"),
            Intent("chatgpt", "what is Python"),
        )

    def test_chatgpt_without_api_key(self):
        """chatgpt should return a helpful message when no API key is set."""
        os.environ.pop("OPENAI_API_KEY", None)
        result = self.assistant._chatgpt_request("hello")
        self.assertIn("OPENAI_API_KEY", result)

    def test_parse_search_on_chatgpt(self):
        """'search X on chatgpt' should return a chatgpt intent with X as query."""
        self.assertEqual(
            self.assistant.parse("search what is AI on chatgpt"),
            Intent("chatgpt", "what is AI"),
        )

    def test_parse_google_on_chatgpt(self):
        """'google X on chatgpt' should return a chatgpt intent with X as query."""
        self.assertEqual(
            self.assistant.parse("google meaning of life on chatgpt"),
            Intent("chatgpt", "meaning of life"),
        )

    def test_parse_look_up_on_chatgpt(self):
        """'look up X on chatgpt' should return a chatgpt intent with X as query."""
        self.assertEqual(
            self.assistant.parse("look up python on chatgpt"),
            Intent("chatgpt", "python"),
        )

    def test_parse_ask_chatgpt_about(self):
        """'ask chatgpt about X' should strip 'about' and return X as query."""
        self.assertEqual(
            self.assistant.parse("ask chatgpt about machine learning"),
            Intent("chatgpt", "machine learning"),
        )

    def test_parse_search_chatgpt_for(self):
        """'search chatgpt for X' should return a chatgpt intent with X as query."""
        self.assertEqual(
            self.assistant.parse("search chatgpt for quantum computing"),
            Intent("chatgpt", "quantum computing"),
        )

    def test_eof_during_run_confirmation_exits_gracefully(self):
        """EOFError at the run confirmation prompt shouldn't crash."""
        with patch("builtins.input", side_effect=EOFError):
            try:
                self.assistant.run_command("echo hello")
            except EOFError:
                self.fail("run_command should not propagate EOFError")

    # --- Skills system tests ---
    def test_parse_skills_command(self):
        """'skills' should return a skill_list intent."""
        self.assertEqual(self.assistant.parse("skills"), Intent("skills"))

    def test_parse_skill_command(self):
        """'skill <name> <args>' should return a skill intent."""
        self.assertEqual(
            self.assistant.parse("skill calculate 2 + 2"),
            Intent("skill", "calculate 2 + 2"),
        )

    def test_default_skills_registered(self):
        """Default skills (calculate, note, remind) should be registered."""
        names = {name for name, _ in self.assistant.list_skills()}
        self.assertIn("calculate", names)
        self.assertIn("note", names)
        self.assertIn("remind", names)

    def test_register_custom_skill(self):
        """register_skill should add a new skill to the registry."""
        self.assistant.register_skill("test", "A test skill", lambda v: f"got: {v}")
        names = {name for name, _ in self.assistant.list_skills()}
        self.assertIn("test", names)

    def test_execute_known_skill(self):
        """execute_skill should call the handler and print its output."""
        self.assistant.register_skill("test", "A test skill", lambda v: f"got: {v}")
        with patch("builtins.print") as mock_print:
            self.assistant.execute_skill("test hello")
        mock_print.assert_called_once_with("got: hello")

    def test_execute_unknown_skill(self):
        """execute_skill should print a helpful message for unknown skills."""
        with patch("builtins.print") as mock_print:
            self.assistant.execute_skill("nonexistent")
        mock_print.assert_called_once()
        self.assertIn("No skill", mock_print.call_args[0][0])

    def test_calculate_skill(self):
        """The built-in calculate skill should evaluate math expressions."""
        with patch("builtins.print") as mock_print:
            self.assistant.execute_skill("calculate 2 + 2")
        mock_print.assert_called_once_with("Result: 4")

    def test_calculate_skill_multiplication(self):
        """The calculate skill should handle multiplication."""
        with patch("builtins.print") as mock_print:
            self.assistant.execute_skill("calculate 6 * 7")
        mock_print.assert_called_once_with("Result: 42")

    def test_unregister_skill(self):
        """unregister_skill should remove a skill."""
        self.assistant.register_skill("temp", "A temp skill", lambda v: "temp")
        self.assistant.unregister_skill("temp")
        names = {name for name, _ in self.assistant.list_skills()}
        self.assertNotIn("temp", names)


if __name__ == "__main__":
    unittest.main()
