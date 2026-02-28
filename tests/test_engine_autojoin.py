from pathlib import Path

from src.engine import YotuDriveEngine


def test_auto_join_parts(tmp_path):
    """Engine should correctly join sequential part files."""
    engine = YotuDriveEngine(
        uploads_dir=str(tmp_path / "uploads"),
        temp_dir=str(tmp_path / "temp"),
        downloads_dir=str(tmp_path / "downloads"),
    )

    # Create three part files with known content
    parts = []
    combined = b""
    for idx, content in enumerate([b"AAA", b"BBB", b"CCC"], start=1):
        part_path = tmp_path / f"file.part{idx:03d}.bin"
        part_path.write_bytes(content)
        combined += content
        parts.append(part_path)

    final_path = engine._auto_join_parts(parts)
    assert final_path.exists()
    assert final_path.read_bytes() == combined

