import argparse
import os
import shutil
import sys
import time
import subprocess
from src.encoder import Encoder
from src.decoder import Decoder
from src.db import FileDatabase
from src.youtube import YouTubeStorage
from src.ffmpeg_utils import get_ffmpeg_path, extract_frames, stitch_frames

# Global Database and Storage
db = FileDatabase()
yt = YouTubeStorage()

def encode(args):
    """
    Encode a file into a sequence of video frames (PNG images).
    """
    input_file = args.input_file
    output = args.output
    password = args.password
    
    print(f"Encoding {input_file} into frames at {output}...")
    
    # Clean/Create output directory
    if os.path.exists(output):
        try:
            shutil.rmtree(output)
        except OSError as e:
            print(f"Warning: Could not clean output directory: {e}")
            
    os.makedirs(output, exist_ok=True)
    
    try:
        encoder = Encoder(input_file, output, password=password)
        encoder.run()
        print(f"Success! Frames saved to {output}")
        print("To create a video for YouTube upload, run:")
        print(f"python -m src.cli stitch {output} output.mp4")
        
        # Register locally in DB as "pending upload"
        file_size = os.path.getsize(input_file)
        db.add_file(os.path.basename(input_file), "pending_upload", file_size, {"frames_dir": output})
        
    except Exception as e:
        print(f"Error during encoding: {e}", file=sys.stderr)

def decode(args):
    """
    Decode a sequence of video frames (PNG images) back into the original file.
    """
    input_dir = args.input_dir
    output = args.output
    password = args.password
    
    print(f"Decoding frames from {input_dir} into {output}...")
    
    try:
        decoder = Decoder(input_dir, output, password=password)
        decoder.run()
        print(f"Success! File restored to {decoder.output_file}")
    except Exception as e:
        print(f"Error during decoding: {e}", file=sys.stderr)
        sys.exit(1)

def list_files(args):
    """List all files tracked by YotuDrive."""
    files = db.list_files()
    if not files:
        print("No files found in database.")
        return

    print(f"{'File Name':<30} | {'Video ID':<20} | {'Size (Bytes)':<15} | {'Date':<20}")
    print("-" * 90)
    for f in files:
        date_str = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(f['upload_date']))
        print(f"{f['file_name']:<30} | {f['video_id']:<20} | {f['file_size']:<15} | {date_str:<20}")

def register(args):
    """Register a file with a YouTube Video ID."""
    file_name = args.file_name
    video_id = args.video_id
    
    # We might not know the size if it's not local, so we use 0 or update later
    db.add_file(file_name, video_id, 0, {"status": "uploaded"})
    print(f"File '{file_name}' registered with Video ID '{video_id}'.")

def upload(args):
    """Simulate upload or provide instructions."""
    frames_dir = args.frames_dir
    yt.upload(frames_dir)

def download(args):
    """Download a video from YouTube and extract frames."""
    video_id = args.video_id
    output_dir = args.output_dir
    cookies = args.cookies_browser
    cookies_file = args.cookies_file
    
    print(f"Downloading video {video_id}...")
    # This requires yt-dlp
    if yt.download(video_id, output_dir, cookies_browser=cookies, cookies_file=cookies_file):
        print("Download and extraction complete.")
        print(f"Now you can decode using: python -m src.cli decode {output_dir} --output <filename>")
    else:
        print("Download failed.", file=sys.stderr)
        sys.exit(1)

def stitch(args):
    """Stitch frames into a video using bundled FFmpeg."""
    frames_dir = args.frames_dir
    output_file = args.output_file
    
    print(f"Stitching frames from {frames_dir} to {output_file}...")
    
    try:
        stitch_frames(frames_dir, output_file)
        print(f"Success! Video saved to {output_file}")
    except Exception as e:
        print(f"Error during stitching: {e}")

def main():
    parser = argparse.ArgumentParser(description="YotuDrive CLI - Use YouTube as unlimited cloud storage.")
    subparsers = parser.add_subparsers(dest='command', help='Commands')

    # Encode Command
    parser_encode = subparsers.add_parser('encode', help='Encode a file into video frames.')
    parser_encode.add_argument('input_file', help='Path to the file to encode.')
    parser_encode.add_argument('--output', '-o', default='data/temp/frames', help='Output directory for video frames.')
    parser_encode.add_argument('--password', '-p', help='Password for encryption.')
    parser_encode.set_defaults(func=encode)

    # Decode Command
    parser_decode = subparsers.add_parser('decode', help='Decode video frames back to file.')
    parser_decode.add_argument('input_dir', help='Directory containing the video frames.')
    parser_decode.add_argument('--output', '-o', required=True, help='Output path for the decoded file.')
    parser_decode.add_argument('--password', '-p', help='Password for decryption.')
    parser_decode.set_defaults(func=decode)

    # List Command
    parser_list = subparsers.add_parser('list', help='List all tracked files.')
    parser_list.set_defaults(func=list_files)

    # Register Command
    parser_register = subparsers.add_parser('register', help='Register a file with a YouTube Video ID.')
    parser_register.add_argument('file_name', help='Name of the file.')
    parser_register.add_argument('video_id', help='YouTube Video ID.')
    parser_register.set_defaults(func=register)

    # Upload Command (Instructions)
    parser_upload = subparsers.add_parser('upload', help='Get upload instructions.')
    parser_upload.add_argument('frames_dir', help='Directory containing the frames to upload.')
    parser_upload.set_defaults(func=upload)

    # Download Command
    parser_download = subparsers.add_parser('download', help='Download video from YouTube and extract frames.')
    parser_download.add_argument('video_id', help='YouTube Video ID or URL.')
    parser_download.add_argument('--output_dir', '-o', default='data/temp/downloaded_frames', help='Directory to save extracted frames.')
    parser_download.add_argument('--cookies_browser', help='Browser to use cookies from (chrome, firefox, edge, opera)')
    parser_download.add_argument('--cookies_file', help='Path to Netscape formatted cookies.txt file')
    parser_download.set_defaults(func=download)

    # Stitch Command
    parser_stitch = subparsers.add_parser('stitch', help='Stitch frames into a video (uses bundled FFmpeg).')
    parser_stitch.add_argument('frames_dir', help='Directory containing the frames.')
    parser_stitch.add_argument('output_file', help='Output video file (e.g., output.mp4).')
    parser_stitch.set_defaults(func=stitch)

    args = parser.parse_args()
    
    if hasattr(args, 'func'):
        args.func(args)
    else:
        parser.print_help()

if __name__ == '__main__':
    main()
