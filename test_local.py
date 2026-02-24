import os
import shutil
import hashlib
from src.encoder import Encoder
from src.decoder import Decoder

INPUT_FILE = r"data\input\test.txt"
# Instead of a single video file, we use a directory for frames
VIDEO_FRAMES_DIR = r"data\temp\frames"
OUTPUT_FILE = r"data\output\test_recovered.txt"

def get_file_hash(filepath):
    """Calculates MD5 hash of a file."""
    hasher = hashlib.md5()
    with open(filepath, 'rb') as f:
        buf = f.read()
        hasher.update(buf)
    return hasher.hexdigest()

def main():
    # Ensure directories exist
    os.makedirs(os.path.dirname(INPUT_FILE), exist_ok=True)
    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    
    # Clean up previous run
    if os.path.exists(VIDEO_FRAMES_DIR):
        shutil.rmtree(VIDEO_FRAMES_DIR)
    os.makedirs(VIDEO_FRAMES_DIR, exist_ok=True)

    print("=== YotuDrive Local Test (Frame Mode) ===")
    
    # 1. Encode
    print(f"\n[1] Encoding {INPUT_FILE} -> {VIDEO_FRAMES_DIR}")
    encoder = Encoder(INPUT_FILE, VIDEO_FRAMES_DIR)
    encoder.run()
    
    # 2. Decode
    print(f"\n[2] Decoding {VIDEO_FRAMES_DIR} -> {OUTPUT_FILE}")
    decoder = Decoder(VIDEO_FRAMES_DIR, OUTPUT_FILE)
    decoder.run()
    
    # 3. Verify
    print("\n[3] Verifying Integrity...")
    if not os.path.exists(OUTPUT_FILE):
        print("FAIL: Output file not created.")
        return

    original_hash = get_file_hash(INPUT_FILE)
    recovered_hash = get_file_hash(OUTPUT_FILE)
    
    print(f"Original Hash:  {original_hash}")
    print(f"Recovered Hash: {recovered_hash}")
    
    if original_hash == recovered_hash:
        print("\nSUCCESS: File recovered perfectly! 🎉")
    else:
        print("\nFAIL: Hashes do not match. Data corruption occurred.")

if __name__ == "__main__":
    main()
