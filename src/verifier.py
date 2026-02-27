import os
import shutil
import uuid
import time
from .decoder import Decoder, _process_frame
from .ffmpeg_utils import extract_frames
import numpy as np

def verify_video(video_path):
    """
    Verifies if a video file is a valid YotuDrive archive.
    Returns a dictionary with metadata or raises an exception.
    """
    timestamp = int(time.time())
    unique_id = uuid.uuid4().hex[:8]
    temp_dir = os.path.join("data", "temp", f"verify_{unique_id}_{timestamp}")
    
    try:
        if not os.path.exists(video_path):
            raise FileNotFoundError(f"Video file not found: {video_path}")
            
        # 1. Extract first 10 frames (Header is usually in first 5)
        # We extract a few more just in case of redundancy or slight shifts
        extract_frames(video_path, temp_dir, limit=10)
        
        frame_files = sorted([os.path.join(temp_dir, f) for f in os.listdir(temp_dir) if f.endswith('.png')])
        
        if not frame_files:
            raise ValueError("No frames could be extracted from the video.")
            
        # 2. Use Decoder logic to parse header
        # We instantiate Decoder just to access its methods, we don't run it.
        decoder = Decoder(temp_dir, "dummy_output")
        
        # Detect Config (Block Size, ECC)
        block_size, ecc_bytes, header_copies, version = decoder.detect_config(frame_files)
        
        # Recover Header
        header_candidates = []
        frames_to_scan = min(len(frame_files), header_copies + 5)
        
        HEADER_SIZE = 1024
        
        for i in range(frames_to_scan):
            try:
                if i < len(frame_files):
                    bits = _process_frame((frame_files[i], block_size))
                    if bits is not None:
                        raw = np.packbits(bits).tobytes()
                        if len(raw) >= HEADER_SIZE and raw[:4] == b'YOTU':
                            header_candidates.append(raw[:HEADER_SIZE])
            except:
                continue
                
        if not header_candidates:
             raise ValueError("No valid YotuDrive header found in the first 10 frames.")
             
        # Majority Vote
        valid_header_bytes = decoder.recover_header_majority(header_candidates)
        
        # Parse Header
        payload_len, original_size, expected_checksum, flags, salt, _, valid_crc, filename, _ = decoder.parse_header(valid_header_bytes)
        
        # 3. Construct Report
        report = {
            "valid": True,
            "version": version,
            "filename": filename,
            "original_size": original_size,
            "payload_length": payload_len,
            "encrypted": (flags & 0x02) != 0,
            "compressed": (flags & 0x01) != 0,
            "chunked_encryption": (flags & 0x04) != 0,
            "block_size": block_size,
            "ecc_bytes": ecc_bytes,
            "header_crc_valid": valid_crc,
            "checksum_hex": expected_checksum.hex() if expected_checksum else None
        }
        
        return report
        
    finally:
        # Cleanup
        if os.path.exists(temp_dir):
            try:
                shutil.rmtree(temp_dir)
            except:
                pass
