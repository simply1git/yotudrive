import os
import shutil
import subprocess
import sys
import glob
try:
    import yt_dlp
except ImportError:
    yt_dlp = None

from src.ffmpeg_utils import get_ffmpeg_path, check_ffmpeg_available, extract_frames

class YouTubeStorage:
    """
    Interface for YouTube interaction.
    Currently supports:
    - Manual Upload (instructions)
    - Download via yt-dlp (bundled or system)
    """
    
    def __init__(self, temp_dir="data/temp"):
        self.temp_dir = temp_dir
        os.makedirs(self.temp_dir, exist_ok=True)
        self.ffmpeg_path = get_ffmpeg_path()

    def upload(self, frames_dir):
        """
        Simulates the upload process by providing instructions.
        """
        print("\n=== UPLOAD INSTRUCTIONS ===")
        print(f"1. The frames are ready in: {os.path.abspath(frames_dir)}")
        print("2. Create a video file from these frames.")
        print("   Since FFmpeg might not be in your PATH, use the built-in stitch command:")
        print(f"   python -m src.cli stitch {frames_dir} output.mp4")
        print("3. Upload 'output.mp4' to your YouTube channel.")
        print("4. Copy the Video ID (e.g., dQw4w9WgXcQ).")
        print("5. Register it in YotuDrive using:")
        print("   python -m src.cli register <filename> <video_id>")
        return None

    def kill_browser_process(self, browser_name):
        """Kills the browser process to unlock cookies DB."""
        if os.name != 'nt':
            return
            
        browser_exes = {
            'chrome': 'chrome.exe',
            'firefox': 'firefox.exe',
            'edge': 'msedge.exe',
            'opera': 'opera.exe',
            'brave': 'brave.exe'
        }
        
        exe_name = browser_exes.get(browser_name.lower())
        if not exe_name:
            return

        print(f"Attempting to close {browser_name} to unlock cookies...")
        try:
            subprocess.run(['taskkill', '/F', '/IM', exe_name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            import time
            time.sleep(2) # Wait for file lock release
            
            # Verify if still running
            result = subprocess.run(['tasklist', '/FI', f'IMAGENAME eq {exe_name}'], capture_output=True, text=True)
            if exe_name in result.stdout:
                print(f"Warning: {browser_name} seems to be still running. Cookie extraction might fail.")
                
        except Exception as e:
            print(f"Warning: Failed to kill {browser_name}: {e}")

    def get_playlist_info(self, playlist_url):
        """
        Returns a list of video info dicts from a playlist.
        Each dict contains: {'url': str, 'title': str, 'id': str}
        """
        if not yt_dlp:
            print("Error: 'yt-dlp' library is not installed.")
            return []

        print(f"Fetching playlist info: {playlist_url}")
        
        ydl_opts = {
            'extract_flat': True, # Don't download, just extract info
            'quiet': True,
            'ignoreerrors': True,
        }
        
        video_list = []
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(playlist_url, download=False)
                
                if 'entries' in info:
                    # It's a playlist
                    for entry in info['entries']:
                        if not entry: continue
                        
                        vid_url = entry.get('url')
                        vid_id = entry.get('id')
                        vid_title = entry.get('title', 'Unknown Video')
                        
                        if not vid_url and vid_id:
                            vid_url = f"https://www.youtube.com/watch?v={vid_id}"
                            
                        if vid_url:
                            video_list.append({
                                'url': vid_url,
                                'id': vid_id,
                                'title': vid_title
                            })
                else:
                    # Single video?
                    vid_url = info.get('url')
                    vid_id = info.get('id')
                    vid_title = info.get('title', 'Unknown Video')
                    
                    if not vid_url and vid_id:
                        vid_url = f"https://www.youtube.com/watch?v={vid_id}"

                    if vid_url:
                        video_list.append({
                            'url': vid_url,
                            'id': vid_id,
                            'title': vid_title
                        })
                        
        except Exception as e:
            print(f"Error fetching playlist info: {e}")
            return []
        
        return video_list

    def download(self, video_id_or_url, output_dir, cookies_browser=None, cookies_file=None, check_cancel=None):
        """
        Downloads a video from YouTube using yt-dlp.
        :param video_id_or_url: YouTube Video ID or URL.
        :param output_dir: Directory where frames will be extracted.
        :param cookies_browser: Browser to use cookies from (e.g., 'chrome', 'firefox').
        :param cookies_file: Path to Netscape formatted cookies.txt file.
        :param check_cancel: Optional callback to check for cancellation.
        """
        print(f"Attempting to download video {video_id_or_url}...")
        
        if not yt_dlp:
            print("Error: 'yt-dlp' library is not installed.")
            return False

        if check_cancel:
            try:
                check_cancel()
            except Exception:
                return False

        # Use the output_dir (which is unique) for the temporary video download as well
        # This prevents concurrency issues with multiple downloads
        temp_video_dir = os.path.join(output_dir, "temp_video")
        os.makedirs(temp_video_dir, exist_ok=True)
        
        def progress_hook(d):
            if check_cancel:
                check_cancel()

        # Configure yt-dlp
        output_template = os.path.join(temp_video_dir, "downloaded_video.%(ext)s")
        
        ydl_opts = {
            'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
            'outtmpl': output_template,
            'quiet': False,
            'overwrites': True,
            'ffmpeg_location': self.ffmpeg_path,  # Use bundled ffmpeg
            'progress_hooks': [progress_hook],
            
            # Robustness settings
            'retries': 10,                 # Retry download 10 times
            'fragment_retries': 10,        # Retry fragment downloads
            'skip_unavailable_fragments': False, # Don't skip, we need full data
            'keep_fragments': False,       # Cleanup fragments
            'buffersize': 1024 * 16,       # Buffer size
            'http_chunk_size': 10485760,   # 10MB chunks (helps with stability)
            'socket_timeout': 30,          # 30s timeout
        }

        if cookies_file:
            print(f"Using cookies from file: {cookies_file}")
            ydl_opts['cookiefile'] = cookies_file
        elif cookies_browser:
            print(f"Using cookies from {cookies_browser}...")
            # Try to kill browser first if on Windows
            self.kill_browser_process(cookies_browser)
            ydl_opts['cookiesfrombrowser'] = (cookies_browser, None, None, None)

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([video_id_or_url])
            
            # Find the downloaded file
            # yt-dlp might have merged it into .mp4 or kept it as is
            # We look for the file that was just created/modified or matches pattern
            # Simplest: check known extensions
            video_path = None
            for ext in ['mp4', 'mkv', 'webm']:
                potential_path = output_template.replace("%(ext)s", ext)
                if os.path.exists(potential_path):
                    video_path = potential_path
                    break
            
            if not video_path:
                # Fallback search
                files = glob.glob(os.path.join(temp_video_dir, "downloaded_video.*"))
                if files:
                    video_path = files[0]

            if video_path:
                print(f"Video downloaded to: {video_path}")
                
                # Now extract frames
                print("Extracting frames...")
                extract_frames(video_path, output_dir, check_cancel=check_cancel)

                print(f"Frames extracted to: {output_dir}")
                
                # Cleanup video file immediately to save space
                try:
                    os.remove(video_path)
                    if os.path.exists(temp_video_dir):
                        os.rmdir(temp_video_dir)
                except:
                    pass
                    
                return True
            else:
                print("Error: Could not locate downloaded video file.")
                return False
                
        except Exception as e:
            if str(e) == "Process Cancelled":
                raise e
            print(f"Download failed: {e}")
            if "Private video" in str(e):
                print("HINT: This video is Private. Try using browser cookies or make it Unlisted.")
            if "cookies" in str(e).lower():
                print("HINT: Browser cookies might be locked. Close the browser and try again.")
            return False
