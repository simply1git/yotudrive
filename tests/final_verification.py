
import os
import shutil
import hashlib
import sys
import time

# Ensure src is in path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.file_utils import split_file, auto_join_restored_files

def get_file_hash(filepath):
    md5 = hashlib.md5()
    with open(filepath, 'rb') as f:
        for chunk in iter(lambda: f.read(4096), b""):
            md5.update(chunk)
    return md5.hexdigest()

def test_full_cycle():
    print("=== STARTING END-TO-END VERIFICATION ===")
    
    # 1. Setup
    test_dir = "tests/e2e_temp"
    if os.path.exists(test_dir):
        shutil.rmtree(test_dir)
    os.makedirs(test_dir)
    
    original_file = os.path.join(test_dir, "large_file.bin")
    
    # 2. Create Dummy Large File (e.g. 15MB)
    print("Creating dummy file (15MB)...")
    with open(original_file, "wb") as f:
        f.write(os.urandom(15 * 1024 * 1024))
        
    original_hash = get_file_hash(original_file)
    print(f"Original Hash: {original_hash}")
    
    # 3. Split File (e.g. 5MB chunks -> 3 parts)
    print("Splitting file into 5MB chunks...")
    chunks = split_file(original_file, chunk_size=5 * 1024 * 1024)
    print(f"Generated {len(chunks)} chunks: {[os.path.basename(c) for c in chunks]}")
    
    if len(chunks) != 3:
        print("ERROR: Expected 3 chunks!")
        return False
        
    # 4. Simulate "Restoration"
    # In a real scenario, these chunks would be encoded to video, uploaded, downloaded, and decoded.
    # Here we assume the decoding part worked perfectly and we have the restored chunks.
    # We will rename them slightly to mimic the restoration output if needed, 
    # but usually the decoder outputs the exact filename if possible.
    # Let's move them to a "restored" folder.
    
    restore_dir = os.path.join(test_dir, "restored_output")
    os.makedirs(restore_dir)
    
    simulated_restored_files = []
    for chunk in chunks:
        dest = os.path.join(restore_dir, os.path.basename(chunk))
        shutil.copy(chunk, dest)
        simulated_restored_files.append(dest)
        
    # Shuffle list to ensure sorting works
    import random
    random.shuffle(simulated_restored_files)
    print(f"Simulating restored files (shuffled): {[os.path.basename(f) for f in simulated_restored_files]}")
    
    # 5. Auto-Join
    print("Running Auto-Join...")
    
    def log(msg):
        print(f"[LOG] {msg}")
        
    def progress(p, t):
        pass # print(f"[PROG] {p}/{t}")
        
    final_files = auto_join_restored_files(
        simulated_restored_files,
        log_callback=log,
        progress_callback=progress,
        auto_cleanup=False # Keep parts for debug if needed
    )
    
    print(f"Auto-Join returned: {final_files}")
    
    if len(final_files) != 1:
        print("ERROR: Expected 1 final file!")
        return False
        
    restored_file = final_files[0]
    
    # 6. Verify
    print("Verifying hash...")
    restored_hash = get_file_hash(restored_file)
    print(f"Restored Hash: {restored_hash}")
    
    if original_hash == restored_hash:
        print("SUCCESS: Hashes match!")
        
        # Cleanup
        try:
            shutil.rmtree(test_dir)
            print("Cleanup complete.")
        except:
            pass
        return True
    else:
        print("FAILURE: Hashes do not match!")
        return False

if __name__ == "__main__":
    success = test_full_cycle()
    if success:
        sys.exit(0)
    else:
        sys.exit(1)
