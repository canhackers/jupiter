import contextlib
import io
import json
import os
import tempfile
import unittest

from settings import DEFAULT_SETTINGS, load_settings


class SettingsLoadTests(unittest.TestCase):
    def load_settings_quietly(self, path):
        with contextlib.redirect_stdout(io.StringIO()):
            return load_settings(path)

    def test_missing_settings_file_is_created_with_defaults(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = os.path.join(temp_dir, 'jupiter_settings.json')

            loaded = self.load_settings_quietly(path)

            self.assertEqual(loaded, DEFAULT_SETTINGS)
            with open(path, 'r') as f:
                saved = json.load(f)
            self.assertEqual(saved, DEFAULT_SETTINGS)

    def test_existing_settings_are_merged_with_new_default_keys(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = os.path.join(temp_dir, 'jupiter_settings.json')
            with open(path, 'w') as f:
                json.dump({'Logger': 0}, f)

            loaded = self.load_settings_quietly(path)

            self.assertEqual(loaded['Logger'], 0)
            self.assertEqual(loaded['MarsMode'], 0)
            self.assertIsNone(loaded['MapLampLeftShort'])
            with open(path, 'r') as f:
                saved = json.load(f)
            self.assertIn('MarsMode', saved)
            self.assertIn('MapLampLeftShort', saved)

    def test_invalid_settings_file_is_renamed_and_defaults_are_recreated(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = os.path.join(temp_dir, 'jupiter_settings.json')
            with open(path, 'w') as f:
                f.write('{not json')

            loaded = self.load_settings_quietly(path)

            self.assertEqual(loaded, DEFAULT_SETTINGS)
            self.assertTrue(os.path.exists(os.path.join(temp_dir, 'jupiter_settings_error.json')))
            with open(path, 'r') as f:
                saved = json.load(f)
            self.assertEqual(saved, DEFAULT_SETTINGS)


if __name__ == '__main__':
    unittest.main()
