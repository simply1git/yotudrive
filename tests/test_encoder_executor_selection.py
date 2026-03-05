import concurrent.futures
import unittest
from unittest.mock import patch

import src.encoder as encoder


class TestExecutorSelection(unittest.TestCase):
    def test_frozen_windows_uses_thread_pool(self):
        with patch("src.encoder.os.name", "nt"), patch.object(encoder.sys, "frozen", True, create=True):
            cls = encoder._select_executor_class()
            self.assertIs(cls, concurrent.futures.ThreadPoolExecutor)

    def test_non_frozen_uses_process_pool(self):
        with patch.object(encoder.sys, "frozen", False, create=True):
            cls = encoder._select_executor_class()
            self.assertIs(cls, concurrent.futures.ProcessPoolExecutor)


if __name__ == "__main__":
    unittest.main()
