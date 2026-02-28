import os

from src.encoder import Encoder
from src.decoder import Decoder
from src.config import HEADER_SIZE


def test_header_v5_roundtrip():
    """Ensure V5 headers created by Encoder can be parsed by Decoder."""
    dummy_input = "dummy.bin"
    # We do not touch the filesystem; header creation only uses metadata values.
    encoder = Encoder(dummy_input, output_dir=".", compression="deflate")

    payload_len = 123456789
    original_size = 987654321
    checksum = b"\x01" * 16
    flags = 0b00000111  # compressed + encrypted + chunked
    salt = b"\x02" * 16
    filename = "example.dat"

    header = encoder.create_header(
        payload_length=payload_len,
        original_size=original_size,
        checksum=checksum,
        flags=flags,
        salt=salt,
        filename=filename,
        version=5,
    )

    assert len(header) == HEADER_SIZE

    decoder = Decoder(input_dir=".", output_file="out.bin")
    (
        parsed_payload_len,
        parsed_original_size,
        parsed_checksum,
        parsed_flags,
        parsed_salt,
        header_copies,
        valid_crc,
        parsed_filename,
        _,
    ) = decoder.parse_header(header)

    assert parsed_payload_len == payload_len
    assert parsed_original_size == original_size
    assert parsed_checksum == checksum
    assert parsed_flags == flags
    assert parsed_salt == salt
    assert header_copies >= 1
    assert valid_crc is True
    assert parsed_filename == filename

