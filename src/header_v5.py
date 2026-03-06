"""
YotuDrive V5 Header Utilities
Pure header pack/unpack extracted from encoder.py / decoder.py.
No circular imports — does NOT import encoder or decoder.
"""
import struct
import zlib
import numpy as np

HEADER_SIZE = 1024
MAGIC = b'YOTU'


def pack_header(
    payload_length: int,
    original_size: int,
    checksum: bytes,          # 16-byte MD5
    flags: int,               # Bit0=compress, Bit1=encrypt, Bit2=chunked-enc
    salt: bytes,              # 16 bytes
    filename: str,
    block_size: int,
    ecc_bytes: int,
    header_copies: int = 5,
    version: int = 5,
) -> bytes:
    """
    Build a 1024-byte V5 header with trailing CRC32.

    Header layout (same as encoder.py:create_header):
      0-3   Magic 'YOTU'
      4     Version
      5     Flags
      6     Block Size
      7     ECC Bytes
      8-15  Payload Length (uint64 big-endian)
      16-31 MD5 Checksum
      32-47 Salt
      48-55 Original Size (uint64 big-endian)
      56    Header Copies
      57    Filename Length
      58..  Filename UTF-8
      ...   Zero Padding
      1020-1023 CRC32 of bytes 0..1019
    """
    if len(salt) != 16:
        salt = b'\x00' * 16
    if len(checksum) != 16:
        checksum = b'\x00' * 16

    filename_bytes = filename.encode("utf-8")[:255] if filename else b""

    part1 = (
        MAGIC
        + bytes([version, flags, block_size, ecc_bytes])
        + struct.pack(">Q", payload_length)   # 8 bytes
        + checksum                             # 16 bytes
        + salt                                # 16 bytes
        + struct.pack(">Q", original_size)    # 8 bytes
        + bytes([header_copies, len(filename_bytes)])
        + filename_bytes
    )

    padding_len = HEADER_SIZE - len(part1) - 4  # 4 bytes reserved for CRC
    if padding_len < 0:
        raise ValueError("Header data exceeds 1020 bytes — filename too long?")

    body = part1 + b'\x00' * padding_len
    crc = zlib.crc32(body) & 0xFFFFFFFF
    return body + struct.pack(">I", crc)


def unpack_header(raw: bytes) -> dict:
    """
    Parse a 1024-byte header bytes object.
    Returns a dict of fields or raises ValueError on bad magic/CRC.
    Supports versions 1–5.
    """
    if len(raw) < HEADER_SIZE:
        raise ValueError(f"Header too short: {len(raw)} bytes")

    magic = raw[:4]
    if magic != MAGIC:
        raise ValueError(f"Invalid magic: {magic!r}")

    version = raw[4]

    # CRC check (versions 3+)
    valid_crc = True
    if version >= 3:
        stored_crc = struct.unpack(">I", raw[1020:1024])[0]
        calc_crc = zlib.crc32(raw[:1020]) & 0xFFFFFFFF
        if stored_crc != calc_crc:
            valid_crc = False

    flags = raw[5]

    if version >= 2:
        block_size = raw[6]
        ecc_bytes = raw[7]
        payload_len = struct.unpack(">Q", raw[8:16])[0]
        checksum = raw[16:32]
        salt = raw[32:48]
        original_size = struct.unpack(">Q", raw[48:56])[0]
    else:
        # V1 legacy — different layout
        block_size = 2   # not stored in V1 header
        ecc_bytes = 32
        flags = raw[5]
        payload_len = struct.unpack(">Q", raw[6:14])[0]
        checksum = raw[14:30]
        salt = raw[30:46]
        original_size = struct.unpack(">Q", raw[46:54])[0]
        return {
            "version": version, "flags": flags,
            "block_size": block_size, "ecc_bytes": ecc_bytes,
            "payload_len": payload_len, "checksum": checksum,
            "salt": salt, "original_size": original_size,
            "header_copies": 1, "filename": None,
            "valid_crc": True,
            "compressed": bool(flags & 0x01),
            "encrypted": bool(flags & 0x02),
            "chunked_enc": bool(flags & 0x04),
        }

    header_copies = raw[56] if version >= 3 else 1
    filename = None
    if version >= 4:
        fn_len = raw[57]
        filename = raw[58: 58 + fn_len].decode("utf-8", errors="ignore")

    return {
        "version": version,
        "flags": flags,
        "block_size": block_size,
        "ecc_bytes": ecc_bytes,
        "payload_len": payload_len,
        "checksum": checksum,
        "salt": salt,
        "original_size": original_size,
        "header_copies": header_copies,
        "filename": filename,
        "valid_crc": valid_crc,
        "compressed": bool(flags & 0x01),
        "encrypted": bool(flags & 0x02),
        "chunked_enc": bool(flags & 0x04),
    }


def majority_vote_recover(candidates: list) -> bytes:
    """
    Byte-wise majority vote across multiple (possibly corrupted) 1024-byte headers.
    Returns the recovered 1024-byte header.
    """
    if not candidates:
        raise ValueError("No header candidates provided")
    if len(candidates) == 1:
        return candidates[0]

    # Pad all to exactly 1024 bytes
    padded = []
    for h in candidates:
        if len(h) < HEADER_SIZE:
            h = h + b'\x00' * (HEADER_SIZE - len(h))
        padded.append(list(h[:HEADER_SIZE]))

    arr = np.array(padded, dtype=np.uint8)
    recovered = bytearray(HEADER_SIZE)
    for i in range(HEADER_SIZE):
        counts = np.bincount(arr[:, i], minlength=256)
        recovered[i] = int(np.argmax(counts))
    return bytes(recovered)
