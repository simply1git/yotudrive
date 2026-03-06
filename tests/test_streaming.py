
import os
import sys
import hashlib
import shutil
import time

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.encoder import Encoder
from src.decoder import Decoder
from src.config import *

def create_test_file(filename, size_mb):
    print(f"Creating test file {filename} of size {size_mb}MB...")
    with open(filename, 'wb') as f:
        f.write(os.urandom(size_mb * 1024 * 1024))
    print("Test file created.")

def calculate_md5(filename):
    md5 = hashlib.md5()
    with open(filename, 'rb') as f:
        for chunk in iter(lambda: f.read(4096), b""):
            md5.update(chunk)
    return md5.digest()

def test_streaming_pipeline():
    # Setup paths
    test_dir = "test_streaming_data"
    if os.path.exists(test_dir):
        shutil.rmtree(test_dir)
    os.makedirs(test_dir)
    
    input_file = os.path.join(test_dir, "large_input.dat")
    output_frames_dir = os.path.join(test_dir, "frames")
    restored_file = os.path.join(test_dir, "restored_large_input.dat")
    
    # 1. Create a "large" file (50MB is enough to test streaming logic without taking forever)
    # Actually, 50MB might take a while to encode/decode with python RS.
    # Let's start with 5MB to verify correctness first.
    create_test_file(input_file, 5)
    
    original_md5 = calculate_md5(input_file)
    print(f"Original MD5: {original_md5.hex()}")
    
    # 2. Encode (Streaming)
    print("\n--- Encoding ---")
    print(f"Encoder imported from: {Encoder.__module__}")
    import inspect
    encoder_file = inspect.getfile(Encoder)
    print(f"Encoder file: {encoder_file}")
    
    # Debug: Print content of encoder.py around run method
    with open(encoder_file, 'r') as f:
        content = f.readlines()
        start_line = 78 # run method starts around 79
        print("--- Encoder Source Check ---")
        for i in range(start_line, start_line + 20):
            if i < len(content):
                print(f"{i+1}: {content[i].rstrip()}")
        print("----------------------------")
        
    # Using password to trigger encryption streaming logic
    encoder = Encoder(input_file, output_frames_dir, password="testpassword", threads=4)
    print(f"Encoder dir: {dir(encoder)}")
    encoder.run()
    
    # 3. Decode (Streaming)
    print("\n--- Decoding ---")
    decoder = Decoder(output_frames_dir, restored_file, password="testpassword", threads=4)
    decoder.run()
    
    # 4. Verify
    if not os.path.exists(restored_file):
        print("Error: Restored file not found!")
        sys.exit(1)
        
    restored_md5 = calculate_md5(restored_file)
    print(f"Restored MD5: {restored_md5.hex()}")
    
    if original_md5 == restored_md5:
        print("\nSUCCESS: Streaming Pipeline Verified!")
    else:
        print("\nFAILURE: MD5 Mismatch!")
        sys.exit(1)

if __name__ == "__main__":
    test_streaming_pipeline()
