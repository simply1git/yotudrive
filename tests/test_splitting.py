
import os
import shutil
import hashlib
import sys

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.file_utils import split_file, join_files

def get_hash(file_path):
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        while b := f.read(8192):
            h.update(b)
    return h.hexdigest()

def test_split_join():
    test_dir = "test_split_data"
    if os.path.exists(test_dir):
        shutil.rmtree(test_dir)
    os.makedirs(test_dir)
    
    # Create a dummy file (e.g. 5MB)
    original_file = os.path.join(test_dir, "original.dat")
    with open(original_file, "wb") as f:
        f.write(os.urandom(5 * 1024 * 1024))
        
    print(f"Created {original_file} (5MB)")
    original_hash = get_hash(original_file)
    
    # Split into 1MB chunks
    split_dir = os.path.join(test_dir, "parts")
    os.makedirs(split_dir)
    
    print("Splitting...")
    chunks = split_file(original_file, 1 * 1024 * 1024, output_dir=split_dir)
    print(f"Split into {len(chunks)} chunks:")
    for c in chunks:
        print(f"  {os.path.basename(c)} ({os.path.getsize(c)} bytes)")
        
    if len(chunks) != 5:
        print("Error: Expected 5 chunks.")
        return False
        
    # Join
    joined_file = os.path.join(test_dir, "joined.dat")
    print("Joining...")
    join_files(chunks, joined_file)
    
    joined_hash = get_hash(joined_file)
    
    if original_hash == joined_hash:
        print("Success: Hashes match!")
        return True
    else:
        print("Failure: Hashes do not match!")
        return False

if __name__ == "__main__":
    try:
        if test_split_join():
            print("Test Passed")
            # Cleanup
            shutil.rmtree("test_split_data")
            exit(0)
        else:
            print("Test Failed")
            exit(1)
    except Exception as e:
        print(f"Test Exception: {e}")
        exit(1)
