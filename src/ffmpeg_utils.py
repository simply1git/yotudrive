import os
import sys

def get_ffmpeg_path():
    """
    Returns the path to the FFmpeg executable.
    Prioritizes 'imageio-ffmpeg' if available, otherwise falls back to 'ffmpeg' in PATH.
    """
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError:
        return "ffmpeg" # Fallback to system PATH

def check_ffmpeg_available():
    """
    Checks if FFmpeg is available (either via imageio-ffmpeg or system PATH).
    """
    import subprocess
    ffmpeg_path = get_ffmpeg_path()
    try:
        subprocess.run([ffmpeg_path, "-version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        return True, ffmpeg_path
    except (FileNotFoundError, subprocess.CalledProcessError, OSError):
        return False, None

def extract_frames(video_path, output_dir, limit=None, check_cancel=None):
    """
    Extracts frames from a video file into a directory.
    :param limit: Maximum number of frames to extract (for verification/preview).
    """
    ffmpeg_path = get_ffmpeg_path()
    
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        
    cmd = [
        ffmpeg_path,
        "-hide_banner", # Hide banner
        "-loglevel", "error", # Only errors
        "-i", video_path,
        "-start_number", "0",
    ]
    
    if limit:
        cmd.extend(["-vframes", str(limit)])
        
    cmd.append(os.path.join(output_dir, "frame_%08d.png"))
    
    return run_ffmpeg(cmd, check_cancel)

def stitch_frames(frames_dir, output_video, framerate=30, encoder="libx264", preset="medium", check_cancel=None):
    """
    Stitches frames from a directory into a video file.
    """
    import subprocess
    ffmpeg_path = get_ffmpeg_path()
    
    input_pattern = os.path.join(frames_dir, "frame_%08d.png")
    
    # Determine settings based on encoder
    # Hardware encoders usually handle presets differently or have different names
    # But 'medium', 'slow', 'fast' are often mapped or ignored safely.
    # For NVENC: p1-p7 are presets, but -preset medium works as alias often or we can map.
    # For simplicity, we pass preset, but if it fails, user should switch back to libx264.
    
    cmd = [
        ffmpeg_path,
        "-hide_banner",
        "-loglevel", "error",
        "-framerate", str(framerate),
        "-start_number", "0",
        "-i", input_pattern,
        "-c:v", encoder,
    ]
    
    # Encoder-specific options
    if "libx264" in encoder:
        cmd.extend(["-preset", preset, "-crf", "18"])
    elif "nvenc" in encoder:
        # NVENC uses -cq for VBR or -qp for CQP. -crf is x264 specific.
        # We'll use -cq 19 for high quality
        cmd.extend(["-preset", "p6", "-cq", "19"]) # p6 is slower/better
    elif "qsv" in encoder:
        cmd.extend(["-global_quality", "20", "-look_ahead", "1"])
    elif "amf" in encoder:
         cmd.extend(["-quality", "quality", "-rc", "cqp", "-qp_p", "18", "-qp_i", "18"])
    else:
        # Fallback/Generic
        cmd.extend(["-preset", preset])
        
    cmd.extend([
        "-pix_fmt", "yuv420p", # Standard compatibility
        "-movflags", "+faststart", # Web optimization
        "-y", # Overwrite output
        output_video
    ])
    
    # Estimate total frames if not provided
    total_frames = None
    try:
        total_frames = len([f for f in os.listdir(frames_dir) if f.endswith('.png')])
    except:
        pass

    process = run_ffmpeg(cmd, check_cancel, progress_cb=progress_cb, total_frames=total_frames)
    
    # Automatic fallback logic for hardware encoders
    if process.returncode != 0:
        if encoder != "libx264":
            print(f"Warning: Encoder '{encoder}' failed with return code {process.returncode}.")
            print("Falling back to software encoder (libx264)...")
            return stitch_frames(frames_dir, output_video, framerate, encoder="libx264", preset=preset, check_cancel=check_cancel)
        else:
            # If libx264 fails, raise exception to stop the process
            raise subprocess.CalledProcessError(process.returncode, cmd)
            
    return process

def run_ffmpeg(cmd, check_cancel=None, progress_cb=None, total_frames=None):
    import subprocess
    import threading
    import time
    import re
    
    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    
    def consume_stream(stream):
        try:
            # For stdout, we only print if it's not empty and we want to see it?
            # FFmpeg prints logs to stderr by default. stdout is usually empty unless -f rawvideo is used.
            # We already set -loglevel error, so stderr should be clean.
            for line in iter(stream.readline, b''):
                decoded_line = line.decode('utf-8', errors='replace').strip()
                if not decoded_line: continue
                
                # Progress parsing: "frame=  123 fps=..."
                if progress_cb and total_frames:
                    match = re.search(r'frame=\s*(\d+)', decoded_line)
                    if match:
                        frame_count = int(match.group(1))
                        pct = min(99, (frame_count / total_frames) * 100)
                        progress_cb(pct)

                if not any(x in decoded_line for x in ["frame=", "fps=", "size=", "time=", "bitrate="]):
                    print(decoded_line)
        except:
            pass
        finally:
            stream.close()
            
    t_out = threading.Thread(target=consume_stream, args=(process.stdout,), daemon=True)
    t_err = threading.Thread(target=consume_stream, args=(process.stderr,), daemon=True)
    t_out.start()
    t_err.start()
    
    try:
        while process.poll() is None:
            if check_cancel:
                check_cancel()
            time.sleep(0.1)
    except Exception as e:
        process.kill()
        t_out.join(timeout=1.0)
        t_err.join(timeout=1.0)
        raise e
        
    t_out.join()
    t_err.join()
    
    return process
