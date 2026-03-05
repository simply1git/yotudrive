import os
import struct
import uuid
import zlib
from dataclasses import dataclass
from typing import Iterable, List, Optional

MAGIC = b"YOTU"
HEADER_SIZE = 1024
CRC_OFFSET = HEADER_SIZE - 4

FLAG_COMPRESSED = 0x01
FLAG_ENCRYPTED = 0x02
FLAG_CHUNKED_ENCRYPTION = 0x04

COMPRESSION_STORE = 0
COMPRESSION_DEFLATE = 1
COMPRESSION_LZMA = 2
COMPRESSION_BZIP2 = 3


@dataclass(frozen=True)
class HeaderV5:
    version: int
    flags: int
    block_size: int
    ecc_bytes: int
    payload_length: int
    original_size: int
    md5_checksum: bytes
    salt: bytes
    header_copies: int
    compression: int
    kdf_iterations: int
    encryption_chunk_size: int
    part_index: int
    total_parts: int
    file_id: str
    filename: str


@dataclass(frozen=True)
class ParsedHeader:
    header: HeaderV5
    crc_valid: bool


def _safe_filename_bytes(filename: str, max_len: int) -> bytes:
    raw = os.path.basename(filename or "")
    encoded = raw.encode("utf-8", errors="ignore")
    return encoded[:max_len]


def _file_id_bytes(file_id: Optional[str]) -> bytes:
    if not file_id:
        return uuid.uuid4().bytes
    try:
        return uuid.UUID(file_id).bytes
    except (ValueError, AttributeError):
        return uuid.uuid5(uuid.NAMESPACE_OID, str(file_id)).bytes


def pack_header_v5(
    *,
    flags: int,
    block_size: int,
    ecc_bytes: int,
    payload_length: int,
    original_size: int,
    md5_checksum: bytes,
    salt: bytes,
    filename: str,
    header_copies: int = 5,
    compression: int = COMPRESSION_DEFLATE,
    kdf_iterations: int = 1_200_000,
    encryption_chunk_size: int = 1 * 1024 * 1024,
    part_index: int = 1,
    total_parts: int = 1,
    file_id: Optional[str] = None,
) -> bytes:
    if len(md5_checksum) != 16:
        raise ValueError("md5_checksum must be 16 bytes")
    if len(salt) != 16:
        raise ValueError("salt must be 16 bytes")
    if block_size <= 0 or block_size > 255:
        raise ValueError("block_size must be 1..255")
    if ecc_bytes <= 0 or ecc_bytes >= 255:
        raise ValueError("ecc_bytes must be 1..254")

    fixed = bytearray(CRC_OFFSET)
    fixed[0:4] = MAGIC
    fixed[4] = 5
    fixed[5] = flags & 0xFF
    fixed[6] = block_size & 0xFF
    fixed[7] = ecc_bytes & 0xFF
    fixed[8:16] = struct.pack(">Q", payload_length)
    fixed[16:24] = struct.pack(">Q", original_size)
    fixed[24:40] = md5_checksum
    fixed[40:56] = salt
    fixed[56] = header_copies & 0xFF
    fixed[57] = compression & 0xFF
    fixed[58:62] = struct.pack(">I", int(kdf_iterations))
    fixed[62:66] = struct.pack(">I", int(encryption_chunk_size))
    fixed[66:70] = struct.pack(">I", int(part_index))
    fixed[70:74] = struct.pack(">I", int(total_parts))
    fixed[74:90] = _file_id_bytes(file_id)

    max_name = CRC_OFFSET - 91
    fname = _safe_filename_bytes(filename, max_name)
    fixed[90] = len(fname)
    if fname:
        fixed[91 : 91 + len(fname)] = fname

    crc = zlib.crc32(bytes(fixed)) & 0xFFFFFFFF
    return bytes(fixed) + struct.pack(">I", crc)


def parse_header_v5(data: bytes) -> ParsedHeader:
    if len(data) < HEADER_SIZE:
        raise ValueError("Header data too short")

    raw = data[:HEADER_SIZE]
    if raw[0:4] != MAGIC:
        raise ValueError("Invalid magic")

    version = raw[4]
    if version != 5:
        raise ValueError(f"Unsupported V5 parser version: {version}")

    stored_crc = struct.unpack(">I", raw[CRC_OFFSET:HEADER_SIZE])[0]
    calc_crc = zlib.crc32(raw[:CRC_OFFSET]) & 0xFFFFFFFF

    name_len = raw[90]
    max_name = CRC_OFFSET - 91
    name_len = min(name_len, max_name)
    filename = raw[91 : 91 + name_len].decode("utf-8", errors="ignore")

    header = HeaderV5(
        version=version,
        flags=raw[5],
        block_size=raw[6],
        ecc_bytes=raw[7],
        payload_length=struct.unpack(">Q", raw[8:16])[0],
        original_size=struct.unpack(">Q", raw[16:24])[0],
        md5_checksum=bytes(raw[24:40]),
        salt=bytes(raw[40:56]),
        header_copies=raw[56],
        compression=raw[57],
        kdf_iterations=struct.unpack(">I", raw[58:62])[0],
        encryption_chunk_size=struct.unpack(">I", raw[62:66])[0],
        part_index=struct.unpack(">I", raw[66:70])[0],
        total_parts=struct.unpack(">I", raw[70:74])[0],
        file_id=str(uuid.UUID(bytes=bytes(raw[74:90]))),
        filename=filename,
    )
    return ParsedHeader(header=header, crc_valid=(stored_crc == calc_crc))


def recover_header_majority(candidates: Iterable[bytes]) -> bytes:
    normalized: List[bytes] = []
    for h in candidates:
        if not h:
            continue
        if len(h) < HEADER_SIZE:
            h = h + (b"\x00" * (HEADER_SIZE - len(h)))
        normalized.append(h[:HEADER_SIZE])

    if not normalized:
        raise ValueError("No header candidates provided")
    if len(normalized) == 1:
        return normalized[0]

    out = bytearray(HEADER_SIZE)
    for i in range(HEADER_SIZE):
        counts = [0] * 256
        for h in normalized:
            counts[h[i]] += 1
        out[i] = max(range(256), key=lambda b: counts[b])
    return bytes(out)
