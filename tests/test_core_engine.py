"""
Unit tests for the Engine facade.
We mock the underlying db, encoder, and decoder since those are
tested separately in their own modules.
"""
import unittest
from unittest.mock import patch, MagicMock
from src.core.engine import get_engine, Engine

class TestCoreEngine(unittest.TestCase):
    def setUp(self):
        self.engine = Engine()

    @patch('src.encoder.Encoder')
    def test_encode_file_delegation(self, mock_encoder_class):
        mock_instance = MagicMock()
        mock_encoder_class.return_value = mock_instance
        
        self.engine.encode_file('in.txt', 'out_dir', block_size=4, ecc_bytes=16)
        
        mock_encoder_class.assert_called_once_with(
            'in.txt', 'out_dir', password=None, block_size=4, ecc_bytes=16,
            threads=None, progress_callback=None, check_cancel=None
        )
        mock_instance.run.assert_called_once()
        
    @patch('src.decoder.Decoder')
    def test_decode_source_delegation(self, mock_decoder_class):
        mock_instance = MagicMock()
        mock_instance.output_file = 'out.txt'
        mock_decoder_class.return_value = mock_instance
        
        result = self.engine.decode_source('out_dir', 'out.txt', password='abc')
        
        mock_decoder_class.assert_called_once_with(
            'out_dir', 'out.txt', password='abc', threads=None,
            progress_callback=None, check_cancel=None
        )
        mock_instance.run.assert_called_once()
        self.assertEqual(result, 'out.txt')

    @patch('src.db.FileDatabase')
    def test_list_files_filtering(self, mock_db_class):
        mock_db = MagicMock()
        mock_db.list_files.return_value = [
            {"id": "1", "owner_email": "admin@yotu"},
            {"id": "2", "owner_email": "user@yotu"},
            {"id": "3"} # legacy
        ]
        mock_db_class.return_value = mock_db
        
        all_files = self.engine.list_files()
        self.assertEqual(len(all_files), 3)
        
        admin_files = self.engine.list_files(owner_email="admin@yotu")
        self.assertEqual(len(admin_files), 1)
        self.assertEqual(admin_files[0]["id"], "1")

        legacy_admin = self.engine.list_files(owner_email="admin@yotu", include_legacy=True)
        self.assertEqual(len(legacy_admin), 2)

    @patch('src.db.FileDatabase')
    def test_attach_video_reference(self, mock_db_class):
        mock_db = MagicMock()
        mock_db.get_file.return_value = {"id": "123", "owner_email": "user@yotu"}
        mock_db_class.return_value = mock_db
        
        # Valid user
        res = self.engine.attach_video_reference("123", "v_abc", video_url="http://yt", owner_email="user@yotu")
        self.assertEqual(res["video_id"], "v_abc")
        self.assertEqual(res["video_url"], "http://yt")

if __name__ == '__main__':
    unittest.main()
