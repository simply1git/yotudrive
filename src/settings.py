import json
import os
from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any, Dict, Optional

from .config import DEFAULT_BLOCK_SIZE, DEFAULT_ECC_BYTES, DEFAULT_HEADER_COPIES


class CompressionStrategy(str, Enum):
    STORE = "store"
    DEFLATE = "deflate"
    LZMA = "lzma"
    BZIP2 = "bzip2"


@dataclass
class EngineSettings:
    block_size: int = DEFAULT_BLOCK_SIZE
    ecc_bytes: int = DEFAULT_ECC_BYTES
    threads: int = max(1, (os.cpu_count() or 4) - 1)
    header_copies: int = DEFAULT_HEADER_COPIES
    encoder: str = "libx264"
    theme: str = "cosmo"
    compression: str = CompressionStrategy.DEFLATE.value
    auto_cleanup: bool = True
    split_size: str = "No Split"
    split_threshold_gb: float = 10.0
    split_enabled: bool = True
    encryption_chunk_size: int = 1 * 1024 * 1024
    kdf_iterations: int = 1_200_000

    @property
    def split_threshold_bytes(self) -> int:
        if self.split_threshold_gb <= 0:
            return 0
        return int(self.split_threshold_gb * 1024 * 1024 * 1024)


def _normalize_compression(value: str) -> str:
    if not value:
        return CompressionStrategy.DEFLATE.value

    normalized = str(value).strip().lower()
    aliases = {
        "none": CompressionStrategy.STORE.value,
        "store": CompressionStrategy.STORE.value,
        "no-compression": CompressionStrategy.STORE.value,
        "fast (deflate)": CompressionStrategy.DEFLATE.value,
        "deflate": CompressionStrategy.DEFLATE.value,
        "best (lzma)": CompressionStrategy.LZMA.value,
        "lzma": CompressionStrategy.LZMA.value,
        "bzip2": CompressionStrategy.BZIP2.value,
    }
    return aliases.get(normalized, CompressionStrategy.DEFLATE.value)


def _coerce(raw: Dict[str, Any]) -> EngineSettings:
    defaults = EngineSettings()
    return EngineSettings(
        block_size=int(raw.get("block_size", defaults.block_size)),
        ecc_bytes=int(raw.get("ecc_bytes", defaults.ecc_bytes)),
        threads=max(1, int(raw.get("threads", defaults.threads))),
        header_copies=max(1, int(raw.get("header_copies", defaults.header_copies))),
        encoder=str(raw.get("encoder", defaults.encoder)),
        theme=str(raw.get("theme", defaults.theme)),
        compression=_normalize_compression(str(raw.get("compression", defaults.compression))),
        auto_cleanup=bool(raw.get("auto_cleanup", defaults.auto_cleanup)),
        split_size=str(raw.get("split_size", defaults.split_size)),
        split_threshold_gb=float(raw.get("split_threshold_gb", defaults.split_threshold_gb)),
        split_enabled=bool(raw.get("split_enabled", defaults.split_enabled)),
        encryption_chunk_size=max(64 * 1024, int(raw.get("encryption_chunk_size", defaults.encryption_chunk_size))),
        kdf_iterations=max(100_000, int(raw.get("kdf_iterations", defaults.kdf_iterations))),
    )


def load_settings(path: str = "settings.json") -> EngineSettings:
    if not os.path.exists(path):
        return EngineSettings()
    try:
        with open(path, "r", encoding="utf-8") as fh:
            raw = json.load(fh)
        if not isinstance(raw, dict):
            return EngineSettings()
        return _coerce(raw)
    except (OSError, ValueError, json.JSONDecodeError):
        return EngineSettings()


def save_settings(settings: EngineSettings, path: str = "settings.json") -> None:
    payload = asdict(settings)
    payload["compression"] = _normalize_compression(payload["compression"])
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=4)


def merge_settings(base: EngineSettings, overrides: Optional[Dict[str, Any]]) -> EngineSettings:
    if not overrides:
        return base
    merged = asdict(base)
    merged.update(overrides)
    return _coerce(merged)
