import os
import sys
import shutil
import time
import numpy as np
from PIL import Image

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.encoder import Encoder
from src.decoder import Decoder
from src.ffmpeg_utils import stitch_frames, extract_frames
from src.config import DEFAULT_HEADER_COPIES

def test_full_cycle():
    print("Testing Full Cycle: Encode -> Stitch -> Extract -> Decode...")
    
    # Setup directories
    test_dir = "tests/temp_full_cycle"
    input_file = os.path.join(test_dir, "test_input.txt")
    frames_dir = os.path.join(test_dir, "frames")
    video_file = os.path.join(test_dir, "output.mp4")
    extracted_dir = os.path.join(test_dir, "extracted_frames")
    output_file = os.path.join(test_dir, "restored_output.txt")
    
    if os.path.exists(test_dir):
        shutil.rmtree(test_dir)
    # os.makedirs(frames_dir)  <-- REMOVED: Encoder should create this
    os.makedirs(os.path.dirname(frames_dir), exist_ok=True) # Ensure parent exists
    os.makedirs(extracted_dir)
    
    # Create dummy input file (enough for ~5 frames at BS=4)
    # BS=4 -> 480x270 bits = 129600 bits = 16200 bytes per frame
    # Header is 1024 bytes.
    # Data payload per frame ~ 16KB.
    # Let's create 100KB file.
    data = b"Hello Full Cycle Integration Test!" * 3000 # ~100KB
    with open(input_file, 'wb') as f:
        f.write(data)
        
    print(f"Created input file: {len(data)} bytes")
    
    # 1. Encode with Block Size 4, ECC 10
    print("\n1. Encoding...")
    # Using BS=4 for faster processing but still testing block logic
    encoder = Encoder(input_file, frames_dir, block_size=4, ecc_bytes=10)
    encoder.run()
    
    # Verify Header Copies
    print(f"\n2. Verifying Header Copies (Expect {DEFAULT_HEADER_COPIES})...")
    for i in range(DEFAULT_HEADER_COPIES):
        frame_path = os.path.join(frames_dir, f"frame_{i:04d}.png")
        if not os.path.exists(frame_path):
            print(f"FAIL: Header frame {i} missing!")
            return
    print("  Header frames exist.")

    # 3. Stitch to Video
    print("\n3. Stitching to Video (ffmpeg)...")
    try:
        stitch_frames(frames_dir, video_file, framerate=30)
        if os.path.exists(video_file):
            print(f"  Video created: {video_file} ({os.path.getsize(video_file)} bytes)")
        else:
            print("FAIL: Video file not created!")
            return
    except Exception as e:
        print(f"FAIL: Stitching failed: {e}")
        return

    # 4. Extract Frames from Video
    print("\n4. Extracting Frames from Video (ffmpeg)...")
    try:
        extract_frames(video_file, extracted_dir)
        extracted_files = os.listdir(extracted_dir)
        print(f"  Extracted {len(extracted_files)} frames.")
        if len(extracted_files) == 0:
            print("FAIL: No frames extracted!")
            return
    except Exception as e:
        print(f"FAIL: Extraction failed: {e}")
        return
        
    # Check frame names in extracted dir
    # Should be frame_0000.png, frame_0001.png, etc.
    if not os.path.exists(os.path.join(extracted_dir, "frame_0000.png")):
        print("FAIL: Extracted frames do not start at 0! (frame_0000.png missing)")
        # List first few files
        print("First 5 files:", sorted(extracted_files)[:5])
        return
    else:
        print("  frame_0000.png found (0-based indexing confirmed).")

    # 5. Decode
    print("\n5. Decoding from Extracted Frames...")
    decoder = Decoder(extracted_dir, output_file)
    try:
        decoder.run()
    except Exception as e:
        print(f"FAIL: Decoding failed: {e}")
        import traceback
        traceback.print_exc()
        return

    # 6. Verify Output
    print("\n6. Verifying Output...")
    if not os.path.exists(output_file):
        print("FAIL: Output file not created.")
        return
        
    with open(output_file, 'rb') as f:
        restored_data = f.read()
        
    if restored_data == data:
        print("SUCCESS! Full cycle test passed.")
    else:
        print("FAIL: Data mismatch.")
        print(f"Original: {len(data)} bytes")
        print(f"Restored: {len(restored_data)} bytes")
        # Check first few bytes
        print(f"Original start: {data[:20]}")
        print(f"Restored start: {restored_data[:20]}")

if __name__ == "__main__":
    test_full_cycle()
