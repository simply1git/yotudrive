
import os
import shutil
import hashlib
import time
import sys

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.encoder import Encoder
from src.decoder import Decoder
from src.config import DEFAULT_BLOCK_SIZE, DEFAULT_ECC_BYTES

def create_large_file(filepath, size_mb):
    """Creates a file with random data of specified size in MB."""
    print(f"Creating {size_mb}MB test file at {filepath}...")
    with open(filepath, 'wb') as f:
        # Write in 1MB chunks to be memory efficient
        chunk = os.urandom(1024 * 1024)
        for _ in range(size_mb):
            f.write(chunk)

def calculate_md5(filepath):
    md5 = hashlib.md5()
    with open(filepath, 'rb') as f:
        for chunk in iter(lambda: f.read(4096 * 1024), b""):
            md5.update(chunk)
    return md5.hexdigest()

def progress_callback(pct, stage):
    print(f"[{stage}] Progress: {pct:.1f}%")

def test_streaming_pipeline():
    # Setup paths
    base_dir = os.path.dirname(os.path.abspath(__file__))
    test_dir = os.path.join(base_dir, "temp_large_test")
    input_file = os.path.join(test_dir, "large_input.bin")
    frames_dir = os.path.join(test_dir, "frames")
    restored_file = os.path.join(test_dir, "large_restored.bin")
    
    # Clean/Create dirs
    if os.path.exists(test_dir):
        shutil.rmtree(test_dir)
    os.makedirs(test_dir)
    os.makedirs(frames_dir)
    
    # 1. Create Test File (10MB to trigger multiple chunks of 4MB pipeline)
    create_large_file(input_file, 10)
    original_md5 = calculate_md5(input_file)
    print(f"Original MD5: {original_md5}")
    
    # 2. Encode
    print("\n=== STARTING ENCODER ===")
    encoder = Encoder(
        input_file=input_file,
        output_dir=frames_dir,
        password="testpassword",
        progress_callback=lambda pct: progress_callback(pct, "ENCODER"),
        block_size=DEFAULT_BLOCK_SIZE,
        ecc_bytes=DEFAULT_ECC_BYTES,
        threads=4
    )
    
    start_time = time.time()
    encoder.run()
    encode_time = time.time() - start_time
    print(f"Encoding completed in {encode_time:.2f}s")
    
    # Check if frames were created
    frames = os.listdir(frames_dir)
    print(f"Created {len(frames)} frames.")
    if len(frames) == 0:
        print("ERROR: No frames created!")
        return False

    # 3. Decode
    print("\n=== STARTING DECODER ===")
    decoder = Decoder(
        input_dir=frames_dir,
        output_file=restored_file,
        password="testpassword",
        progress_callback=lambda pct: progress_callback(pct, "DECODER"),
        threads=4
    )
    
    start_time = time.time()
    decoder.run()
    decode_time = time.time() - start_time
    print(f"Decoding completed in {decode_time:.2f}s")
    
    # 4. Verify
    if not os.path.exists(restored_file):
        print("ERROR: Restored file not found!")
        return False
        
    restored_md5 = calculate_md5(restored_file)
    print(f"Restored MD5: {restored_md5}")
    
    if original_md5 == restored_md5:
        print("\nSUCCESS: MD5 Checksums match!")
        return True
    else:
        print("\nFAILURE: MD5 Checksums do NOT match!")
        return False

if __name__ == "__main__":
    try:
        success = test_streaming_pipeline()
        if success:
            # Cleanup
            shutil.rmtree(os.path.join(os.path.dirname(os.path.abspath(__file__)), "temp_large_test"))
            sys.exit(0)
        else:
            sys.exit(1)
    except Exception as e:
        print(f"EXCEPTION: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
