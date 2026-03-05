import unittest

from src.decoder import Decoder


class DecoderDetectionTests(unittest.TestCase):
    def test_candidate_block_sizes(self):
        candidates = Decoder._candidate_block_sizes(max_block_size=64)
        self.assertIn(6, candidates)
        self.assertIn(15, candidates)
        self.assertIn(20, candidates)
        self.assertNotIn(7, candidates)
        self.assertNotIn(11, candidates)


if __name__ == "__main__":
    unittest.main()
