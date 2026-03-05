import os
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from src.core.engine import Engine


class EngineSmokeTests(unittest.TestCase):
    def test_encode_file_uses_encoder_and_db(self):
        with tempfile.TemporaryDirectory() as td:
            input_file = os.path.join(td, "input.bin")
            output_dir = os.path.join(td, "frames")
            with open(input_file, "wb") as fh:
                fh.write(b"abc123" * 100)

            engine = Engine(settings_path=os.path.join(td, "settings.json"), db_path=os.path.join(td, "db.json"))

            with patch("src.core.engine.Encoder") as mock_encoder:
                instance = MagicMock()
                mock_encoder.return_value = instance
                result = engine.encode_file(input_file=input_file, output_root=output_dir, password=None)

            self.assertEqual(len(result.parts), 1)
            self.assertTrue(os.path.isdir(output_dir))
            instance.run.assert_called_once()
            files = engine.list_files()
            self.assertEqual(len(files), 1)
            self.assertEqual(files[0]["video_id"], "pending_upload")

    def test_encode_file_without_db_registration(self):
        with tempfile.TemporaryDirectory() as td:
            input_file = os.path.join(td, "input.bin")
            output_dir = os.path.join(td, "frames")
            with open(input_file, "wb") as fh:
                fh.write(b"z" * 1024)

            engine = Engine(settings_path=os.path.join(td, "settings.json"), db_path=os.path.join(td, "db.json"))

            with patch("src.core.engine.Encoder") as mock_encoder:
                instance = MagicMock()
                mock_encoder.return_value = instance
                result = engine.encode_file(
                    input_file=input_file,
                    output_root=output_dir,
                    password=None,
                    register_in_db=False,
                )

            self.assertEqual(len(result.parts), 1)
            self.assertIsNone(result.parts[0].db_id)
            self.assertEqual(engine.list_files(), [])

    def test_encode_to_video_pipeline_with_verification(self):
        with tempfile.TemporaryDirectory() as td:
            input_file = os.path.join(td, "input.bin")
            output_video = os.path.join(td, "out.mp4")
            restored_file = os.path.join(td, "restored.bin")

            with open(input_file, "wb") as fh:
                fh.write(b"abc" * 100)

            engine = Engine(settings_path=os.path.join(td, "settings.json"), db_path=os.path.join(td, "db.json"))

            with patch.object(engine, "encode_file") as mock_encode, \
                 patch("src.core.engine.stitch_frames") as mock_stitch, \
                 patch("src.core.engine.extract_frames") as mock_extract, \
                 patch.object(engine, "decode_source", return_value=restored_file) as mock_decode, \
                 patch.object(Engine, "_file_md5", side_effect=["same", "same"]):
                result = engine.encode_to_video(
                    input_file=input_file,
                    output_video=output_video,
                    verify_roundtrip=True,
                    auto_cleanup=True,
                    register_in_db=False,
                )

            mock_encode.assert_called_once()
            mock_stitch.assert_called_once()
            mock_extract.assert_called_once()
            mock_decode.assert_called_once()
            self.assertTrue(result["verified"])
            self.assertEqual(result["video_file"], output_video)

    def test_decode_video_source_pipeline(self):
        with tempfile.TemporaryDirectory() as td:
            video_path = os.path.join(td, "video.mp4")
            output_file = os.path.join(td, "restored.bin")
            with open(video_path, "wb") as fh:
                fh.write(b"dummy")

            engine = Engine(settings_path=os.path.join(td, "settings.json"), db_path=os.path.join(td, "db.json"))

            with patch("src.core.engine.extract_frames") as mock_extract, \
                 patch.object(engine, "decode_source", return_value=output_file) as mock_decode:
                result = engine.decode_video_source(
                    video_path=video_path,
                    output_file=output_file,
                    auto_cleanup=True,
                )

            mock_extract.assert_called_once()
            mock_decode.assert_called_once()
            self.assertEqual(result["output_file"], output_file)


if __name__ == "__main__":
    unittest.main()
