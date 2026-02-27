import reedsolo
from src.config import DEFAULT_ECC_BYTES, RS_BLOCK_SIZE
import concurrent.futures
import os
import math

# Helper functions for multiprocessing (top-level)
def _encode_blocks(args):
    blocks, ecc_bytes = args
    rs = reedsolo.RSCodec(ecc_bytes)
    return [rs.encode(block) for block in blocks]

def _decode_blocks(args):
    blocks, ecc_bytes = args
    rs = reedsolo.RSCodec(ecc_bytes)
    decoded = []
    for block in blocks:
        # We try to decode each block
        try:
            dec, _, _ = rs.decode(block)
            decoded.append(dec)
        except reedsolo.ReedSolomonError:
            raise ValueError("RS Decoding failed")
    return decoded

class RSManager:
    """
    Manages Reed-Solomon encoding and decoding.
    Uses ProcessPoolExecutor for parallel processing if data is large.
    """
    def __init__(self, n=RS_BLOCK_SIZE, k=None, max_workers=None):
        self.max_workers = max_workers or os.cpu_count()
        
        if k is None:
            self.ecc_bytes = DEFAULT_ECC_BYTES
        else:
            self.ecc_bytes = n - k
            
        self.data_block_size = n - self.ecc_bytes
        self.rs_block_size = n
            
        # Initialize codec with configured ECC bytes
        self.rs = reedsolo.RSCodec(self.ecc_bytes)

    def encode(self, data):
        """Encodes data using Reed-Solomon."""
        # Pad data to be a multiple of DATA_BLOCK_SIZE
        if len(data) % self.data_block_size != 0:
            padding_len = self.data_block_size - (len(data) % self.data_block_size)
            data += b'\x00' * padding_len
            
        # Split into blocks of DATA_BLOCK_SIZE
        blocks = [data[i:i+self.data_block_size] for i in range(0, len(data), self.data_block_size)]
        
        # If data is small, process sequentially
        if len(blocks) < 100: # < ~22KB
             return b"".join([self.rs.encode(block) for block in blocks])
             
        # For larger data, use parallel processing
        blocks_per_task = 1000
        task_chunks = [blocks[i:i+blocks_per_task] for i in range(0, len(blocks), blocks_per_task)]
        
        # Prepare args: (chunk, ecc_bytes)
        tasks = [(chunk, self.ecc_bytes) for chunk in task_chunks]
        
        encoded_data = []
        with concurrent.futures.ProcessPoolExecutor(max_workers=self.max_workers) as executor:
            results = executor.map(_encode_blocks, tasks)
            for res in results:
                encoded_data.extend(res)
                
        return b"".join(encoded_data)

    def decode(self, data):
        """Decodes data using Reed-Solomon."""
        # RS encoded data must be a multiple of RS_BLOCK_SIZE
        if len(data) % self.rs_block_size != 0:
            trim_len = len(data) % self.rs_block_size
            data = data[:-trim_len]
            
        if len(data) == 0:
            return b""
            
        # Split into RS_BLOCK_SIZE blocks
        blocks = [data[i:i+self.rs_block_size] for i in range(0, len(data), self.rs_block_size)]
        
        if len(blocks) < 100:
            decoded_blocks = []
            for block in blocks:
                try:
                    decoded, _, _ = self.rs.decode(block)
                    decoded_blocks.append(decoded)
                except reedsolo.ReedSolomonError:
                    raise ValueError("RS Decoding failed for a block")
            return b"".join(decoded_blocks)
            
        # Parallel processing
        blocks_per_task = 1000
        task_chunks = [blocks[i:i+blocks_per_task] for i in range(0, len(blocks), blocks_per_task)]
        
        # Prepare args: (chunk, ecc_bytes)
        tasks = [(chunk, self.ecc_bytes) for chunk in task_chunks]
        
        decoded_data = []
        with concurrent.futures.ProcessPoolExecutor(max_workers=self.max_workers) as executor:
            try:
                results = executor.map(_decode_blocks, tasks)
                for res in results:
                    decoded_data.extend(res)
            except Exception as e:
                raise ValueError(f"RS Decoding failed: {e}")
                
        return b"".join(decoded_data)
