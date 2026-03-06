import os

def split_file(file_path, chunk_size, output_dir=None, progress_callback=None):
    """
    Splits a file into chunks of roughly chunk_size bytes.
    Returns a list of paths to the chunk files.
    Chunks are named file.ext.001, file.ext.002, etc.
    """
    if not output_dir:
        output_dir = os.path.dirname(file_path)
    
    base_name = os.path.basename(file_path)
    file_size = os.path.getsize(file_path)
    
    if file_size <= chunk_size:
        return [file_path]
    
    chunk_paths = []
    buffer_size = 1024 * 1024 * 10 # 10MB Buffer
    
    with open(file_path, 'rb') as src:
        part_num = 1
        bytes_read_total = 0
        
        while True:
            # Start a new chunk
            part_suffix = f"{part_num:03d}"
            chunk_name = f"{base_name}.{part_suffix}"
            if output_dir:
                chunk_path = os.path.join(output_dir, chunk_name)
            else:
                chunk_path = chunk_name # Should use absolute path ideally
            
            # Write chunk
            current_chunk_size = 0
            chunk_written = False
            
            with open(chunk_path, 'wb') as dest:
                while current_chunk_size < chunk_size:
                    # Determine how much to read: min(buffer, remaining_chunk_space)
                    read_size = min(buffer_size, chunk_size - current_chunk_size)
                    buf = src.read(read_size)
                    if not buf:
                        break # EOF of source file
                    
                    dest.write(buf)
                    current_chunk_size += len(buf)
                    bytes_read_total += len(buf)
                    chunk_written = True
                    
                    if progress_callback:
                        progress_callback(bytes_read_total, file_size)

            if not chunk_written:
                # If we opened a file but wrote 0 bytes because we hit EOF immediately
                # remove the empty file and break
                try:
                    os.remove(chunk_path)
                except OSError:
                    pass
                break
                
            chunk_paths.append(chunk_path)
            part_num += 1
            
            # If the last chunk was smaller than requested, we are done
            if current_chunk_size < chunk_size:
                break
                
    return chunk_paths

def join_files(chunk_paths, output_path, progress_callback=None):
    """
    Joins multiple file chunks into a single file.
    """
    # Sort chunks to ensure correct order
    def get_part_number(filename):
        try:
            ext = os.path.splitext(filename)[1]
            if len(ext) > 1 and ext[1:].isdigit():
                return int(ext[1:])
            return filename
        except:
            return filename
            
    # Sort in-place based on numeric extension
    chunk_paths.sort(key=get_part_number)
    
    total_size = sum(os.path.getsize(p) for p in chunk_paths)
    processed = 0
    
    with open(output_path, 'wb') as dest:
        for chunk_path in chunk_paths:
            with open(chunk_path, 'rb') as src:
                while True:
                    buf = src.read(1024 * 1024 * 10) # 10MB buffer
                    if not buf:
                        break
                    dest.write(buf)
                    processed += len(buf)
                    if progress_callback:
                        progress_callback(processed, total_size)

def auto_join_restored_files(file_list, log_callback=None, progress_callback=None, auto_cleanup=True):
    """
    Detects if files in file_list are split parts (e.g., .001, .002) and joins them.
    Returns the modified list of files (joined files + non-split files).
    """
    import shutil
    
    # We must operate on a copy of the list to avoid modification during iteration issues
    # But we want to return a list that represents the final state
    
    # Strategy:
    # 1. Identify groups of split files
    # 2. Join each group
    # 3. Construct the final list: 
    #    Start with original list.
    #    Remove parts that were joined.
    #    Add the joined file.
    
    groups = {}
    
    # Group by base name (removing the numeric extension)
    # e.g. "video.mp4.001" -> base="video.mp4", ext=".001"
    for f in file_list:
        if not os.path.exists(f):
            continue
            
        base, ext = os.path.splitext(f)
        if len(ext) > 1 and ext[1:].isdigit():
            # It's a candidate part
            if base not in groups: 
                groups[base] = []
            groups[base].append(f)
    
    final_files = list(file_list)
    
    for base_name, parts in groups.items():
        if len(parts) > 1:
            # Sort parts numerically
            parts.sort(key=lambda x: int(os.path.splitext(x)[1][1:]) if os.path.splitext(x)[1][1:].isdigit() else x)
            
            # Verify sequence? (001, 002...)
            # For robustness, we just join them in order.
            
            output_filename = base_name
            
            if log_callback: 
                log_callback(f"Auto-joining {len(parts)} parts into {os.path.basename(output_filename)}...")
            
            try:
                join_files(parts, output_filename, progress_callback=progress_callback)
                
                if log_callback: 
                    log_callback(f"Joined successfully: {output_filename}")
                
                # Update final list
                if output_filename not in final_files:
                    final_files.append(output_filename)
                
                # Remove parts from final list
                for p in parts:
                    if p in final_files:
                        final_files.remove(p)
                
                # Cleanup parts
                if auto_cleanup:
                    for p in parts:
                        try:
                            os.remove(p)
                            if log_callback: 
                                log_callback(f"Cleanup: Removed split part {os.path.basename(p)}")
                        except Exception as e:
                            if log_callback:
                                log_callback(f"Cleanup Warning: Failed to remove {os.path.basename(p)}: {e}")
            except Exception as e:
                if log_callback: 
                    log_callback(f"Auto-join failed for {os.path.basename(base_name)}: {e}")
                
    return final_files
