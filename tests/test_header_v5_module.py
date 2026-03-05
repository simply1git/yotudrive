import unittest

from src.header_v5 import (
    COMPRESSION_DEFLATE,
    FLAG_CHUNKED_ENCRYPTION,
    FLAG_COMPRESSED,
    FLAG_ENCRYPTED,
    pack_header_v5,
    parse_header_v5,
    recover_header_majority,
)


class HeaderV5Tests(unittest.TestCase):
    def test_pack_parse_roundtrip(self):
        payload_md5 = bytes.fromhex("00112233445566778899aabbccddeeff")
        salt = bytes.fromhex("ffeeddccbbaa99887766554433221100")
        header_bytes = pack_header_v5(
            flags=FLAG_COMPRESSED | FLAG_ENCRYPTED | FLAG_CHUNKED_ENCRYPTION,
            block_size=2,
            ecc_bytes=32,
            payload_length=123456,
            original_size=654321,
            md5_checksum=payload_md5,
            salt=salt,
            filename="example.bin",
            compression=COMPRESSION_DEFLATE,
            part_index=2,
            total_parts=5,
            file_id="550e8400-e29b-41d4-a716-446655440000",
        )

        parsed = parse_header_v5(header_bytes)
        self.assertTrue(parsed.crc_valid)
        self.assertEqual(parsed.header.version, 5)
        self.assertEqual(parsed.header.payload_length, 123456)
        self.assertEqual(parsed.header.original_size, 654321)
        self.assertEqual(parsed.header.filename, "example.bin")
        self.assertEqual(parsed.header.part_index, 2)
        self.assertEqual(parsed.header.total_parts, 5)
        self.assertEqual(parsed.header.md5_checksum, payload_md5)

    def test_majority_recovery(self):
        payload_md5 = bytes.fromhex("00112233445566778899aabbccddeeff")
        salt = bytes.fromhex("ffeeddccbbaa99887766554433221100")
        baseline = bytearray(
            pack_header_v5(
                flags=FLAG_COMPRESSED,
                block_size=4,
                ecc_bytes=16,
                payload_length=999,
                original_size=1111,
                md5_checksum=payload_md5,
                salt=salt,
                filename="majority.txt",
            )
        )

        a = bytes(baseline)
        b = bytearray(baseline)
        c = bytearray(baseline)
        b[30] ^= 0xFF
        c[30] ^= 0xFF
        c[700] ^= 0x01

        recovered = recover_header_majority([a, bytes(b), bytes(c)])
        parsed = parse_header_v5(recovered)
        self.assertEqual(parsed.header.filename, "majority.txt")
        self.assertEqual(parsed.header.payload_length, 999)


if __name__ == "__main__":
    unittest.main()
