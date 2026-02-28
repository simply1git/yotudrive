import reedsolo
import numpy as np
from PIL import Image
from .rs_manager import RSManager
from .config import *
import os
import math
import struct
import hashlib
import zlib
from tqdm import tqdm
import concurrent.futures
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import base64
import collections
import time

# Helper function for RS Encoding (Parallel Step 1)
def _rs_encode_chunk(args):
    data_chunk, ecc_bytes = args
    n = 255
    k = n - ecc_bytes
    # Initialize codec
    # Note: creating RSCodec is cheap? If not, we might want to cache it or pass it?
    # It precomputes tables. It might be slightly expensive.
    # But this runs in a worker process that might be reused.
    # We can use a global cache in the worker?
    # For now, let's assume it's fast enough or optimization is for later.
    rsc = reedsolo.RSCodec(ecc_bytes)
    
    # Process blocks
    encoded_chunk = b''
    # We expect data_chunk to be multiple of k
    # But if it's the last chunk, it might be padded by the generator?
    # Or we handle padding here?
    # The generator should handle padding to ensure alignment.
    
    for i in range(0, len(data_chunk), k):
        block = data_chunk[i:i+k]
        # Pad last block if necessary (should be handled by caller for alignment, but safety check)
        if len(block) < k:
             block += b'\x00' * (k - len(block))
        encoded_chunk += rsc.encode(block)
    return encoded_chunk

# Helper function for parallel frame generation (must be picklable)
def _render_and_save_frame(args):
    index, frame_bits, output_dir, block_size = args
    
    # Scale up to block size
    # Repeat rows and cols
    frame_scaled = frame_bits.repeat(block_size, axis=0).repeat(block_size, axis=1)
    
    # Convert to 0/255
    frame_arr = (frame_scaled * 255).astype(np.uint8)
    
    # Create PIL Image
    img = Image.fromarray(frame_arr, mode='L') # L = 8-bit pixels, black and white
    
    # Save Frame
    frame_path = os.path.join(output_dir, f"frame_{index:08d}.png")
    img.save(frame_path)
    return index

class Encoder:
    def __init__(self, input_file, output_dir, password=None, progress_callback=None, 
                 block_size=DEFAULT_BLOCK_SIZE, ecc_bytes=DEFAULT_ECC_BYTES, threads=None, check_cancel=None):
        """
        :param input_file: Path to the file to encode.
        :param output_dir: Directory where video frames (PNGs) will be saved.
        :param password: Optional password for encryption.
        :param progress_callback: Function to call with progress updates (0-100).
        :param block_size: Size of each pixel block (e.g. 1, 2, 4).
        :param ecc_bytes: Number of Reed-Solomon ECC bytes per 255-byte block.
        :param threads: Number of parallel threads to use.
        :param check_cancel: Function to check for cancellation (should return True or raise Exception).
        """
        self.input_path = input_path
        self.output_dir = os.path.abspath(output_dir)
        self.ecc_bytes = ecc_bytes
        self.compression = compression
        self.password = password
        self.progress_callback = progress_callback
        self.block_size = block_size
        self.threads = threads
        self.check_cancel = check_cancel
        self.rs_manager = RSManager(ecc_bytes) # Will be re-initialized in run() with correct ECC settings

    def read_file(self):
        """Reads the input file as binary."""
        with open(self.input_path, 'rb') as f:
            return f.read()
    
    def calculate_checksum(self):
        """Calculates MD5 checksum of the file (streaming)."""
        md5 = hashlib.md5()
        with open(self.input_file, 'rb') as f:
            for chunk in iter(lambda: f.read(4096 * 1024), b""):
                md5.update(chunk)
        return md5.digest()

    def get_file_chunks(self, chunk_size):
        """Yields chunks of the file."""
        with open(self.input_file, 'rb') as f:
            while True:
                data = f.read(chunk_size)
                if not data:
                    break
                yield data

    def run(self):
        print(f"Processing {self.input_file}...")
        
        # Create output directory early
        print(f"CWD: {os.getcwd()}")
        print(f"Output Dir: {self.output_dir}")
        os.makedirs(self.output_dir, exist_ok=True)
        if os.path.exists(self.output_dir):
            print(f"Directory {self.output_dir} exists.")
        else:
            print(f"Directory {self.output_dir} DOES NOT EXIST after makedirs!")
            
        print(f"Created output directory: {self.output_dir}")
        
        # 1. Pre-calculation (Streaming)
        original_size = os.path.getsize(self.input_file)
        print(f"Original Size: {original_size} bytes")
        
        print("Calculating checksum...")
        checksum = self.calculate_checksum()
        
        # Initialize RS Manager
        self.rs_manager = RSManager(n=RS_BLOCK_SIZE, k=RS_BLOCK_SIZE - self.ecc_bytes)
        data_block_size = RS_BLOCK_SIZE - self.ecc_bytes
        
        # Calculate Payload Length (Compressed + Encrypted + ECC)
        # Note: We can't know the EXACT compressed size without compressing.
        # For large files, we MUST stream compression.
        # But to create the header, we need the payload length.
        # This is a Chicken-and-Egg problem for streaming.
        # Solution:
        # 1. Use a streamable format where header doesn't strictly require total payload length 
        #    OR use a placeholder in header and update it later (impossible for video).
        # 2. Store payload length as 0 or estimate? No, decoder needs it.
        # 3. Two-pass approach:
        #    Pass 1: Read -> Compress -> Encrypt -> Count Bytes (discard output).
        #    Pass 2: Read -> Compress -> Encrypt -> ECC -> Write Frames.
        # This is slow (reads file twice) but memory efficient.
        # For 70GB, reading twice is better than crashing.
        
        print("Pass 1: Calculating payload size (Streaming compression)...")
        payload_len = 0
        
        # We need to replicate the exact transformation chain to get accurate size
        # Chain: Read -> Compress (zlib stream) -> Encrypt (Fernet stream) -> ECC (RS)
        
        # Zlib Compressor
        compressor = zlib.compressobj(level=1) # Faster level for large files? Or 9? Let's use 1 for speed on 70GB.
        # Note: User might want level 9. Let's stick to default or make it configurable. 
        # For now, let's use level 6 (default) for balance.
        compressor = zlib.compressobj(level=6)
        
        # Encryption
        encryptor = None
        salt = b'\x00' * 16
        if self.password:
            salt = os.urandom(16)
            key = self.derive_key(self.password, salt)
            # Fernet does not support streaming natively easily (it has HMAC and padding).
            # It expects full blocks.
            # However, Fernet is built on AES-CBC with PKCS7 padding in a specific format.
            # To stream 70GB, we shouldn't use Fernet.encrypt(whole_data).
            # We should use cryptography's Cipher context.
            # But to keep compatibility with existing Decoder (which uses Fernet),
            # we must check if we can stream Fernet. 
            # Fernet format: Version | Timestamp | IV | Ciphertext | HMAC
            # It's not designed for streaming huge files.
            # STARTUP WARNING: For 70GB, standard Fernet is not suitable as it authenticates the *whole* message.
            # We will use it on *chunks*? No, that would increase size significantly.
            # We should switch to a streaming-friendly encryption (e.g. AES-GCM or CTR) or apply Fernet on chunks.
            # Applying Fernet on chunks means we have overhead per chunk.
            # If chunk is large (e.g. 1MB), overhead is negligible.
            # Let's use Fernet on 1MB chunks!
            # This changes the format. The Decoder must know this.
            # Wait, the current implementation does: f.encrypt(compressed_data).
            # If we change to chunk-based encryption, we break compatibility with V3/V4 decoders 
            # UNLESS we introduce a V5 header flag "Chunked Encryption".
            
            # Given the requirement "handle larger files", we MUST change the strategy.
            # Let's stick to the current logic but apply it block-wise.
            # But standard Fernet is for the whole blob.
            # If we simply encrypt 1MB chunks, the output is a sequence of Fernet tokens.
            # Payload = Token1 + Token2 + ...
            # Decoder reads Token1, decrypts, Token2, decrypts...
            # We need to define a chunk size.
            
            f = Fernet(key)
        
        # Let's define a processing chunk size for the pipeline
        PIPELINE_CHUNK_SIZE = 4 * 1024 * 1024 # 4MB
        
        # We need to calculate exact payload size.
        # Since we are using Fernet on chunks, the size is deterministic.
        # Fernet size = Input + Padding + Overhead (Version+Timestamp+IV+HMAC = 1+8+16+32 = 57 bytes?)
        # Fernet uses AES-128-CBC with PKCS7.
        # Output size = ((Input + 16) // 16) * 16 + Overhead?
        # Actually Fernet.encrypt result is Base64 encoded! 
        # Base64 expansion is ~4/3.
        # This is huge overhead and CPU cost for 70GB.
        # But we must stick to the "Robust" promise.
        
        # Simulating Pass 1 size calculation:
        # If we use Zlib stream, we don't know the size until we finish.
        # So we really have to run the compressor.
        
        # Let's do Pass 1.
        compressed_size = 0
        encrypted_size = 0
        final_payload_size = 0
        
        # For the sake of time, we can assume payload_len is needed for the header.
        # Is it?
        # Header: payload_length (8 bytes).
        # Yes.
        
        # Optimization:
        # Can we write the header *after* encoding?
        # No, the header is at the start of the video (Frame 0-4).
        # We need it first.
        
        # Okay, Pass 1 is unavoidable if we want exact progress and header at start.
        # We will count bytes.
        
        # NOTE: For 70GB, we might skip zlib compression to save time?
        # No, usually desirable.
        # We will implement a "Fast Mode" later? No, robust first.
        
        # Generator for Pass 1
        def pass1_stream():
            nonlocal compressed_size
            processed_bytes = 0
            
            pbar = None
            if not self.progress_callback:
                 try:
                    pbar = tqdm(total=original_size, unit='B', unit_scale=True, desc="Pass 1")
                 except:
                    pass

            with open(self.input_file, 'rb') as f:
                while True:
                    if self.check_cancel: self.check_cancel()
                    chunk = f.read(PIPELINE_CHUNK_SIZE)
                    if not chunk:
                        break
                    
                    processed_bytes += len(chunk)
                    if self.progress_callback and processed_bytes % (PIPELINE_CHUNK_SIZE * 5) == 0:
                         pct = min(50, (processed_bytes / original_size) * 50)
                         self.progress_callback(pct)
                    
                    if pbar:
                        pbar.update(len(chunk))

                    # Compress
                    c_chunk = compressor.compress(chunk)
                    if c_chunk:
                        compressed_size += len(c_chunk)
                        yield c_chunk
                
                # Flush compressor
                c_chunk = compressor.flush()
                if c_chunk:
                    compressed_size += len(c_chunk)
                    yield c_chunk
            
            if pbar:
                pbar.close()
                    
        # Iterate Pass 1 to calculate size
        # We need to account for Encryption and ECC expansion
        
        chunk_accumulator = b''
        # Fernet overhead calculation
        # If we use Fernet on chunks, we need to know how we split the compressed stream.
        # Let's split compressed stream into fixed chunks for encryption?
        # Yes.
        ENCRYPTION_CHUNK_SIZE = 1 * 1024 * 1024 # 1MB chunks for encryption
        
        for data in pass1_stream():
            if self.password:
                # Accumulate data to encrypt in chunks
                chunk_accumulator += data
                while len(chunk_accumulator) >= ENCRYPTION_CHUNK_SIZE:
                    to_encrypt = chunk_accumulator[:ENCRYPTION_CHUNK_SIZE]
                    chunk_accumulator = chunk_accumulator[ENCRYPTION_CHUNK_SIZE:]
                    
                    # Encrypt
                    # enc = f.encrypt(to_encrypt) 
                    # We don't need to actually encrypt, just know the size
                    # Fernet size formula:
                    # PKCS7 pad to 16 bytes: len + (16 - len%16)
                    # + 57 bytes overhead (approx)
                    # Base64 encode: ceil(binary_len / 3) * 4
                    
                    # To be safe/exact, we should actually run it or use formula
                    # Let's run it for correctness, but it's slow.
                    # Formula is better.
                    # Fernet implementation details:
                    # 1. Padding: pad(data, 128) -> multiple of 16 bytes
                    # 2. IV (16) + Ciphertext + HMAC (32)
                    # 3. Base64url
                    
                    # Padded length
                    pad_len = 16 - (len(to_encrypt) % 16)
                    padded_size = len(to_encrypt) + pad_len
                    bin_size = 1 + 8 + 16 + padded_size + 32 # Version(1)+TS(8)+IV(16)+Cipher+HMAC(32)
                    b64_size = 4 * ((bin_size + 2) // 3) # Base64
                    
                    encrypted_size += b64_size
            else:
                encrypted_size += len(data)
                
        # Process remaining accumulator
        if self.password and chunk_accumulator:
             to_encrypt = chunk_accumulator
             pad_len = 16 - (len(to_encrypt) % 16)
             padded_size = len(to_encrypt) + pad_len
             bin_size = 1 + 8 + 16 + padded_size + 32
             b64_size = 4 * ((bin_size + 2) // 3)
             encrypted_size += b64_size
             
        # Now we have encrypted_size (which is the input to ECC)
        # ECC adds parity bytes.
        # RS Block: 255 bytes total = (255 - ecc) data + ecc parity
        # Output size = ceil(encrypted_size / data_block_size) * 255
        
        num_rs_blocks = math.ceil(encrypted_size / data_block_size)
        # payload_len in header should be the size BEFORE ECC (Encrypted/Compressed size)
        # The Decoder uses this to calculate expected ECC blocks.
        payload_len = encrypted_size
        total_encoded_len = num_rs_blocks * 255
        
        print(f"Calculated Payload Length (Header): {payload_len} bytes")
        print(f"Total Encoded Length (Post-ECC): {total_encoded_len} bytes")
        
        # 2. Prepare Header
        flags = 1 # Compressed
        if self.password:
            flags |= 2 # Encrypted + Chunked (Implicit for large files? No, we need a flag for chunked)
            # Wait, if we use chunked encryption, the decoder MUST know.
            # Standard decoder expects one blob.
            # We must set a new flag or version.
            # Let's use Version 5 for "Streaming/Large File" support.
            pass
            
        # Version 5: Supports Chunked Encryption
        VERSION = 5
        
        # Header creation (modified for V5 if needed, or V4 if compatible)
        # If we just change internal processing but result is a stream of bytes,
        # does the decoder care?
        # Yes, if encryption is chunked, decoder needs to decrypt chunks.
        # If not encrypted, it's just a zlib stream (compatible).
        # So only Encryption changes format.
        
        # If encrypted, we set a flag.
        # Let's use Bit 2 of flags for "Chunked Encryption".
        if self.password:
            flags |= 4 # Bit 2 = Chunked Encryption
            
        filename = os.path.basename(self.input_file)
        
        # We need to update create_header to accept Version
        header = self.create_header(payload_len, original_size, checksum, flags, salt, filename, version=VERSION)
        
        # 3. Generate Header Frames
        data_width = VIDEO_WIDTH // self.block_size
        data_height = VIDEO_HEIGHT // self.block_size
        bits_per_frame = data_width * data_height
        
        header_bits = self.bytes_to_bits(header)
        
        # Pad header bits to fit exactly one frame
        padding_needed = bits_per_frame - len(header_bits)
        if padding_needed > 0:
            header_frame_bits = np.concatenate([header_bits, np.zeros(padding_needed, dtype=np.uint8)])
        else:
            header_frame_bits = header_bits[:bits_per_frame]
            
        header_frame_bits = header_frame_bits.reshape((data_height, data_width))
        
        # 4. Pass 2: Processing and Encoding
        print("Pass 2: Encoding and Rendering...")
        
        # Re-initialize compressor for Pass 2
        compressor = zlib.compressobj(level=6)
        
        # Generator for Encoded Data Stream (ECC output)
        def data_stream():
            i = 0
            chunk_acc = b''
            # Pass 2 File Reading
            with open(self.input_file, 'rb') as infile:
                while True:
                    if self.check_cancel: self.check_cancel()
                    file_chunk = infile.read(PIPELINE_CHUNK_SIZE)
                    if not file_chunk:
                        break
                    
                    # Compress
                    c_chunk = compressor.compress(file_chunk)
                    
                    # Encrypt Logic
                    if self.password:
                        chunk_acc += c_chunk
                        while len(chunk_acc) >= ENCRYPTION_CHUNK_SIZE:
                            to_enc = chunk_acc[:ENCRYPTION_CHUNK_SIZE]
                            chunk_acc = chunk_acc[ENCRYPTION_CHUNK_SIZE:]
                            # Encrypt
                            enc = f.encrypt(to_enc)
                            yield enc
                            i += 1
                    else:
                        if c_chunk:
                            yield c_chunk
                            
                # Flush Compressor
                c_chunk = compressor.flush()
                if self.password:
                    chunk_acc += c_chunk
                    while len(chunk_acc) >= ENCRYPTION_CHUNK_SIZE:
                        to_enc = chunk_acc[:ENCRYPTION_CHUNK_SIZE]
                        chunk_acc = chunk_acc[ENCRYPTION_CHUNK_SIZE:]
                        enc = f.encrypt(to_enc)
                        yield enc
                        i += 1
                    
                    if chunk_acc:
                        enc = f.encrypt(chunk_acc)
                        yield enc
                        i += 1
                else:
                    if c_chunk:
                        yield c_chunk

        # We need an iterator that yields BITS for frames.
        # Data Stream -> RS Encode -> Bits -> Frames
        
        # RS Encoder needs blocks of `data_block_size`.
        # We need to buffer data_stream output to feed RS.
        
        # New Logic for Parallel Pipeline
        data_block_size = 255 - self.ecc_bytes
        # Calculate optimal chunk size for RS workers (approx 1MB to keep latency low but throughput high)
        # Must be multiple of data_block_size
        blocks_per_chunk = max(1, (1024 * 1024) // data_block_size) 
        RS_WORKER_CHUNK_SIZE = blocks_per_chunk * data_block_size
        
        def buffered_rs_input_generator():
            buffer = b''
            for chunk in data_stream():
                buffer += chunk
                while len(buffer) >= RS_WORKER_CHUNK_SIZE:
                    yield (buffer[:RS_WORKER_CHUNK_SIZE], self.ecc_bytes)
                    buffer = buffer[RS_WORKER_CHUNK_SIZE:]
            if buffer:
                remainder = len(buffer) % data_block_size
                if remainder > 0:
                    buffer += b'\x00' * (data_block_size - remainder)
                yield (buffer, self.ecc_bytes)

        # Execution
        # We need to manually handle the header frames first
        # Write header frames
        for i in range(DEFAULT_HEADER_COPIES):
            _render_and_save_frame((i, header_frame_bits, self.output_dir, self.block_size))

        # Parallel Process Body
        max_workers = max(1, os.cpu_count() - 1)
        if hasattr(self, 'threads') and self.threads:
             max_workers = self.threads
             
        print(f"Rendering Body Frames with {max_workers} workers...")
        
        estimated_frames = math.ceil((total_encoded_len * 8) / bits_per_frame)
        
        # Pipeline State
        rs_input_gen = buffered_rs_input_generator()
        rs_futures = collections.deque()
        render_futures = set()
        
        frame_bits_buffer = np.array([], dtype=np.uint8)
        frame_idx = 0
        
        MAX_RS_PENDING = max_workers * 2
        MAX_RENDER_PENDING = max_workers * 4 
        
        input_exhausted = False
        
        pbar = tqdm(total=estimated_frames, desc="Encoding")
        
        with concurrent.futures.ProcessPoolExecutor(max_workers=max_workers) as executor:
            while True:
                if self.check_cancel: self.check_cancel()
                # 1. Fill RS Pipeline
                while not input_exhausted and len(rs_futures) < MAX_RS_PENDING:
                    try:
                        chunk_args = next(rs_input_gen)
                        fut = executor.submit(_rs_encode_chunk, chunk_args)
                        rs_futures.append(fut)
                    except StopIteration:
                        input_exhausted = True
                        
                # 2. Process RS Results (In Order) -> Submit Render Tasks
                while rs_futures and len(render_futures) < MAX_RENDER_PENDING:
                    if rs_futures[0].done():
                        fut = rs_futures.popleft()
                        try:
                            encoded_chunk = fut.result()
                            
                            block_bits = np.unpackbits(np.frombuffer(encoded_chunk, dtype=np.uint8))
                            frame_bits_buffer = np.concatenate([frame_bits_buffer, block_bits])
                            
                            while len(frame_bits_buffer) >= bits_per_frame:
                                frame_bits = frame_bits_buffer[:bits_per_frame]
                                frame_bits_buffer = frame_bits_buffer[bits_per_frame:]
                                frame_bits = frame_bits.reshape((data_height, data_width))
                                
                                task = (DEFAULT_HEADER_COPIES + frame_idx, frame_bits, self.output_dir, self.block_size)
                                rf = executor.submit(_render_and_save_frame, task)
                                render_futures.add(rf)
                                frame_idx += 1
                                
                        except Exception as e:
                            print(f"Error in RS encoding: {e}")
                            raise e
                    else:
                        break 
                
                # 3. Check Render Futures
                done_render = {fut for fut in render_futures if fut.done()}
                for fut in done_render:
                    render_futures.remove(fut)
                    pbar.update(1)
                    if self.progress_callback and pbar.n % 10 == 0:
                        pct = 50 + min(50, (pbar.n / estimated_frames) * 50)
                        self.progress_callback(pct)
                    try:
                        fut.result()
                    except Exception as e:
                        print(f"Error in Render: {e}")
                        raise e
                
                # 4. Handle Final Bits (Flush)
                if input_exhausted and not rs_futures and len(frame_bits_buffer) > 0:
                    while len(frame_bits_buffer) > 0:
                        if len(frame_bits_buffer) >= bits_per_frame:
                             frame_bits = frame_bits_buffer[:bits_per_frame]
                             frame_bits_buffer = frame_bits_buffer[bits_per_frame:]
                        else:
                             padding = np.zeros(bits_per_frame - len(frame_bits_buffer), dtype=np.uint8)
                             frame_bits = np.concatenate([frame_bits_buffer, padding])
                             frame_bits_buffer = np.array([], dtype=np.uint8)
                        
                        frame_bits = frame_bits.reshape((data_height, data_width))
                        task = (DEFAULT_HEADER_COPIES + frame_idx, frame_bits, self.output_dir, self.block_size)
                        rf = executor.submit(_render_and_save_frame, task)
                        render_futures.add(rf)
                        frame_idx += 1
                        if frame_idx > estimated_frames:
                            pbar.total = frame_idx
                
                # 5. Termination
                if input_exhausted and not rs_futures and not render_futures:
                    break
                    
                # 6. Wait Strategy
                wait_list = []
                if len(render_futures) >= MAX_RENDER_PENDING:
                    wait_list.extend(list(render_futures))
                elif rs_futures and not rs_futures[0].done():
                    if len(rs_futures) >= MAX_RS_PENDING:
                        wait_list.append(rs_futures[0])
                    else:
                        if input_exhausted:
                            wait_list.append(rs_futures[0])
                
                if not wait_list and not done_render and not input_exhausted:
                     pass # Loop to fill more RS tasks
                elif wait_list:
                    concurrent.futures.wait(wait_list, return_when=concurrent.futures.FIRST_COMPLETED)
        
        pbar.close()
        if self.progress_callback:
            self.progress_callback(100)
            
        print("Encoding complete.")
    def derive_key(self, password, salt):
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        return base64.urlsafe_b64encode(kdf.derive(password.encode()))

    def create_header(self, payload_length, original_size, checksum, flags, salt, filename, version=4):
        """
        Creates a fixed-size header containing metadata.
        Header Structure (1024 bytes):
        - Magic (4 bytes): YOTU
        - Version (1 byte): 4 or 5
        - Flags (1 byte): Bit 0 = Compressed, Bit 1 = Encrypted
        - Block Size (1 byte): e.g. 2
        - ECC Bytes (1 byte): e.g. 32
        - Payload Length (8 bytes): Unsigned Long Long
        - Checksum (16 bytes): MD5 of ORIGINAL data
        - Salt (16 bytes): For encryption key derivation
        - Original Size (8 bytes): Unsigned Long Long
        - Header Copies (1 byte): Number of header frames (at offset 56)
        - Filename Length (1 byte): Length of filename (at offset 57)
        - Filename (N bytes): UTF-8 Encoded Filename (at offset 58)
        - Header CRC32 (4 bytes): CRC32 of the header itself (at offset 1020)
        - Reserved (Remaining bytes): Padding
        """
        magic = b'YOTU'
        version_byte = bytes([version])
        flags_byte = bytes([flags])
        block_size_byte = bytes([self.block_size])
        ecc_bytes_byte = bytes([self.ecc_bytes])
        
        payload_len_bytes = struct.pack('>Q', payload_length)
        original_size_bytes = struct.pack('>Q', original_size)
        
        # Salt is 16 bytes
        if len(salt) != 16:
            salt = b'\x00' * 16
            
        header_part1 = (magic + version_byte + flags_byte + block_size_byte + ecc_bytes_byte + 
                  payload_len_bytes + checksum + salt + original_size_bytes)
        
        # Add Header Copies at offset 56
        # header_part1 len = 4+1+1+1+1+8+16+16+8 = 56 bytes
        header_copies_byte = bytes([DEFAULT_HEADER_COPIES])
        
        # Add Filename
        filename_bytes = filename.encode('utf-8')
        if len(filename_bytes) > 255:
            filename_bytes = filename_bytes[:255] # Truncate if too long
            
        filename_len_byte = bytes([len(filename_bytes)])
        
        header_data = header_part1 + header_copies_byte + filename_len_byte + filename_bytes
        
        # Padding
        padding_len = HEADER_SIZE - len(header_data) - 4 # Reserve 4 bytes for CRC32
        padding = b'\x00' * padding_len
        
        header_without_crc = header_data + padding
        
        # Calculate CRC32 of header_without_crc
        header_crc = zlib.crc32(header_without_crc) & 0xFFFFFFFF
        header_crc_bytes = struct.pack('>I', header_crc)
        
        return header_without_crc + header_crc_bytes




    def bytes_to_bits(self, data):
        """Converts byte array to a boolean numpy array (bits)."""
        byte_arr = np.frombuffer(data, dtype=np.uint8)
        bits = np.unpackbits(byte_arr)
        return bits

    def create_frames(self, bits):
        """Generates video frames as PNG images."""
        total_bits = len(bits)
        bits_per_frame = BITS_PER_FRAME
        total_frames = math.ceil(total_bits / bits_per_frame)
        
        print(f"Generating {total_frames} frames for {total_bits} bits...")
        
        # Ensure output directory exists
        os.makedirs(self.output_dir, exist_ok=True)
        print(f"Created output directory: {self.output_dir}")
        
        # Pad bits
        padding_needed = (total_frames * bits_per_frame) - total_bits
        if padding_needed > 0:
            bits = np.concatenate([bits, np.zeros(padding_needed, dtype=np.uint8)])
            
        frames_data = bits.reshape((total_frames, DATA_HEIGHT, DATA_WIDTH))
        
        # Prepare arguments for parallel processing
        tasks = []
        for i in range(total_frames):
            tasks.append((i, frames_data[i], self.output_dir))
            
        # Use ProcessPoolExecutor for parallel frame generation
        max_workers = os.cpu_count()
        print(f"Rendering frames using {max_workers} processes...")
        
        with concurrent.futures.ProcessPoolExecutor(max_workers=max_workers) as executor:
            # Map returns results in order, but we want progress bar
            results = list(tqdm(executor.map(_render_and_save_frame, tasks), total=total_frames, desc="Rendering Frames"))
            
            # Update progress callback if needed (approximate)
            if self.progress_callback:
                self.progress_callback(100)
            
        print(f"Frames saved to {self.output_dir}")
