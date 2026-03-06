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
import glob
import sys
import concurrent.futures
from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import base64
import re

# Helper function for parallel frame processing (must be picklable)
def _process_frame(args):
    """Extracts bits from a frame image using Block Averaging for robustness."""
    img_path, block_size = args
    
    # Calculate dimensions
    data_height = VIDEO_HEIGHT // block_size
    data_width = VIDEO_WIDTH // block_size
    bits_per_frame = data_width * data_height
    
    if img_path is None:
        # Return zeros for missing frame
        return np.zeros(bits_per_frame, dtype=np.uint8)

    try:
        with Image.open(img_path) as img:
            # Convert to grayscale if not already
            if img.mode != 'L':
                img = img.convert('L')
            
            # Convert to numpy array
            frame = np.array(img, dtype=np.uint8)
            
            # Check dimensions
            if frame.shape != (VIDEO_HEIGHT, VIDEO_WIDTH):
                # Resize if needed (e.g. YouTube compression changed size)
                img = img.resize((VIDEO_WIDTH, VIDEO_HEIGHT), Image.Resampling.LANCZOS)
                frame = np.array(img, dtype=np.uint8)
            
            # Robust Decoding: Block Averaging
            # Reshape to (rows, block_size, cols, block_size)
            # This allows us to calculate the mean of each block efficiently
            h, w = frame.shape
            # Ensure dimensions are divisible by block_size
            h_trim = h - (h % block_size)
            w_trim = w - (w % block_size)
            frame_trimmed = frame[:h_trim, :w_trim]
            
            # Reshape to 4D array: (grid_rows, block_h, grid_cols, block_w)
            blocks = frame_trimmed.reshape(data_height, block_size, data_width, block_size)
            
            # Calculate mean of each block (axis 1 and 3 are the internal block dims)
            block_means = blocks.mean(axis=(1, 3))
            
            # Thresholding at 128
            bits = (block_means > 128).astype(np.uint8)
            
            return bits.flatten()
    except Exception as e:
        print(f"Error processing frame {img_path}: {e}")
        return None

class Decoder:
    def __init__(self, input_dir, output_file, password=None, progress_callback=None, threads=None, check_cancel=None):
        """
        :param input_dir: Directory containing video frames (PNGs).
        :param output_file: Path to save the decoded file.
        :param password: Optional password for decryption.
        :param progress_callback: Function to call with progress updates (0-100).
        :param threads: Number of parallel threads to use.
        :param check_cancel: Function to check for cancellation (should return True or raise Exception).
        """
        self.input_dir = input_dir
        self.output_file = output_file
        self.password = password
        self.progress_callback = progress_callback
        self.threads = threads
        self.check_cancel = check_cancel
        self.rs_manager = None # Will be initialized after header parsing

    def derive_key(self, password, salt):
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        return base64.urlsafe_b64encode(kdf.derive(password.encode()))

    def process_body_frames_streaming(self, body_files, detected_block_size, output_file, payload_len, flags, salt):
        """
        Processes body frames in chunks, decodes RS, decrypts, decompresses, and writes to file.
        This handles large files by not loading everything into RAM.
        """
        import zlib
        from cryptography.fernet import Fernet
        
        # Prepare Streaming Components
        is_encrypted = (flags & 0x02) != 0
        is_chunked_encryption = (flags & 0x04) != 0 # Version 5 feature
        is_compressed = (flags & 0x01) != 0
        
        fernet = None
        if is_encrypted:
            if not self.password:
                raise ValueError("File is encrypted but no password provided.")
            key = self.derive_key(self.password, salt)
            fernet = Fernet(key)
            
        decompressor = zlib.decompressobj()
        
        # RS Config
        # data_block_size = RS_BLOCK_SIZE - self.rs_manager.ecc_bytes # No, rs_manager stores k
        # But wait, rs_manager.k is what we need?
        # RSManager in this project uses `reedsolo`? 
        # self.rs_manager = RSManager(n=255, k=255-ecc)
        # Decoding returns the original message (k bytes).
        
        # We need to buffer bits until we have a full RS block (255 bytes)
        rs_block_size = 255
        
        # Generator that yields decoded bits from frames
        def bit_stream():
            # Process frames in batches to keep parallelism high but memory low
            BATCH_SIZE = 255 
            
            total_frames = len(body_files)
            
            # Use a single executor for all batches to avoid overhead
            with concurrent.futures.ProcessPoolExecutor(max_workers=self.threads) as executor:
                for i in range(0, total_frames, BATCH_SIZE):
                    if self.check_cancel: self.check_cancel()
                    batch = body_files[i:min(i + BATCH_SIZE, total_frames)]
                    
                    if self.progress_callback:
                        pct = min(100, (i / total_frames) * 100)
                        self.progress_callback(pct)
                    
                    # Prepare tasks
                    tasks = []
                    for f in batch:
                        tasks.append((f, detected_block_size))
                        
                    # Execute Batch
                    # We map the batch tasks
                    results = list(executor.map(_process_frame, tasks))
                        
                    for bits in results:
                        if bits is not None:
                            yield bits
                        else:
                            # Missing frame: Yield zeros (size of frame)
                            dw = VIDEO_WIDTH // detected_block_size
                            dh = VIDEO_HEIGHT // detected_block_size
                            yield np.zeros(dw * dh, dtype=np.uint8)

        # Stream Processor
        byte_accumulator = b''
        total_bytes_extracted = 0
        
        # Output File
        print(f"Restoring to {output_file} (Streaming)...")
        with open(output_file, 'wb') as f_out:
            
            # 1. Accumulate bits -> RS Blocks
            # 2. RS Decode -> Data Blocks
            # 3. Accumulate Data Blocks -> Decrypt/Decompress -> Write
            
            rs_buffer = b''
            
            # Bit stream yields numpy arrays of bits
            for bits in bit_stream():
                # Check if we have already extracted all payload
                if total_bytes_extracted >= payload_len:
                    break

                # Pack bits to bytes
                # Note: bits length might not be multiple of 8?
                # Actually _process_frame returns flattened array.
                # Ideally bits_per_frame is multiple of 8.
                # If not, np.packbits pads with zeros at the end.
                # But we concatenated them in the original code.
                # Here we must be careful.
                # The original code: np.concatenate(all_bits) then packbits.
                # This treats the bit stream as continuous.
                # If a frame has 10 bits and we pack it, we get 2 bytes (6 bits padding).
                # But the next frame should start at bit 11.
                # So we cannot packbits per frame if size % 8 != 0.
                
                # Check alignment
                if len(bits) % 8 != 0:
                    # This is tricky for streaming if we pack per frame.
                    # We must maintain a bit buffer.
                    # Or ensures bits_per_frame is byte aligned.
                    # 1920/2 = 960, 1080/2 = 540. 960*540 = 518400. /8 = 64800.
                    # It IS byte aligned for block size 2.
                    # What about others?
                    # 1920 and 1080 are divisible by 1, 2, 3, 4, 5, 6, 8, 10, 12, 15, 16...
                    # So for all supported block sizes, bits_per_frame is divisible by 8?
                    # 1920*1080 = 2,073,600.
                    # Divisible by 8? Yes.
                    # So frame bits are always byte-aligned.
                    pass
                
                frame_bytes = np.packbits(bits).tobytes()
                rs_buffer += frame_bytes
                
                while len(rs_buffer) >= rs_block_size:
                    block = rs_buffer[:rs_block_size]
                    rs_buffer = rs_buffer[rs_block_size:]
                    
                    # RS Decode
                    try:
                        decoded_block = self.rs_manager.decode(block)
                        # decoded_block is bytearray or bytes
                    except Exception as e:
                        # ECC Failed. 
                        # For video storage, maybe just output the data part (corrupted)?
                        # Or zero it?
                        # RSManager.decode usually raises ReedSolomonError
                        # We can try to just strip parity?
                        # k = n - ecc
                        k = rs_block_size - self.rs_manager.ecc_bytes
                        decoded_block = block[:k]
                        print("ECC Failed for a block, using raw data.")

                    # Truncate to payload_len
                    bytes_remaining = payload_len - total_bytes_extracted
                    if bytes_remaining <= 0:
                        continue
                        
                    if len(decoded_block) > bytes_remaining:
                        decoded_block = decoded_block[:bytes_remaining]
                        
                    total_bytes_extracted += len(decoded_block)
                    byte_accumulator += decoded_block
                    
                    # Process Accumulated Data (Decrypt/Decompress)
                    # We need to handle Encryption Boundaries
                    
                    if is_encrypted:
                        if is_chunked_encryption:
                            # Encrypted in 1MB chunks (PKCS7 padded + Fernet overhead)
                            # We need to find Fernet tokens.
                            # Fernet tokens are variable length? No, deterministic if input is fixed.
                            # But we don't know the exact boundaries easily without a delimiter or length prefix.
                            # The Encoder simply concatenated them?
                            # "yield enc" -> concatenated.
                            # Fernet tokens are Base64 strings.
                            # They are NOT fixed length if input varies (e.g. last chunk).
                            # But we used fixed chunk size for all but last.
                            # ENCRYPTION_CHUNK_SIZE = 1MB.
                            # So the token size for 1MB input is FIXED.
                            # Token Size = Fernet_Size(1MB).
                            # We can calculate it.
                            
                            # Recalculate token size for 1MB
                            # 1MB = 1048576 bytes
                            # Pad: 1048576 is div by 16. Pad = 16 bytes (PKCS7 always pads).
                            # Padded = 1048592
                            # Bin = 1+8+16+1048592+32 = 1048649
                            # B64 = 4 * ceil(1048649/3) = 4 * 349550 = 1398200 bytes.
                            
                            TOKEN_SIZE = 1398200
                            
                            while len(byte_accumulator) >= TOKEN_SIZE:
                                # Check if this is a full token or we are near end
                                # What if last token is smaller?
                                # We might try to decrypt TOKEN_SIZE.
                                # If it fails, maybe it's not a full token?
                                # But we iterate stream.
                                # If we have > TOKEN_SIZE, we can safely take TOKEN_SIZE.
                                # Wait, what if the last chunk is exactly 1MB? Then it works.
                                # What if last chunk < 1MB? Then token is smaller.
                                # But we only know it's the last chunk when stream ends.
                                
                                # So we consume full tokens while we can.
                                # If stream ends, we consume the rest.
                                
                                # Problem: We are inside a loop over bits. We don't know if stream ended.
                                # We need to handle this after the loop?
                                # No, we need to process as we go to save RAM.
                                
                                # Heuristic: If len >= TOKEN_SIZE, take TOKEN_SIZE.
                                # Unless it's the very last part of file?
                                # If we take TOKEN_SIZE and it was actually 2 small tokens?
                                # Impossible if we used fixed chunking. 
                                # Only the last one can be small.
                                # So if we have >= TOKEN_SIZE, the first TOKEN_SIZE bytes MUST be a full token
                                # (because a small token can only appear at the end).
                                
                                token = byte_accumulator[:TOKEN_SIZE]
                                byte_accumulator = byte_accumulator[TOKEN_SIZE:]
                                
                                try:
                                    dec = fernet.decrypt(token)
                                    # Decompress
                                    if is_compressed:
                                        # Decompress streaming
                                        decomp = decompressor.decompress(dec)
                                        if decomp:
                                            f_out.write(decomp)
                                    else:
                                        f_out.write(dec)
                                except Exception as e:
                                    # Might be that we grabbed too much? Or data corrupt?
                                    print(f"Decryption error (Token Size {len(token)}): {e}")
                        else:
                            # Not chunked (V4 legacy or small file).
                            # We must wait for ALL data.
                            # Streaming not supported for V4 Encrypted.
                            # We just accumulate everything.
                            pass
                    else:
                        # Not Encrypted
                        # Just decompress
                        if is_compressed:
                            chunk = byte_accumulator
                            byte_accumulator = b'' # Drain
                            decomp = decompressor.decompress(chunk)
                            if decomp:
                                f_out.write(decomp)
                        else:
                            f_out.write(byte_accumulator)
                            byte_accumulator = b''
            
            # End of stream loop
            # Process remaining buffer
            
            if is_encrypted and is_chunked_encryption:
                # Remaining byte_accumulator should be the last token
                if byte_accumulator:
                    try:
                        dec = fernet.decrypt(byte_accumulator)
                        if is_compressed:
                            decomp = decompressor.decompress(dec)
                            if decomp:
                                f_out.write(decomp)
                        else:
                            f_out.write(dec)
                    except Exception as e:
                         print(f"Final decryption error: {e}")

            elif is_encrypted and not is_chunked_encryption:
                # V4 Legacy: Decrypt all at once
                if byte_accumulator:
                     try:
                        dec = fernet.decrypt(byte_accumulator)
                        if is_compressed:
                             f_out.write(zlib.decompress(dec)) # Non-streaming decompress for legacy
                        else:
                             f_out.write(dec)
                     except Exception as e:
                         print(f"Legacy decryption error: {e}")
            
            # Flush Decompressor
            if is_compressed:
                try:
                    f_out.write(decompressor.flush())
                except:
                    pass
            
            if self.progress_callback:
                self.progress_callback(100)

    def remove_error_correction(self, data):
        """Removes Error Correction (Reed-Solomon)."""
        print("Decoding ECC (Reed-Solomon)...")
        decoded_data = self.rs_manager.decode(data)
        return decoded_data

    def verify_checksum(self, data, expected_checksum):
        """Verifies MD5 checksum."""
        actual_checksum = hashlib.md5(data).digest()
        return actual_checksum == expected_checksum

    def parse_header(self, data):
        """Parses the header to get metadata."""
        if len(data) < HEADER_SIZE:
            raise ValueError("Data too short to contain header")
            
        magic = data[:4]
        if magic != b'YOTU':
            raise ValueError(f"Invalid Magic Number: {magic}")
            
        version = data[4] # byte
        valid_crc = True
        
        if version == 4:
            # Header Structure (1024 bytes):
            # ... (Same as V3 up to offset 56)
            # - Header Copies (1 byte)
            # - Filename Length (1 byte) (Offset 57)
            # - Filename (N bytes) (Offset 58)
            # ...
            
            # Verify Header Integrity (CRC32)
            if len(data) >= 1024:
                header_content = data[:1020]
                stored_crc_bytes = data[1020:1024]
                stored_crc = struct.unpack('>I', stored_crc_bytes)[0]
                calculated_crc = zlib.crc32(header_content) & 0xFFFFFFFF
                
                if calculated_crc != stored_crc:
                    print(f"Warning: Header CRC mismatch! Stored: {stored_crc}, Calc: {calculated_crc}")
                    valid_crc = False
            
            flags = data[5]
            payload_len_bytes = data[8:16]
            payload_len = struct.unpack('>Q', payload_len_bytes)[0]
            
            expected_checksum = data[16:32]
            salt = data[32:48]
            
            original_size_bytes = data[48:56]
            original_size = struct.unpack('>Q', original_size_bytes)[0]
            
            header_copies = data[56]
            
            # Extract Filename
            filename_len = data[57]
            filename = data[58:58+filename_len].decode('utf-8', errors='ignore')
            
            return payload_len, original_size, expected_checksum, flags, salt, header_copies, valid_crc, filename, data[HEADER_SIZE:]

        elif version == 5:
            # Header Structure (Same as V4 but with different flags support):
            # - Magic (4 bytes): YOTU
            # - Version (1 byte): 5
            # - Flags (1 byte): Bit 0 = Compressed, Bit 1 = Encrypted, Bit 2 = Chunked Encryption
            # ... (Rest same as V4)
            
            # Verify Header Integrity (CRC32)
            if len(data) >= 1024:
                header_content = data[:1020]
                stored_crc_bytes = data[1020:1024]
                stored_crc = struct.unpack('>I', stored_crc_bytes)[0]
                calculated_crc = zlib.crc32(header_content) & 0xFFFFFFFF
                
                if calculated_crc != stored_crc:
                    print(f"Warning: Header CRC mismatch! Stored: {stored_crc}, Calc: {calculated_crc}")
                    valid_crc = False
            
            flags = data[5]
            payload_len_bytes = data[8:16]
            payload_len = struct.unpack('>Q', payload_len_bytes)[0]
            
            expected_checksum = data[16:32]
            salt = data[32:48]
            
            original_size_bytes = data[48:56]
            original_size = struct.unpack('>Q', original_size_bytes)[0]
            
            header_copies = data[56]
            
            # Extract Filename
            filename_len = data[57]
            filename = data[58:58+filename_len].decode('utf-8', errors='ignore')
            
            return payload_len, original_size, expected_checksum, flags, salt, header_copies, valid_crc, filename, data[HEADER_SIZE:]

        elif version == 3:
            # Header Structure (1024 bytes):
            # - Magic (4 bytes): YOTU
            # - Version (1 byte): 3
            # - Flags (1 byte)
            # - Block Size (1 byte)
            # - ECC Bytes (1 byte)
            # - Payload Length (8 bytes)
            # - Checksum (16 bytes)
            # - Salt (16 bytes)
            # - Original Size (8 bytes)
            # - Header Copies (1 byte)
            # - Header CRC32 (4 bytes)
            
            # Verify Header Integrity (CRC32)
            if len(data) >= 1024:
                header_content = data[:1020]
                stored_crc_bytes = data[1020:1024]
                stored_crc = struct.unpack('>I', stored_crc_bytes)[0]
                calculated_crc = zlib.crc32(header_content) & 0xFFFFFFFF
                
                if calculated_crc != stored_crc:
                    print(f"Warning: Header CRC mismatch! Stored: {stored_crc}, Calc: {calculated_crc}")
                    valid_crc = False
                else:
                    # print("Header Integrity Verified.")
                    pass
            
            flags = data[5]
            # block_size = data[6]
            # ecc_bytes = data[7]
            
            payload_len_bytes = data[8:16]
            payload_len = struct.unpack('>Q', payload_len_bytes)[0]
            
            expected_checksum = data[16:32]
            
            salt = data[32:48]
            
            original_size_bytes = data[48:56]
            original_size = struct.unpack('>Q', original_size_bytes)[0]
            
            header_copies = data[56]
            
            return payload_len, original_size, expected_checksum, flags, salt, header_copies, valid_crc, None, data[HEADER_SIZE:]

        elif version == 2:
            # Header Structure (1024 bytes):
            # - Magic (4 bytes): YOTU
            # - Version (1 byte): 2
            # - Flags (1 byte)
            # - Block Size (1 byte)
            # - ECC Bytes (1 byte)
            # - Payload Length (8 bytes)
            # - Checksum (16 bytes)
            # - Salt (16 bytes)
            # - Original Size (8 bytes)
            
            flags = data[5]
            # block_size = data[6]
            # ecc_bytes = data[7]
            
            payload_len_bytes = data[8:16]
            payload_len = struct.unpack('>Q', payload_len_bytes)[0]
            
            expected_checksum = data[16:32]
            
            salt = data[32:48]
            
            original_size_bytes = data[48:56]
            original_size = struct.unpack('>Q', original_size_bytes)[0]
            
            return payload_len, original_size, expected_checksum, flags, salt, DEFAULT_HEADER_COPIES, True, None, data[HEADER_SIZE:]
            
        elif version == 1:
            # Legacy Version 1
            flags = data[5]
            
            payload_len_bytes = data[6:14]
            payload_len = struct.unpack('>Q', payload_len_bytes)[0]
            
            expected_checksum = data[14:30]
            
            salt = data[30:46]
            
            original_size_bytes = data[46:54]
            original_size = struct.unpack('>Q', original_size_bytes)[0]
            
            return payload_len, original_size, expected_checksum, flags, salt, DEFAULT_HEADER_COPIES, True, None, data[HEADER_SIZE:]
        else:
            raise ValueError(f"Unknown Header Version: {version}")

    def detect_config(self, frame_files):
        """
        Attempts to detect the Block Size and ECC Bytes from the first few frames.
        Returns: (block_size, ecc_bytes, header_copies, version)
        """
        print("Detecting file configuration...")
        
        # Check up to 5 frames (to handle corrupted first frames)
        frames_to_check = frame_files[:5]
        
        for frame_path in frames_to_check:
            # Try common block sizes
            for test_block_size in [1, 2, 4, 8, 12]:
                try:
                    # Process just enough to get the header
                    bits = _process_frame((frame_path, test_block_size))
                    
                    if bits is None:
                        continue
                        
                    # Pack to bytes
                    raw_arr = np.packbits(bits)
                    raw_bytes = raw_arr.tobytes()
                    
                    if len(raw_bytes) < 4:
                        continue
                        
                    # Check Magic
                    if raw_bytes[:4] == b'YOTU':
                        print(f"Found valid header in {os.path.basename(frame_path)} with Block Size: {test_block_size}")
                        
                        version = raw_bytes[4]
                        
                        if version >= 3:
                            block_size_in_header = raw_bytes[6]
                            ecc_bytes = raw_bytes[7]
                            header_copies = raw_bytes[56]
                            print(f"Detected V{version} Header. BlockSize: {block_size_in_header}, ECC: {ecc_bytes}, Copies: {header_copies}")
                            return block_size_in_header, ecc_bytes, header_copies, version
                        elif version == 2:
                            block_size_in_header = raw_bytes[6]
                            ecc_bytes = raw_bytes[7]
                            print(f"Detected V2 Header. BlockSize: {block_size_in_header}, ECC: {ecc_bytes}")
                            return block_size_in_header, ecc_bytes, 1, 2
                        else:
                            # V1 (fixed block size/ecc or user specified, but usually we don't have this info here)
                            # Assuming V1 uses defaults if detected this way?
                            # V1 header structure: YOTU + Version(1) + Flags + PayloadLen...
                            # It doesn't store Block Size/ECC in header!
                            # So if we found YOTU, it means our test_block_size was correct?
                            # Not necessarily. YOTU is 4 bytes.
                            pass

                except Exception as e:
                    # print(f"Detection error: {e}")
                    pass
                    
        raise ValueError("Could not detect configuration from frames.")

    def recover_header_majority(self, header_candidates):
        """
        Recovers a header from multiple potentially corrupted copies using majority voting.
        :param header_candidates: List of bytes objects (each 1024 bytes).
        :return: Recovered header bytes (1024 bytes).
        """
        if not header_candidates:
            return None
            
        count = len(header_candidates)
        if count == 1:
            return header_candidates[0]
            
        print(f"Recovering header from {count} copies using Majority Vote...")
            
        # Convert to numpy array of bytes (uint8)
        # shape: (count, 1024)
        # Ensure all candidates are 1024 bytes
        candidates_arr = []
        for h in header_candidates:
            if len(h) < 1024:
                h = h + b'\x00' * (1024 - len(h))
            candidates_arr.append(list(h[:1024]))
            
        arr = np.array(candidates_arr, dtype=np.uint8)
        
        recovered = bytearray(1024)
        for i in range(1024):
            # Get all values for byte i
            values = arr[:, i]
            # Find most common value
            counts = np.bincount(values, minlength=256)
            most_common = np.argmax(counts)
            recovered[i] = most_common
            
        return bytes(recovered)

    def guess_extension(self, data):
        """Guesses file extension from magic bytes."""
        if len(data) < 4:
            return None
            
        if data.startswith(b'PK\x03\x04'):
            return '.zip'
        if data.startswith(b'\x89PNG\r\n\x1a\n'):
            return '.png'
        if data.startswith(b'\xff\xd8\xff'):
            return '.jpg'
        if data.startswith(b'%PDF-'):
            return '.pdf'
        if data.startswith(b'MZ'):
            return '.exe'
        if len(data) > 12 and data[4:12] == b'ftypisom':
            return '.mp4'
        if len(data) > 12 and data[4:12] == b'ftypmp42':
            return '.mp4'
        if data.startswith(b'\x1a\x45\xdf\xa3'):
            return '.mkv'
        if data.startswith(b'Rar!'):
            return '.rar'
        if data.startswith(b'\x1f\x8b'):
            return '.gz'
        if data.startswith(b'7z\xbc\xaf\x27\x1c'):
            return '.7z'
            
        return None

    def run(self):
        print(f"Reading frames from {self.input_dir}...")
        frame_files = sorted(glob.glob(os.path.join(self.input_dir, "*.png")))
        
        if not frame_files:
            raise FileNotFoundError(f"No frames found in {self.input_dir}")
            
        # 1. Detect Configuration
        try:
            detected_block_size, detected_ecc_bytes, header_copies, version = self.detect_config(frame_files)
            print(f"Configuration: Block Size={detected_block_size}, ECC Bytes={detected_ecc_bytes}, Version={version}")
        except Exception as e:
            print(f"Configuration detection failed: {e}")
            print("Falling back to defaults (Block Size=2, ECC=32)")
            detected_block_size = 2
            detected_ecc_bytes = 32
            header_copies = 1
            version = 1

        # 2. Initialize RSManager
        self.rs_manager = RSManager(n=RS_BLOCK_SIZE, k=RS_BLOCK_SIZE - detected_ecc_bytes)

        # 3. Determine which frames to process as BODY
        if version >= 3:
            # For V3, the first 'header_copies' frames are purely header + padding.
            # We must identify frames by their index in the filename (frame_XXXX.png).
            # Indices < header_copies are header frames.
            # Indices >= header_copies are body frames.
            
            # We need to extract metadata NOW to know what we are doing
            # (although we already got parameters from detect_config)
            # We need full metadata (checksum, salt, etc.)
            
            header_candidates = []
            
            # Scan all potential header frames (up to header_copies + small buffer)
            frames_to_scan = min(len(frame_files), header_copies + 5)
            
            for i in range(frames_to_scan):
                try:
                    bits = _process_frame((frame_files[i], detected_block_size))
                    if bits is not None:
                        raw = np.packbits(bits).tobytes()
                        # Only consider it a header candidate if it starts with 'YOTU'
                        # In case we have corrupted header frames that don't even have YOTU,
                        # we might skip them.
                        # But wait, if YOTU is corrupted, we skip it.
                        # Ideally, we should include ALL frames that SHOULD be headers.
                        # But we don't know for sure which ones are headers if filenames are scrambled.
                        # Assuming filename order is somewhat reliable or at least we check start.
                        if len(raw) >= HEADER_SIZE and raw[:4] == b'YOTU':
                            header_candidates.append(raw[:HEADER_SIZE])
                except:
                    continue
            
            if not header_candidates:
                 raise ValueError("Could not recover header from any frame!")
                 
            # Majority Vote
            valid_header_bytes = self.recover_header_majority(header_candidates)
            
            # Parse Header
            payload_len, original_size, expected_checksum, flags, salt, _, valid_crc, filename, _ = self.parse_header(valid_header_bytes)
            
            if not valid_crc:
                print("WARNING: Header checksum verification failed after majority vote! Data might be corrupted.")
            else:
                print("Header successfully recovered and verified.")
            
            # Calculate Total Body Frames expected
            data_block_size = 255 - detected_ecc_bytes
            num_blocks = math.ceil(payload_len / data_block_size)
            encoded_len = num_blocks * 255
            total_bits = encoded_len * 8
            
            dw = VIDEO_WIDTH // detected_block_size
            dh = VIDEO_HEIGHT // detected_block_size
            bits_per_frame = dw * dh
            
            total_body_frames = math.ceil(total_bits / bits_per_frame)
            print(f"Expected Body Frames: {total_body_frames} (based on payload {payload_len} bytes)")
            
            # Map existing frames by index
            frame_map = {}
            for f in frame_files:
                basename = os.path.basename(f)
                match = re.search(r'frame_(\d+)', basename)
                if match:
                    idx = int(match.group(1))
                    frame_map[idx] = f
            
            # Reconstruct body_files list with None for missing frames
            body_files = []
            missing_count = 0
            for i in range(total_body_frames):
                idx = header_copies + i
                if idx in frame_map:
                    body_files.append(frame_map[idx])
                else:
                    body_files.append(None)
                    missing_count += 1
            
            if missing_count > 0:
                print(f"Warning: {missing_count} body frames are missing! Inserting placeholders (zeros).")
            
        else:
            # V1/V2: Header is part of the stream
            body_files = frame_files
            payload_len = None
            original_size = None
            expected_checksum = None
            flags = None
            salt = None

        # 4. Process Body Frames
        if version >= 5:
            # Resolve Output Path for Streaming
            final_output_path = self.output_file
            output_dir = os.path.dirname(self.output_file)
            if output_dir and not os.path.exists(output_dir):
                 os.makedirs(output_dir, exist_ok=True)

            if os.path.isdir(self.output_file):
                if filename:
                    safe_filename = os.path.basename(filename)
                    final_output_path = os.path.join(self.output_file, safe_filename)
                else:
                    final_output_path = os.path.join(self.output_file, "restored_file.bin")
            else:
                 root, ext = os.path.splitext(self.output_file)
                 if not ext and filename:
                      _, internal_ext = os.path.splitext(filename)
                      if internal_ext:
                          final_output_path = self.output_file + internal_ext
            
            print(f"Decoding {len(body_files)} body frames (Streaming Mode)...")
            self.process_body_frames_streaming(body_files, detected_block_size, final_output_path, payload_len, flags, salt)
            
            print("Verifying Checksum of restored file...")
            md5 = hashlib.md5()
            with open(final_output_path, 'rb') as f:
                for chunk in iter(lambda: f.read(4096 * 1024), b""):
                    md5.update(chunk)
            
            if md5.digest() == expected_checksum:
                print("Checksum Valid!")
            else:
                print("WARNING: Checksum Invalid! Data might be corrupted.")
                
            self.output_file = final_output_path
            print(f"Success! File restored to {self.output_file}")
            return

        print(f"Decoding {len(body_files)} body frames (Legacy Mode)...")
        
        # Prepare tasks
        tasks = []
        for i, file_path in enumerate(body_files):
            tasks.append((file_path, detected_block_size))
            
        # Parallel Execution
        max_workers = max(1, os.cpu_count() - 1)
        if hasattr(self, 'threads') and self.threads:
             max_workers = self.threads
             
        results = []
        with concurrent.futures.ProcessPoolExecutor(max_workers=max_workers) as executor:
            results = list(tqdm(executor.map(_process_frame_wrapper, tasks), total=len(tasks), desc="Decoding Frames"))
            
        # Filter None results
        results = [r for r in results if r is not None]
        
        # Since we processed files in order, results might be out of order due to parallel completion
        # But _process_frame_wrapper doesn't return index. 
        # Wait, map returns results in order of iterable!
        # So 'results' corresponds to 'body_files' order.
        # We don't need to sort if map preserves order (which it does).
        
        all_bits = results
        
        if not all_bits:
            raise ValueError("No data decoded from frames.")
            
        full_bits = np.concatenate(all_bits)
        full_bytes = np.packbits(full_bits).tobytes()
        
        # 5. Handle Data Extraction (Header vs Body)
        if version >= 3:
            # full_bytes IS the encoded body
            encoded_data = full_bytes
        else:
            # full_bytes starts with Header
            payload_len, original_size, expected_checksum, flags, salt, _, _, filename, encoded_data = self.parse_header(full_bytes)

        # 6. RS Decode
        print("Correcting errors (Reed-Solomon)...")
        try:
            compressed_data = self.remove_error_correction(encoded_data)
        except Exception as e:
            print(f"ECC Failed: {e}")
            raise

        # 7. Checksum/Decrypt/Decompress
        # Decrypt if needed
        # We need flags from header (which we parsed earlier or just now)
        is_encrypted = (flags & 0x02) != 0
        is_compressed = (flags & 0x01) != 0
        
        final_data = compressed_data
        
        if is_encrypted:
            if not self.password:
                raise ValueError("File is encrypted but no password provided. Please enter the password in the GUI.")
                
            print("Decrypting...")
            key = self.derive_key(self.password, salt)
            f = Fernet(key)
            try:
                final_data = f.decrypt(final_data)
            except InvalidToken:
                raise ValueError("Invalid password or corrupted data.")
                
        if is_compressed:
            print("Decompressing...")
            try:
                final_data = zlib.decompress(final_data)
            except zlib.error:
                 raise ValueError("Decompression failed. Data might be corrupted.")
                 
        # Verify Checksum
        print("Verifying Checksum...")
        if self.verify_checksum(final_data, expected_checksum):
            print("Checksum Valid!")
        else:
            print("WARNING: Checksum Invalid! Data might be corrupted.")
            
        # Verify Size
        if len(final_data) != original_size:
            print(f"WARNING: Size mismatch! Expected {original_size}, got {len(final_data)}")
            
        # Save File
        output_dir = os.path.dirname(self.output_file)
        if output_dir and not os.path.exists(output_dir):
             os.makedirs(output_dir, exist_ok=True)
             
        # Determine Final Output Path
        final_output_path = self.output_file
        
        if os.path.isdir(self.output_file):
            # If output is a directory, use the internal filename
            if filename:
                # Remove any potentially dangerous characters/paths from filename
                safe_filename = os.path.basename(filename)
                final_output_path = os.path.join(self.output_file, safe_filename)
            else:
                # Fallback: Try to guess extension
                guessed_ext = self.guess_extension(final_data) or ".bin"
                final_output_path = os.path.join(self.output_file, f"restored_file{guessed_ext}")
                print(f"Using fallback filename with guessed extension: {guessed_ext}")
        else:
            # If output is a file path, check if we need to append extension
            root, ext = os.path.splitext(self.output_file)
            if not ext:
                 # Priority 1: Use internal filename extension
                 if filename:
                      _, internal_ext = os.path.splitext(filename)
                      if internal_ext:
                          final_output_path = self.output_file + internal_ext
                          print(f"Appended extension from metadata: {internal_ext}")
                 else:
                     # Priority 2: Guess from content
                     guessed_ext = self.guess_extension(final_data)
                     if guessed_ext:
                         final_output_path = self.output_file + guessed_ext
                         print(f"Appended guessed extension: {guessed_ext}")

        self.output_file = final_output_path
             
        with open(self.output_file, 'wb') as f:
             f.write(final_data)
             
        print(f"Success! File restored to {self.output_file}")

# Wrapper for pickling
def _process_frame_wrapper(args):
    return _process_frame(args)
