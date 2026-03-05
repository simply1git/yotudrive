# YotuDrive V5 Architecture (Foundation)

## What Was Implemented

This repository now includes a modular V5 foundation layer:

- `src/header_v5.py`
  - Dedicated V5 header pack/unpack with CRC32 validation.
  - Includes payload metadata, ECC config, compression id, part index/total parts, KDF iterations, and encryption chunk size.
  - Majority-vote header recovery helper.
- `src/settings.py`
  - Centralized settings schema with defaults, normalization, load/save, and override merge.
- `src/core/engine.py`
  - Shared engine facade used by interfaces.
  - Exposes `encode_file`, `decode_source`, `verify_video`, `list_files`, and `attach_video_reference`.
  - Supports split-aware encode orchestration and multipart DB linking.
- `src/youtube_api.py`
  - Optional OAuth uploader integration layer for YouTube Data API v3.
  - Uses installed-app OAuth with refreshable credential persistence.

## Why These Design Choices

- Fernet is not suitable for true unbounded streaming as a single token; chunked token strategy is kept for compatibility.
- RS remains chunked around `n=255` symbols with configurable ECC parity bytes.
- Header metadata is isolated from encoder/decoder monoliths to allow deterministic tests and future protocol evolution.

## Deep-Research Notes Applied

- Fernet guidance from `cryptography.io` confirms whole-message limitations and recommends strong KDF iterations.
- Reed-Solomon operational constraints from `reedsolo` docs align with 255-symbol blocks and parity/error correction tradeoffs.
- YouTube Data API guidance from Google docs informed OAuth scope, resumable upload usage, and token management strategy.

## Next Build Steps

- Wire web backend endpoints to `src/core/engine.py` (no Flask app exists yet in this workspace).
- Integrate `src/youtube_api.py` option into GUI flows for direct upload mode.
- Expand integration tests for split playlist restore and auto-join across parts.
