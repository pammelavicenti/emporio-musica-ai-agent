from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from emporio_agent.config import Settings


class SettingsTests(unittest.TestCase):
    def test_model_has_no_assumed_default(self) -> None:
        with patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}, clear=True):
            settings = Settings.from_environment()
        self.assertEqual(settings.model, "")
        with self.assertRaisesRegex(ValueError, "GEMINI_MODEL"):
            settings.validate()

    def test_explicit_key_and_model_pass_configuration_validation(self) -> None:
        with patch.dict(
            os.environ,
            {"GEMINI_API_KEY": "test-key", "GEMINI_MODEL": "account-model"},
            clear=True,
        ):
            settings = Settings.from_environment()
        settings.validate()
        self.assertEqual(settings.model, "account-model")


if __name__ == "__main__":
    unittest.main()
