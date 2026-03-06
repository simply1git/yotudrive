import os
import sys
import shutil
import numpy as np
from PIL import Image

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.encoder import Encoder
from src.decoder import Decoder
from src.config import DEFAULT_HEADER_COPIES

def test_header_redundancy():
    print("Testing Header Redundancy...")
    
    # Setup directories
    test_dir = "tests/temp_redundancy"
    input_file = os.path.join(test_dir, "test_input.txt")
    frames_dir = os.path.join(test_dir, "frames")
    output_file = os.path.join(test_dir, "restored_output.txt")
    
    if os.path.exists(test_dir):
        shutil.rmtree(test_dir)
    os.makedirs(frames_dir)
    
    # Create dummy input file (enough for 2-3 frames at BS=8)
    # BS=8 -> 240x135 bits = 32400 bits = 4050 bytes per frame
    # Header is 1024 bytes.
    # Data payload per frame ~ 4050 bytes.
    # Let's create 10KB file.
    data = b"Hello Header Redundancy!" * 500 # ~12KB
    with open(input_file, 'wb') as f:
        f.write(data)
        
    print(f"Created input file: {len(data)} bytes")
    
    # 1. Encode with Block Size 8, ECC 10
    print("\n1. Encoding...")
    encoder = Encoder(input_file, frames_dir, block_size=8, ecc_bytes=10)
    encoder.run()
    
    # Verify Header Copies
    print(f"\n2. Verifying Header Copies (Expect {DEFAULT_HEADER_COPIES})...")
    for i in range(DEFAULT_HEADER_COPIES):
        frame_path = os.path.join(frames_dir, f"frame_{i:04d}.png")
        if not os.path.exists(frame_path):
            print(f"FAIL: Header frame {i} missing!")
            return
        else:
            print(f"  Header frame {i} exists.")
            
    # Verify Body Frames
    body_frame_start = DEFAULT_HEADER_COPIES
    if not os.path.exists(os.path.join(frames_dir, f"frame_{body_frame_start:04d}.png")):
         print("FAIL: Body frame missing!")
         return
    print("  Body frames exist.")

    # 3. Corrupt Multiple Header Frames to test Majority Vote
    print("\n3. Corrupting header frames...")
    
    # Corrupt frame 0 (Delete)
    os.remove(os.path.join(frames_dir, "frame_0000.png"))
    print("  Deleted frame_0000.png")
    
    # Corrupt frame 1 (Corrupt Byte 10 - Payload Length - force to 0)
    # Byte 10 is bits 80-87. 
    # At Block Size 8, this is Block 10 (if we count bytes). 
    # Wait, bits 0-31 are YOTU. 32-39 Version. 40-47 Flags. 48-55 BlockSize. 56-63 ECC. 64-127 PayloadLen.
    # So Payload Length starts at Bit 64.
    # Bit 64 is Block 64.
    # X = 64 * 8 = 512. Y = 0.
    # Corrupt a 8x8 block at (512, 0) to Black (0)
    img1_path = os.path.join(frames_dir, "frame_0001.png")
    img1 = Image.open(img1_path)
    pixels1 = img1.load()
    for x in range(512, 520):
        for y in range(8):
            pixels1[x, y] = 0 # Force Black (Bit 0)
    img1.save(img1_path)
    print("  Corrupted frame_0001.png (Bit 64 forced to 0)")
    
    # Corrupt frame 2 (Corrupt Bit 64 - force to 1/White)
    img2_path = os.path.join(frames_dir, "frame_0002.png")
    img2 = Image.open(img2_path)
    pixels2 = img2.load()
    for x in range(512, 520):
        for y in range(8):
            pixels2[x, y] = 255 # Force White (Bit 1)
    img2.save(img2_path)
    print("  Corrupted frame_0002.png (Bit 64 forced to 1)")
    
    # Frames 3 & 4 are intact.
    # Majority Vote should see: 0, 1, Correct, Correct.
    # If Correct is 0, then 0 wins (3 vs 1).
    # If Correct is 1, then 1 wins (3 vs 1).
    # Wait, if Correct is 0, Frame 1 agrees.
    # If Correct is 1, Frame 2 agrees.
    # So we need to corrupt it to the OPPOSITE of correct to prove it fixes it.
    # But we don't know what correct is easily here (it depends on data).
    # But blindly forcing 0 and 1 ensures at least one is wrong.
    # And since we have 2 other pure copies, the Correct value will have at least 2 votes.
    # The Wrong value will have at most 1 vote (unless Correct was 0, then 0 has 2 votes).
    # In any case, Majority Vote should pick the majority.
    
    # 4. Decode
    print("\n4. Decoding (Should use backup header)...")
    decoder = Decoder(frames_dir, output_file)
    try:
        decoder.run()
    except Exception as e:
        print(f"FAIL: Decoding failed: {e}")
        import traceback
        traceback.print_exc()
        return

    # 5. Verify Output
    print("\n5. Verifying Output...")
    if not os.path.exists(output_file):
        print("FAIL: Output file not created.")
        return
        
    with open(output_file, 'rb') as f:
        restored_data = f.read()
        
    if restored_data == data:
        print("SUCCESS! Data restored correctly despite missing frame_0000.")
    else:
        print("FAIL: Data mismatch.")
        print(f"Original: {len(data)} bytes")
        print(f"Restored: {len(restored_data)} bytes")

if __name__ == "__main__":
    test_header_redundancy()
