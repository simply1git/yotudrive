import os
import tempfile
import unittest

from src.settings import CompressionStrategy, EngineSettings, load_settings, merge_settings, save_settings


class SettingsTests(unittest.TestCase):
    def test_merge_and_normalization(self):
        base = EngineSettings()
        merged = merge_settings(
            base,
            {
                "compression": "Fast (Deflate)",
                "threads": 0,
                "kdf_iterations": 20000,
                "split_threshold_gb": 1.5,
            },
        )
        self.assertEqual(merged.compression, CompressionStrategy.DEFLATE.value)
        self.assertEqual(merged.threads, 1)
        self.assertGreaterEqual(merged.kdf_iterations, 100000)
        self.assertEqual(merged.split_threshold_bytes, int(1.5 * 1024 * 1024 * 1024))

    def test_save_and_load(self):
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "settings.json")
            settings = EngineSettings(block_size=8, ecc_bytes=24, compression=CompressionStrategy.BZIP2.value)
            save_settings(settings, path)
            loaded = load_settings(path)
            self.assertEqual(loaded.block_size, 8)
            self.assertEqual(loaded.ecc_bytes, 24)
            self.assertEqual(loaded.compression, CompressionStrategy.BZIP2.value)


if __name__ == "__main__":
    unittest.main()
