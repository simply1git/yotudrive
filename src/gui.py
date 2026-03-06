import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, simpledialog
import ttkbootstrap as ttk
from ttkbootstrap.constants import *
import subprocess
import threading
import sys
import os
import json
import queue
import time
import shutil
import zipfile
import datetime
import webbrowser
import logging
from ttkbootstrap.widgets.scrolled import ScrolledFrame

from src.encoder import Encoder
from src.decoder import Decoder
from src.db import FileDatabase
from src.ffmpeg_utils import extract_frames, stitch_frames
from src.youtube import YouTubeStorage
from src.config import DEFAULT_BLOCK_SIZE, DEFAULT_ECC_BYTES
from src.file_utils import split_file, join_files
import src.logger as app_logger

class RedirectText:
    def __init__(self, msg_queue):
        self.msg_queue = msg_queue

    def write(self, string):
        if string.strip():
            self.msg_queue.put(("log", string))
            # Also log to file
            logging.info(string.strip())
        
    def flush(self):
        pass

class YotuDriveGUI:
    def __init__(self, root):
        # Setup Persistent Logging
        try:
            self.log_file = app_logger.setup_logging(console=False)
        except Exception as e:
            print(f"Failed to setup logging: {e}")
            self.log_file = None

        self.root = root
        self.root.title("YotuDrive Manager - Enterprise Edition")
        self.root.geometry("1100x800")
        
        # Configure Grid Weight
        root.columnconfigure(0, weight=1)
        root.rowconfigure(0, weight=1)

        # Job Queue
        self.job_queue = queue.Queue()
        self.msg_queue = queue.Queue() # Initialize msg_queue BEFORE load_settings calls log()
        self.is_processing = False
        self.cancel_event = threading.Event()
        
        # Main Layout
        main_frame = ttk.Frame(root, padding=10)
        main_frame.grid(row=0, column=0, sticky="nsew")
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(0, weight=1)

        # Notebook (Tabs)
        self.notebook = ttk.Notebook(main_frame)
        self.notebook.grid(row=0, column=0, sticky="nsew")
        
        # Tabs
        self.tab_files = ttk.Frame(self.notebook, padding=10)
        self.tab_upload = ttk.Frame(self.notebook, padding=10)
        self.tab_restore = ttk.Frame(self.notebook, padding=10)
        self.tab_tools = ttk.Frame(self.notebook, padding=10)
        self.tab_queue = ttk.Frame(self.notebook, padding=10)
        
        self.notebook.add(self.tab_files, text="My Files")
        self.notebook.add(self.tab_upload, text="Encode (Upload)")
        self.notebook.add(self.tab_restore, text="Decode (Restore)")
        self.notebook.add(self.tab_tools, text="Tools")
        self.notebook.add(self.tab_queue, text="Job Queue")
        
        # Settings Variables
        self.setting_block_size = tk.IntVar(value=DEFAULT_BLOCK_SIZE)
        self.setting_ecc_bytes = tk.IntVar(value=DEFAULT_ECC_BYTES)
        cpu_count = os.cpu_count()
        default_threads = max(1, (cpu_count if cpu_count else 4) - 1)
        self.setting_threads = tk.IntVar(value=default_threads)
        self.setting_auto_cleanup = tk.BooleanVar(value=True)
        self.setting_encoder = tk.StringVar(value="libx264")
        self.setting_theme = tk.StringVar(value="cosmo")
        self.setting_compression = tk.StringVar(value="Fast (Deflate)")
        self.setting_split_size = tk.StringVar(value="No Split")
        
        # Load User Preferences
        self.load_settings()

        # Check for critical dependencies
        try:
            import yt_dlp
        except ImportError:
            # We don't block start, but we warn
            self.root.after(1000, lambda: messagebox.showwarning(
                "Missing Dependency", 
                "The 'yt-dlp' library is missing.\n\n"
                "YouTube download/restore features will be disabled or fail.\n"
                "Please install it manually: pip install yt-dlp"
            ))

        # Setup Tabs
        self.setup_files_tab()
        self.setup_upload_tab()
        self.setup_restore_tab()
        self.setup_tools_tab()
        self.setup_queue_tab()
        
        # Progress Bar Area
        self.progress_frame = ttk.Frame(main_frame)
        self.progress_frame.grid(row=1, column=0, sticky="ew", pady=(10, 0))
        self.progress_frame.columnconfigure(1, weight=1)
        
        # Row 0: Progress Bar
        ttk.Label(self.progress_frame, text="Progress:").grid(row=0, column=0, padx=5, sticky="w")
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(self.progress_frame, variable=self.progress_var, maximum=100, bootstyle="striped-success")
        self.progress_bar.grid(row=0, column=1, sticky="ew", padx=5)
        
        # Cancel Button (row 0, col 2)
        self.cancel_button = ttk.Button(self.progress_frame, text="Cancel", command=self.cancel_process, state="disabled", bootstyle="danger")
        self.cancel_button.grid(row=0, column=2, padx=5)
        
        # Row 1: Status Labels (Split to avoid overlap)
        self.status_frame = ttk.Frame(self.progress_frame)
        self.status_frame.grid(row=1, column=0, columnspan=3, sticky="ew", pady=(5, 0))
        self.status_frame.columnconfigure(1, weight=1)

        self.status_label = ttk.Label(self.status_frame, text="Idle", width=50, anchor="w")
        self.status_label.grid(row=0, column=0, padx=5, sticky="w")
        
        self.eta_label = ttk.Label(self.status_frame, text="ETA: --:--", width=20, anchor="e")
        self.eta_label.grid(row=0, column=1, padx=5, sticky="e")

        # Console Log
        self.log_frame = ttk.LabelFrame(main_frame, text="Activity Log")
        self.log_frame.grid(row=2, column=0, sticky="ew", pady=(10, 0))
        self.log_frame.columnconfigure(0, weight=1)
        
        log_btn_frame = ttk.Frame(self.log_frame)
        log_btn_frame.grid(row=0, column=1, sticky='ns', padx=5, pady=5)
        ttk.Button(log_btn_frame, text="Clear", command=self.clear_log, bootstyle="secondary-outline").pack(side='top', pady=2)

        self.log_text = scrolledtext.ScrolledText(self.log_frame, height=8, state='disabled', font=('Consolas', 9))
        self.log_text.grid(row=0, column=0, sticky="ew", padx=5, pady=5)
        
        # Redirect stdout/stderr
        self.msg_queue = queue.Queue()
        self.redirector = RedirectText(self.msg_queue)
        sys.stdout = self.redirector
        sys.stderr = self.redirector
        
        # Start checking queue
        self.root.after(100, self.process_queue)
        self.root.after(1000, self.process_job_queue)

    def setup_queue_tab(self):
        self.queue_list = tk.Listbox(self.tab_queue, width=100, height=20)
        self.queue_list.pack(side="left", fill="both", expand=True, padx=5, pady=5)
        
        btn_frame = ttk.Frame(self.tab_queue)
        btn_frame.pack(side="right", fill="y", padx=5, pady=5)
        
        # ttk.Button(btn_frame, text="Remove Selected", command=self.remove_from_queue, bootstyle="danger").pack(fill="x", pady=5)
        ttk.Button(btn_frame, text="Clear Queue", command=self.clear_queue, bootstyle="warning").pack(fill="x", pady=5)

    def add_to_queue(self, job_type, **kwargs):
        job_id = f"{job_type.upper()} - {datetime.datetime.now().strftime('%H:%M:%S')}"
        self.job_queue.put({"id": job_id, "type": job_type, "args": kwargs})
        self.queue_list.insert(tk.END, f"[{'PENDING'}] {job_id}")
        self.log(f"Job added to queue: {job_id}")

    def remove_from_queue(self):
        # This is tricky with a standard queue, we might just clear UI and let background worker skip cancelled
        # For a real implementation, we'd need a list-based queue or deque
        pass # To be implemented if needed

    def clear_queue(self):
        with self.job_queue.mutex:
            self.job_queue.queue.clear()
        self.queue_list.delete(0, tk.END)
        self.log("Queue cleared.")

    def process_job_queue(self):
        if not self.is_processing and not self.job_queue.empty():
            job = self.job_queue.get()
            self.is_processing = True
            self.current_job = job
            
            # Update UI
            # Find the item in listbox and mark as running
            # For simplicity, we just log it
            self.log(f"Starting job: {job['id']}")
            
            if job['type'] == 'encode':
                threading.Thread(target=self.run_encode_job, args=(job['args'],), daemon=True).start()
            elif job['type'] == 'decode':
                threading.Thread(target=self.run_decode_job, args=(job['args'],), daemon=True).start()
            elif job['type'] == 'restore_youtube':
                threading.Thread(target=self.run_restore_youtube_job, args=(job['args'],), daemon=True).start()
        
        self.root.after(1000, self.process_job_queue)

    def run_encode_job(self, args):
        try:
            self.start_encode_stitch(args['files'], args['output_path'], args.get('password'), args.get('zip_name'), args.get('auto_cleanup', True))
        except Exception as e:
            self.log(f"Error in job: {e}")
        finally:
            self.is_processing = False
            self.job_queue.task_done()

    def run_decode_job(self, args):
        try:
            video_paths = args.get('video_paths')
            if not video_paths:
                 video_paths = [args.get('video_path')]
            
            self.batch_restore_task(video_paths, args['output_dir'], args.get('password'), args.get('auto_cleanup', True))
        except Exception as e:
            self.log(f"Error in job: {e}")
        finally:
            self.is_processing = False
            self.job_queue.task_done()

    def run_restore_youtube_job(self, args):
        try:
            # Handle potential key name mismatch if any, though add_to_queue uses output_path
            output_path = args.get('output_path') or args.get('output_file')
            self.restore_from_youtube(
                args['video_id'], 
                output_path, 
                args.get('password'), 
                args.get('auto_cleanup', True),
                args.get('is_playlist', False)
            )
        except Exception as e:
            self.log(f"Error in job: {e}")
        finally:
            self.is_processing = False
            self.job_queue.task_done()


    def clear_log(self):
        self.log_text.config(state='normal')
        self.log_text.delete('1.0', 'end')
        self.log_text.config(state='disabled')

    def log(self, message):
        self.msg_queue.put(("log", message))
        # Also log to file
        logging.info(message)

    def process_queue(self):
        try:
            while True:
                msg_type, data = self.msg_queue.get_nowait()
                if msg_type == "log":
                    self.log_text.config(state='normal')
                    self.log_text.insert('end', data + "\n")
                    self.log_text.see('end')
                    self.log_text.config(state='disabled')
                elif msg_type == "refresh_files":
                    self.refresh_file_list()
                elif msg_type == "upload_step_2":
                    if isinstance(data, tuple):
                        self.enable_upload_step_2(*data)
                    else:
                        self.enable_upload_step_2(data)
                elif msg_type == "progress":
                    value, status, eta = data
                    if value is not None:
                        self.progress_var.set(value)
                    if status:
                        # Truncate status if too long
                        max_len = 60
                        if len(status) > max_len:
                            status = status[:max_len-3] + "..."
                        self.status_label.config(text=status)
                    if eta:
                        self.eta_label.config(text=f"ETA: {eta}")
                elif msg_type == "error":
                    title, msg = data
                    messagebox.showerror(title, msg)
                elif msg_type == "success":
                    title, msg = data
                    messagebox.showinfo(title, msg)
                elif msg_type == "set_cancel_state":
                    state = data
                    self.cancel_button.configure(state=state)
                elif msg_type == "job_finished":
                    self.is_processing = False
                    self.current_job = None
                    self.update_progress(0, "Idle")
                    self.log("Ready.")
        except queue.Empty:
            pass
        self.root.after(100, self.process_queue)

    def cancel_process(self):
        if not self.is_processing:
            return
        
        # Check if queue has pending items
        pending_count = self.job_queue.qsize()
        
        confirm = False
        clear_queue = False
        
        if pending_count > 0:
             # askyesnocancel: Yes=True (Clear All), No=False (Current Only), Cancel=None
             ans = messagebox.askyesnocancel("Cancel Process", 
                  f"There are {pending_count} jobs pending in the queue.\n\n"
                  "Do you want to cancel ALL pending jobs as well?\n\n"
                  "Yes: Cancel Current + Clear Queue\n"
                  "No: Cancel Current Only (Queue continues)\n"
                  "Cancel: Return (Do nothing)")
             
             if ans is None:
                 return
             elif ans is True:
                 confirm = True
                 clear_queue = True
             else:
                 confirm = True
        else:
            if messagebox.askyesno("Cancel Process", "Are you sure you want to cancel? This will stop the current operation and clean up temporary files."):
                confirm = True

        if confirm:
            if clear_queue:
                with self.job_queue.mutex:
                    self.job_queue.queue.clear()
                self.queue_list.delete(0, tk.END)
                self.log("Queue cleared by user.")
                
            self.log("Cancelling process...")
            self.cancel_event.set()
            self.cancel_button.configure(state='disabled')
            self.update_progress(0, "Cancelling...")

    def update_progress(self, value, status=None, eta=None):
        self.msg_queue.put(("progress", (value, status, eta)))

    def run_command_thread(self, cmd, callback=None, callback_arg=None):
        def target():
            self.log(f"Running: {' '.join(cmd)}")
            try:
                startupinfo = None
                if os.name == 'nt':
                    startupinfo = subprocess.STARTUPINFO()
                    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                
                process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                    universal_newlines=True,
                    startupinfo=startupinfo,
                    cwd=os.getcwd()
                )
                
                for line in process.stdout:
                    self.log(line.strip())
                
                process.wait()
                if process.returncode == 0:
                    self.log("Command completed successfully.")
                    if callback:
                        if callback_arg:
                            self.root.after(0, lambda: callback(callback_arg))
                        else:
                            self.root.after(0, callback)
                else:
                    self.log(f"Command failed with return code {process.returncode}")
            except Exception as e:
                self.log(f"Error executing command: {e}")

        threading.Thread(target=target, daemon=True).start()

    def open_output_folder(self):
        folder = os.getcwd()
        if os.name == 'nt':
            os.startfile(folder)
        else:
            subprocess.Popen(['xdg-open', folder])

    def setup_files_tab(self):
        frame = self.tab_files
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(0, weight=1)
        
        # Treeview
        columns = ('file_name', 'video_id', 'size', 'date')
        self.tree = ttk.Treeview(frame, columns=columns, show='headings')
        self.tree.heading('file_name', text='File Name')
        self.tree.heading('video_id', text='Video ID')
        self.tree.heading('size', text='Size (Bytes)')
        self.tree.heading('date', text='Date')
        
        self.tree.column('file_name', width=200)
        self.tree.column('video_id', width=150)
        self.tree.column('size', width=100)
        self.tree.column('date', width=150)
        
        self.tree.grid(row=0, column=0, sticky='nsew', padx=5, pady=5)
        
        # Scrollbar
        scrollbar = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscroll=scrollbar.set)
        scrollbar.grid(row=0, column=1, sticky='ns')
        
        # Buttons
        btn_frame = ttk.Frame(frame)
        btn_frame.grid(row=1, column=0, columnspan=2, sticky='ew', padx=5, pady=5)
        
        ttk.Button(btn_frame, text="Refresh", command=self.refresh_file_list, bootstyle="info").pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Delete Selected", command=self.delete_selected, bootstyle="danger").pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Open Folder", command=self.open_output_folder, bootstyle="secondary").pack(side='left', padx=5)

        # Cookie Selector for Restore
        cookie_frame = ttk.LabelFrame(frame, text="Restore Options (For Private Videos)")
        cookie_frame.grid(row=2, column=0, columnspan=2, sticky='ew', padx=5, pady=5)
        
        ttk.Label(cookie_frame, text="Use Cookies From:").pack(side='left', padx=5)
        self.files_cookie_file_path = tk.StringVar()
        
        ttk.Button(cookie_frame, text="Select cookies.txt", command=self.browse_files_cookie_file).pack(side='left', padx=5)
        self.files_cookie_label = ttk.Label(cookie_frame, textvariable=self.files_cookie_file_path, foreground="blue", font=("Arial", 8))
        self.files_cookie_label.pack(side='left', padx=5)
        
        ttk.Label(cookie_frame, text="(Leave empty for Public/Unlisted videos)").pack(side='left', padx=5)

    def browse_files_cookie_file(self):
        filename = filedialog.askopenfilename(filetypes=[("Text Files", "*.txt"), ("All Files", "*.*")])
        if filename:
            self.files_cookie_file_path.set(filename)

    def refresh_file_list(self):
        for i in self.tree.get_children():
            self.tree.delete(i)
            
        try:
            db = FileDatabase()
            files = db.list_files()
            if not files:
                self.log("Database empty.")
                return

            for entry in files:
                file_name = entry.get('file_name', 'Unknown')
                video_id = entry.get('video_id', 'Unknown')
                file_size = entry.get('file_size', 0)
                upload_date = entry.get('upload_date', 0)
                file_id = entry.get('id') # UUID
                
                date_str = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(upload_date))
                
                # Use file_id as the item ID (iid)
                if file_id:
                    self.tree.insert('', 'end', iid=file_id, values=(file_name, video_id, file_size, date_str))
                else:
                    # Fallback for very old legacy if migration failed (unlikely)
                    self.tree.insert('', 'end', values=(file_name, video_id, file_size, date_str))
                    
        except Exception as e:
            self.log(f"Error loading database: {e}")

    def restore_selected(self):
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("Warning", "Please select a file to restore.")
            return
            
        # Get Item
        item = self.tree.item(selected[0])
        video_id = item['values'][1]
        file_name = item['values'][0]
        
        if video_id == "pending_upload":
            messagebox.showwarning("Warning", "This file is pending upload and cannot be downloaded from YouTube.")
            return

        output_file = filedialog.asksaveasfilename(
            title="Save Restored File As...",
            initialfile=file_name
        )
        if not output_file:
            return
            
        # Ask for password proactively (since we don't have a field here)
        password = simpledialog.askstring("Password", "Enter password (leave empty if none):", show='*')

        # 1. Download
        import time
        import uuid
        timestamp = int(time.time())
        download_dir = os.path.join("data", "temp", f"download_{video_id}_{timestamp}_{uuid.uuid4().hex[:8]}")
        
        cookie_file = self.files_cookie_file_path.get()
        
        # Get Threads
        try:
            threads = self.setting_threads.get()
        except:
            threads = max(1, os.cpu_count() - 1)
            
        def worker():
            try:
                # 1. Download
                self.update_progress(0, "Downloading from YouTube...")
                self.log(f"Starting download: {video_id}")
                
                yt = YouTubeStorage()
                success = yt.download(video_id, download_dir, cookies_file=cookie_file)
                
                if not success:
                    raise Exception("Download failed. Check logs.")
                
                self.log("Download complete.")
                
                # 2. Decode
                self.update_progress(50, "Decoding...")
                self.log("Decoding frames...")
                
                def decode_cb(pct):
                    # Decode is 50-100%
                    self.update_progress(50 + (pct * 0.5), f"Decoding... {pct}%")
                
                # Pass password here
                decoder = Decoder(download_dir, output_file, password=password, progress_callback=decode_cb, threads=threads)
                decoder.run()
                
                self.update_progress(100, "Restore Complete")
                self.log(f"File restored to: {output_file}")
                
                self.msg_queue.put(("success", ("Success", f"File restored successfully to:\n{output_file}")))
                
                # Cleanup
                try:
                    shutil.rmtree(download_dir)
                except:
                    pass

            except Exception as e:
                self.log(f"Error: {e}")
                self.msg_queue.put(("error", ("Error", str(e))))
                self.update_progress(0, "Error")

        threading.Thread(target=worker, daemon=True).start()
        
    def delete_selected(self):
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("Warning", "Please select a file to delete.")
            return
            
        item = self.tree.item(selected[0])
        file_name = item['values'][0]
        file_id = selected[0] # This is the UUID
        
        if messagebox.askyesno("Confirm", f"Are you sure you want to remove '{file_name}' from the database?"):
            try:
                db = FileDatabase()
                db.remove_file(file_id)
                    
                self.refresh_file_list()
                self.log(f"Removed '{file_name}' (ID: {file_id}) from database.")
            except Exception as e:
                self.log(f"Error removing file: {e}")

    # --- Upload Tab ---
    def setup_upload_tab(self):
        frame = self.tab_upload
        frame.columnconfigure(1, weight=1)
        
        # File Selection
        ttk.Label(frame, text="Select Files/Folders:").grid(row=0, column=0, sticky='w', padx=5, pady=5)
        
        file_frame = ttk.Frame(frame)
        file_frame.grid(row=0, column=1, sticky='ew', padx=5, pady=5)
        file_frame.columnconfigure(0, weight=1)
        
        self.upload_file_list = tk.Listbox(file_frame, height=5, selectmode=tk.EXTENDED)
        self.upload_file_list.grid(row=0, column=0, sticky='ew')
        
        # Scrollbar for listbox
        scrollbar = ttk.Scrollbar(file_frame, orient="vertical", command=self.upload_file_list.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.upload_file_list.config(yscrollcommand=scrollbar.set)
        
        btn_box = ttk.Frame(file_frame)
        btn_box.grid(row=1, column=0, columnspan=2, sticky='ew', pady=5)
        ttk.Button(btn_box, text="Add Files", command=self.browse_upload_files, bootstyle="primary-outline").pack(side='left', padx=2)
        ttk.Button(btn_box, text="Add Folder", command=self.browse_upload_folder, bootstyle="primary-outline").pack(side='left', padx=2)
        ttk.Button(btn_box, text="Clear", command=self.clear_upload_list, bootstyle="secondary-outline").pack(side='left', padx=2)
        
        # Output Directory
        ttk.Label(frame, text="Output Directory:").grid(row=1, column=0, sticky='w', padx=5, pady=5)
        self.upload_output_path = tk.StringVar(value=os.path.join(os.getcwd(), "output_frames"))
        ttk.Entry(frame, textvariable=self.upload_output_path).grid(row=1, column=1, sticky='ew', padx=5, pady=5)
        ttk.Button(frame, text="Browse", command=self.browse_output_dir, bootstyle="secondary-outline").grid(row=1, column=2, padx=5, pady=5)
        
        # Password
        ttk.Label(frame, text="Password (Optional):").grid(row=2, column=0, sticky='w', padx=5, pady=5)
        self.upload_password = tk.StringVar()
        ttk.Entry(frame, textvariable=self.upload_password, show="*").grid(row=2, column=1, sticky='ew', padx=5, pady=5)
        
        # Zip Name (Optional - for single folder/multi-file)
        ttk.Label(frame, text="Zip Name (Optional):").grid(row=3, column=0, sticky='w', padx=5, pady=5)
        self.upload_zip_name = tk.StringVar()
        ttk.Entry(frame, textvariable=self.upload_zip_name).grid(row=3, column=1, sticky='ew', padx=5, pady=5)
        ttk.Label(frame, text="(Leave empty for auto-name)", bootstyle="secondary").grid(row=3, column=2, sticky='w', padx=5)

        # Action Buttons
        action_frame = ttk.Frame(frame)
        action_frame.grid(row=4, column=0, columnspan=3, pady=20)
        
        ttk.Button(action_frame, text="Start Encoding", command=lambda: self.start_encode_stitch_wrapper(queue=False), bootstyle="success").pack(side='left', padx=10)
        ttk.Button(action_frame, text="Add to Queue", command=lambda: self.start_encode_stitch_wrapper(queue=True), bootstyle="info").pack(side='left', padx=10)

        # Step 2: Register Upload
        step2_frame = ttk.LabelFrame(frame, text="Step 2: Register Upload (After YouTube Upload)")
        step2_frame.grid(row=5, column=0, columnspan=3, sticky='ew', padx=10, pady=10)
        
        self.upload_video_path_label = ttk.Label(step2_frame, text="Video Path: (Waiting for encoding...)", foreground="gray")
        self.upload_video_path_label.pack(anchor='w', padx=5, pady=5)
        
        # Helper Buttons
        helper_frame = ttk.Frame(step2_frame)
        helper_frame.pack(anchor='w', padx=5, pady=0)
        
        ttk.Button(helper_frame, text="Open YouTube Upload", command=lambda: webbrowser.open("https://studio.youtube.com/channel/UC/videos/upload?d=ud"), bootstyle="danger-outline").pack(side='left', padx=5)
        
        def copy_path():
             path = self.upload_video_path_label.cget("text")
             if "Video Path: " in path:
                 path = path.replace("Video Path: ", "").strip()
                 
             if path and path != "(Waiting for encoding...)":
                 self.root.clipboard_clear()
                 self.root.clipboard_append(path)
                 messagebox.showinfo("Copied", "Video path copied to clipboard!")
             else:
                 messagebox.showwarning("Warning", "No video path available yet.")
        
        ttk.Button(helper_frame, text="Copy Path", command=copy_path, bootstyle="secondary-outline").pack(side='left', padx=5)
        
        # Last Encoded File Name
        self.last_encoded_filename = None
        self.lbl_encoded_name = ttk.Label(step2_frame, text="File to Register: None")
        self.lbl_encoded_name.pack(anchor='w', padx=5, pady=0)

        reg_box = ttk.Frame(step2_frame)
        reg_box.pack(fill='x', padx=5, pady=5)
        
        ttk.Label(reg_box, text="YouTube Video ID:").pack(side='left', padx=5)
        self.video_id_var = tk.StringVar()
        ttk.Entry(reg_box, textvariable=self.video_id_var, width=20).pack(side='left', padx=5)
        
        self.register_btn = ttk.Button(reg_box, text="Register", command=self.register_upload, state='disabled', bootstyle="warning")
        self.register_btn.pack(side='left', padx=5)
        
        ttk.Label(step2_frame, text="1. Upload the generated video to YouTube.\n2. Copy the Video ID.\n3. Paste it above and click Register.", font=("Arial", 8), foreground="gray").pack(anchor='w', padx=5, pady=5)

    def start_encode_stitch_wrapper(self, queue=False):
        files = self.upload_file_list.get(0, tk.END)
        if not files:
            messagebox.showwarning("Warning", "Please select files to upload.")
            return
            
        output_path = self.upload_output_path.get()
        password = self.upload_password.get()
        zip_name = self.upload_zip_name.get()
        auto_cleanup = self.setting_auto_cleanup.get()
        
        if queue:
            self.add_to_queue('encode', files=files, output_path=output_path, password=password, zip_name=zip_name, auto_cleanup=auto_cleanup)
        else:
            threading.Thread(target=self.start_encode_stitch, args=(files, output_path, password, zip_name, auto_cleanup), daemon=True).start()

    def browse_upload_files(self):
        filenames = filedialog.askopenfilenames()
        for f in filenames:
            self.upload_file_list.insert(tk.END, f)

    def browse_upload_folder(self):
        folder = filedialog.askdirectory()
        if folder:
            self.upload_file_list.insert(tk.END, folder)

    def clear_upload_list(self):
        self.upload_file_list.delete(0, tk.END)

    def browse_output_dir(self):
        folder = filedialog.askdirectory()
        if folder:
            self.upload_output_path.set(folder)

    def browse_restore_video(self):
        filenames = filedialog.askopenfilenames(filetypes=[("Video Files", "*.mp4;*.avi;*.mkv"), ("All Files", "*.*")])
        if filenames:
            # Join multiple files with semicolon
            self.restore_video_path.set("; ".join(filenames))

    def browse_restore_output(self):
        folder = filedialog.askdirectory()
        if folder:
            self.restore_output_dir.set(folder)


    def start_encode_stitch(self, input_paths, output_path, password=None, zip_name=None, auto_cleanup=True):
        if not input_paths:
            self.msg_queue.put(("error", ("Warning", "No input files provided.")))
            return
            
        # Determine if we need to zip
        should_zip = False
        zip_base_name = "archive"
        
        if len(input_paths) > 1:
            should_zip = True
        elif len(input_paths) == 1:
             if os.path.isdir(input_paths[0]):
                 should_zip = True
                 zip_base_name = os.path.basename(input_paths[0])
        
        if zip_name:
            zip_base_name = zip_name
        elif should_zip:
             # If called from queue without name, we might need a default or logic to ask (but asking in thread is bad)
             # Ideally zip_name should be passed. If not, use default.
             pass
        
        # Get Advanced Settings
        try:
            block_size = self.setting_block_size.get()
            ecc_bytes = self.setting_ecc_bytes.get()
            threads = self.setting_threads.get()
        except:
            block_size = DEFAULT_BLOCK_SIZE
            ecc_bytes = DEFAULT_ECC_BYTES
            threads = max(1, os.cpu_count() - 1)
        
        # Determine Compression
        comp_setting = self.setting_compression.get()
        if "Store" in comp_setting:
            zip_method = zipfile.ZIP_STORED
            compress_level = None
        elif "Best" in comp_setting:
            zip_method = zipfile.ZIP_LZMA
            compress_level = None # LZMA doesn't support level in zipfile
        elif "BZIP2" in comp_setting:
            zip_method = zipfile.ZIP_BZIP2
            compress_level = None
        else:
            # Default Fast (Deflate)
            zip_method = zipfile.ZIP_DEFLATED
            compress_level = 1
            
        def worker():
            self.cancel_event.clear()
            self.msg_queue.put(("set_cancel_state", "normal"))
            
            def check_cancel():
                if self.cancel_event.is_set():
                    raise Exception("Process Cancelled")
            
            try:
                # Disk Space Check
                total_input_size = 0
                for path in input_paths:
                    if os.path.isfile(path):
                        total_input_size += os.path.getsize(path)
                    elif os.path.isdir(path):
                        for root, _, files in os.walk(path):
                            for file in files:
                                total_input_size += os.path.getsize(os.path.join(root, file))
                
                # Estimate required space: ~1.5x for Zip + ~10x for Frames/Overhead
                required_space = total_input_size * 12
                
                free_space = shutil.disk_usage(".").free
                if free_space < total_input_size * 2:
                     self.msg_queue.put(("error", ("Disk Space Error", f"Not enough disk space to proceed.\nRequired: ~{(total_input_size*2)/(1024**3):.2f} GB (Critical)\nFree: {free_space/(1024**3):.2f} GB")))
                     self.update_progress(0, "Error: Low Disk Space")
                     return
                
                if free_space < required_space:
                    self.log(f"WARNING: Low disk space. Required ~{required_space/(1024**3):.2f} GB, Free {free_space/(1024**3):.2f} GB. Encoding might fail.")

                processing_file = None
                temp_zip = None
                unique_dir = None
                
                import time
                import uuid
                timestamp = int(time.time())
                unique_suffix = f"{timestamp}_{uuid.uuid4().hex[:8]}"
                
                if should_zip:
                    self.update_progress(0, "Zipping content...")
                    self.log(f"Zipping {len(input_paths)} items...")
                    
                    # Create name for zip
                    base_name = zip_base_name
                    
                    # Ensure base_name is safe
                    base_name = "".join([c for c in base_name if c.isalnum() or c in (' ', '.', '_', '-')]).strip() or "archive"
                         
                    unique_dir = os.path.join("data", "processing", f"{base_name}_{unique_suffix}")
                    os.makedirs(unique_dir, exist_ok=True)
                    
                    temp_zip = os.path.join(unique_dir, f"{base_name}.zip")
                    
                    # Zip logic
                    # 1. Calculate total size and collect files
                    files_to_zip = []
                    total_bytes = 0
                    
                    self.update_progress(0, "Preparing to zip...")
                    
                    for path in input_paths:
                        if os.path.isfile(path):
                            files_to_zip.append((path, os.path.basename(path)))
                            total_bytes += os.path.getsize(path)
                        elif os.path.isdir(path):
                            for root, dirs, files in os.walk(path):
                                for file in files:
                                    abs_path = os.path.join(root, file)
                                    # Calculate relative path
                                    rel_path = os.path.relpath(abs_path, os.path.dirname(path))
                                    files_to_zip.append((abs_path, rel_path))
                                    total_bytes += os.path.getsize(abs_path)
                    
                    processed_bytes = 0
                    last_update = 0
                    
                    # 2. Zip with progress and optimized compression
                    # compresslevel=1 is much faster than default (9) with similar ratio for most data
                    
                    zip_args = {'mode': 'w', 'compression': zip_method}
                    if compress_level is not None:
                         zip_args['compresslevel'] = compress_level
                         
                    with zipfile.ZipFile(temp_zip, **zip_args) as zipf:
                        for abs_path, arcname in files_to_zip:
                            file_size = os.path.getsize(abs_path)
                            
                            # Update status
                            self.update_progress((processed_bytes / total_bytes) * 100 if total_bytes > 0 else 0, 
                                               f"Zipping ({comp_setting}): {os.path.basename(abs_path)}")
                            
                            # Ensure forward slashes for zip compatibility
                            arcname = arcname.replace(os.sep, '/')
                            
                            # Create ZipInfo to preserve timestamps/permissions
                            zinfo = zipfile.ZipInfo.from_file(abs_path, arcname=arcname)
                            zinfo.compress_type = zip_method
                            # zipfile handles level via the constructor for DEFLATED in 3.7+
                            
                            # Use open/write for chunked progress on large files
                            with zipf.open(zinfo, 'w') as dest:
                                with open(abs_path, 'rb') as src:
                                    while True:
                                        check_cancel()
                                        buf = src.read(1024 * 1024) # 1MB Chunk
                                        if not buf:
                                            break
                                        dest.write(buf)
                                        processed_bytes += len(buf)
                                        
                                        # Update progress every 10MB or so to avoid UI flooding
                                        if processed_bytes - last_update > 10 * 1024 * 1024:
                                            pct = (processed_bytes / total_bytes) * 100 if total_bytes > 0 else 0
                                            self.update_progress(pct, f"Zipping... {int(pct)}%")
                                            last_update = processed_bytes

                    self.update_progress(100, "Zipping complete")

                    
                    processing_file = temp_zip
                    self.log(f"Content zipped to: {processing_file}")
                    
                else:
                    # Single file case
                    processing_file = input_paths[0]
                    file_name = os.path.basename(processing_file)
                    unique_dir = os.path.join("data", "processing", f"{file_name}_{unique_suffix}")
                    os.makedirs(unique_dir, exist_ok=True)
                
                # Split Logic
                split_size_str = self.setting_split_size.get()
                split_size = None
                if split_size_str and split_size_str != "No Split":
                    size_map = {"100 MB": 100*1024**2, "1 GB": 1024**3, "2 GB": 2*1024**3, "4 GB": 4*1024**3, "10 GB": 10*1024**3, "20 GB": 20*1024**3, "50 GB": 50*1024**3}
                    split_size = size_map.get(split_size_str)

                files_to_process = []
                if split_size and os.path.getsize(processing_file) > split_size:
                    self.log(f"File size larger than {split_size_str}, splitting...")
                    from src import file_utils
                    
                    def split_progress(current, total):
                         self.update_progress((current/total)*100, f"Splitting... {current/1024/1024:.1f} MB")
                         check_cancel()
                    
                    split_dir = os.path.join(unique_dir, "split_parts")
                    os.makedirs(split_dir, exist_ok=True)
                    
                    chunks = file_utils.split_file(processing_file, split_size, output_dir=split_dir, progress_callback=split_progress)
                    files_to_process = chunks
                    self.log(f"Split into {len(chunks)} parts.")
                else:
                    files_to_process = [processing_file]

                generated_videos = []
                
                from src.config import VIDEO_WIDTH, VIDEO_HEIGHT, FPS, RS_BLOCK_SIZE
                
                total_files = len(files_to_process)
                
                for idx, current_file in enumerate(files_to_process):
                    is_part = total_files > 1
                    part_str = f" [Part {idx+1}/{total_files}]" if is_part else ""
                    
                    self.log(f"Processing{part_str}: {os.path.basename(current_file)}")
                    
                    file_size = os.path.getsize(current_file)
                    
                    data_width = VIDEO_WIDTH // block_size
                    data_height = VIDEO_HEIGHT // block_size
                    bits_per_frame = data_width * data_height
                    bytes_per_frame = bits_per_frame / 8
                    
                    if ecc_bytes >= RS_BLOCK_SIZE:
                         raise Exception("ECC Bytes must be less than 255.")
                         
                    data_ratio = (RS_BLOCK_SIZE - ecc_bytes) / RS_BLOCK_SIZE
                    total_bytes_needed = file_size / data_ratio
                    frames_needed = total_bytes_needed / bytes_per_frame
                    seconds_needed = frames_needed / FPS
                    hours_needed = seconds_needed / 3600
                    
                    if hours_needed > 12:
                         raise Exception(f"Estimated video length for part {idx+1} is {hours_needed:.1f} hours (limit 12h).")
                    
                    part_dir = os.path.join(unique_dir, f"part_{idx+1}") if is_part else unique_dir
                    os.makedirs(part_dir, exist_ok=True)
                    
                    frames_dir = os.path.join(part_dir, "frames")
                    verify_dir = os.path.join(part_dir, "verify_frames")
                    verify_output = os.path.join(part_dir, "verify_restored_file")
                    
                    base_name = os.path.basename(current_file)
                    
                    if not os.path.isdir(output_path):
                        os.makedirs(output_path, exist_ok=True)

                    # Generate clean unique filename with suffix to prevent extension hiding confusion
                    # e.g. "doc.zip.mp4" might show as "doc.zip" if extensions are hidden.
                    # "doc.zip_yotu.mp4" shows as "doc.zip_yotu" which is safer.
                    video_filename = f"{base_name}_yotu.mp4"
                    video_file = os.path.join(output_path, video_filename)
                    
                    counter = 1
                    while os.path.exists(video_file):
                        video_file = os.path.join(output_path, f"{base_name}_yotu_{counter}.mp4")
                        counter += 1

                    # 1. Encode
                    self.update_progress(0, f"Encoding{part_str}...")
                    self.log(f"Starting encoding: {base_name}")
                    
                    def progress_cb(pct):
                        self.update_progress(pct * 0.5, f"Encoding{part_str}... {pct}%")
                    
                    encoder = Encoder(current_file, frames_dir, password=password, progress_callback=progress_cb,
                                      block_size=block_size, ecc_bytes=ecc_bytes, threads=threads, check_cancel=check_cancel)
                    encoder.run()
                    
                    # 2. Stitch
                    self.update_progress(50, f"Stitching{part_str}...")
                    video_encoder = self.setting_encoder.get()
                    stitch_frames(frames_dir, video_file, encoder=video_encoder, check_cancel=check_cancel)
                    self.log(f"Video created: {os.path.basename(video_file)}")
                    
                    # 3. Auto-Verification
                    self.update_progress(60, f"Verifying{part_str}...")
                    extract_frames(video_file, verify_dir, check_cancel=check_cancel)
                    
                    def decode_cb(pct):
                        self.update_progress(70 + (pct * 0.25), f"Verifying{part_str}... {pct}%")
                    
                    decoder = Decoder(verify_dir, verify_output, password=password, progress_callback=decode_cb, threads=threads, check_cancel=check_cancel)
                    decoder.run()
                    
                    # Compare checksums
                    self.update_progress(95, f"Checking integrity{part_str}...")
                    original_hash = self.get_file_hash(current_file)
                    restored_hash = self.get_file_hash(decoder.output_file)
                    
                    if original_hash == restored_hash:
                        self.log(f"Verification SUCCESS{part_str}.")
                        generated_videos.append(video_file)
                        
                        if auto_cleanup:
                             try:
                                 shutil.rmtree(part_dir)
                                 if is_part and os.path.exists(current_file):
                                     os.remove(current_file)
                             except:
                                 pass
                    else:
                        raise Exception(f"Verification Failed for part {idx+1}")

                if len(generated_videos) > 0:
                    self.update_progress(100, "All tasks completed")
                    msg_text = "Videos created successfully:\n" + "\n".join([os.path.basename(v) for v in generated_videos])
                    self.msg_queue.put(("success", ("Process Complete", msg_text)))
                    
                    # Just add the first video to the upload tab or maybe all?
                    if len(generated_videos) > 0:
                        self.msg_queue.put(("upload_step_2", (generated_videos[0], os.path.basename(generated_videos[0]))))
                    
                    if auto_cleanup and unique_dir:
                         try:
                             shutil.rmtree(unique_dir)
                         except:
                             pass

            except Exception as e:
                if str(e) == "Process Cancelled":
                    self.log("Process cancelled by user.")
                    self.update_progress(0, "Cancelled")
                    # Cleanup
                    try:
                        if unique_dir and os.path.exists(unique_dir):
                            shutil.rmtree(unique_dir)
                            self.log("Cleanup: Temporary files removed.")
                        
                        # Also clean up partial video file if it exists
                        if 'video_file' in locals() and video_file and os.path.exists(video_file):
                             try:
                                 os.remove(video_file)
                                 self.log(f"Cleanup: Removed partial video file {os.path.basename(video_file)}")
                             except:
                                 pass
                    except:
                        pass
                else:
                    self.log(f"Error: {e}")
                    import traceback
                    traceback.print_exc()
                    self.msg_queue.put(("error", ("Error", str(e))))
                    self.update_progress(0, "Error")
            finally:
                self.msg_queue.put(("set_cancel_state", "disabled"))
                self.msg_queue.put(("job_finished", None))

        threading.Thread(target=worker, daemon=True).start()

    def batch_restore_task(self, video_paths, output_dir, password=None, auto_cleanup=True):
        try:
            threads = self.setting_threads.get()
        except:
            threads = max(1, os.cpu_count() - 1)
            
        self.cancel_event.clear()
        self.msg_queue.put(("set_cancel_state", "normal"))
        
        def check_cancel():
            if self.cancel_event.is_set():
                raise Exception("Process Cancelled")

        restored_files = []
        
        try:
            total_files = len(video_paths)
            for i, video_path in enumerate(video_paths):
                check_cancel()
                
                # Calculate progress range for this file
                pct_per_file = 100.0 / total_files
                base_pct = i * pct_per_file
                
                self.log(f"Processing file {i+1}/{total_files}: {os.path.basename(video_path)}")
                
                try:
                    outfile = self._restore_file_internal(
                        video_path, output_dir, password, auto_cleanup,
                        threads, check_cancel,
                        progress_base=base_pct, progress_scale=pct_per_file/100.0
                    )
                    if outfile:
                        restored_files.append(outfile)
                except Exception as e:
                    if str(e) == "Process Cancelled":
                        raise e
                    self.log(f"Error restoring {video_path}: {e}")
                    import traceback
                    traceback.print_exc()
            
            # Auto-Join Logic
            final_files = list(restored_files)
            if len(restored_files) > 1:
                self.log("Checking for split files to join...")
                try:
                    from src.file_utils import auto_join_restored_files
                    
                    def join_progress(processed, total):
                        if total > 0:
                            pct = (processed / total) * 100
                            self.update_progress(95 + (pct * 0.05), f"Joining Files... {int(pct)}%")
                        
                    final_files = auto_join_restored_files(
                        restored_files, 
                        log_callback=self.log, 
                        progress_callback=join_progress,
                        auto_cleanup=auto_cleanup
                    )
                    
                except Exception as e:
                    self.log(f"Auto-join warning: {e}")

            self.update_progress(100, "All Tasks Complete")
            
            msg = f"Restored {len(restored_files)} files."
            if len(final_files) != len(restored_files):
                msg += f"\n(Auto-joined into {len(final_files)} files)"
                
            file_list_str = "\n".join([os.path.basename(f) for f in final_files])
            if len(file_list_str) > 500: file_list_str = file_list_str[:500] + "..."
            
            self.msg_queue.put(("success", ("Success", f"{msg}\n\n{file_list_str}")))
            
        except Exception as e:
            if str(e) == "Process Cancelled":
                self.log("Process cancelled by user.")
                self.update_progress(0, "Cancelled")
                # Cleanup handled in internal function for temp dirs
            else:
                self.log(f"Error: {e}")
                import traceback
                traceback.print_exc()
                self.msg_queue.put(("error", ("Error", str(e))))
                self.update_progress(0, "Error")
        finally:
            self.msg_queue.put(("set_cancel_state", "disabled"))
            self.msg_queue.put(("job_finished", None))

    def _restore_file_internal(self, video_path, output_dir, password, auto_cleanup, threads, check_cancel_func, progress_base=0, progress_scale=1.0):
        unique_dir = None
        
        try:
            import time
            import uuid
            timestamp = int(time.time())
            
            # Unique temp dir for extraction
            video_name = os.path.splitext(os.path.basename(video_path))[0]
            unique_dir = os.path.join("data", "processing", f"restore_{video_name}_{timestamp}_{uuid.uuid4().hex[:8]}")
            frames_dir = os.path.join(unique_dir, "frames")
            os.makedirs(frames_dir, exist_ok=True)
            
            # Ensure output directory exists
            os.makedirs(output_dir, exist_ok=True)
            
            # 1. Extract Frames
            self.update_progress(progress_base, f"Extracting {os.path.basename(video_path)}...")
            self.log(f"Extracting frames from: {video_path}")
            
            extract_frames(video_path, frames_dir, check_cancel=check_cancel_func)
            
            # 2. Decode
            self.update_progress(progress_base + (40 * progress_scale), f"Decoding {os.path.basename(video_path)}...")
            self.log("Decoding...")
            
            # Pass the directory so Decoder can use the internal filename from header
            output_target = output_dir
            
            def decode_cb(pct):
                local_pct = 40 + (pct * 0.6)
                global_pct = progress_base + (local_pct * progress_scale)
                self.update_progress(global_pct, f"Decoding {os.path.basename(video_path)}... {pct}%")
            
            decoder = Decoder(frames_dir, output_target, password=password, progress_callback=decode_cb, threads=threads, check_cancel=check_cancel_func)
            decoder.run()
            
            final_output = decoder.output_file
            self.log(f"Restored: {final_output}")
            
            # Cleanup
            try:
                if auto_cleanup:
                    shutil.rmtree(unique_dir)
            except:
                pass
                
            return final_output

        except Exception as e:
            # Cleanup on error
            try:
                if unique_dir and os.path.exists(unique_dir):
                    shutil.rmtree(unique_dir)
            except:
                pass
            raise e

    # Backward compatibility wrapper
    def decode_extract_task(self, video_path, output_dir, password=None, auto_cleanup=True):
        self.batch_restore_task([video_path], output_dir, password, auto_cleanup)



    def get_file_hash(self, filepath):
        import hashlib
        md5 = hashlib.md5()
        with open(filepath, 'rb') as f:
            for chunk in iter(lambda: f.read(4096), b""):
                md5.update(chunk)
        return md5.hexdigest()

    def finish_encode_stitch(self, video_file):
        # Deprecated by direct thread usage, but keeping for reference if needed
        pass

    def enable_upload_step_2(self, video_path, filename=None):
        self.register_btn.config(state='normal')
        self.upload_video_path_label.config(text=f"Video Path: {video_path}", foreground="green")
        if filename:
            self.last_encoded_filename = filename
            self.lbl_encoded_name.config(text=f"File to Register: {filename}", foreground="green")

    def register_upload(self):
        video_id = self.video_id_var.get()
        if not video_id:
             messagebox.showwarning("Warning", "Please enter a Video ID.")
             return
             
        file_name = self.last_encoded_filename
        
        if not file_name:
             messagebox.showerror("Error", "No file ready to register. Please encode a file first.")
             return
             
        try:
            # Register in DB
            db = FileDatabase()
            # We don't know the exact size unless we tracked it, but '0' is fine as placeholder
            db.add_file(file_name, video_id, 0, {"status": "uploaded"})
            
            self.refresh_file_list()
            messagebox.showinfo("Success", f"File '{file_name}' registered successfully!")
            
            # Reset UI
            self.video_id_var.set("")
            self.register_btn.config(state='disabled')
            self.upload_video_path_label.config(text="Video Path: (Waiting for encoding...)", foreground="gray")
            self.lbl_encoded_name.config(text="File to Register: None", foreground="black")
            self.last_encoded_filename = None
            
        except Exception as e:
            self.log(f"Error registering upload: {e}")
            messagebox.showerror("Error", f"Failed to register: {e}")

    def browse_cookie_file(self):
        filename = filedialog.askopenfilename(filetypes=[("Text Files", "*.txt"), ("All Files", "*.*")])
        if filename:
            self.cookie_file_path.set(filename)
            self.cookie_browser.set("None") # Reset browser selection

    def help_cookies(self):
        messagebox.showinfo("How to get cookies.txt", 
            "The browser integration is unstable on Windows due to encryption.\n\n"
            "RECOMMENDED METHOD:\n"
            "1. Install 'Get cookies.txt LOCALLY' extension for Chrome/Firefox.\n"
            "2. Go to YouTube and make sure you are logged in.\n"
            "3. Use the extension to export 'cookies.txt'.\n"
            "4. Select that file here.")

    # --- Restore Tab ---
    def setup_restore_tab(self):
        frame = self.tab_restore
        frame.columnconfigure(1, weight=1)
        
        # Source Selection
        ttk.Label(frame, text="Source Type:").grid(row=0, column=0, sticky='w', padx=5, pady=5)
        self.restore_source_var = tk.StringVar(value="local")
        
        source_frame = ttk.Frame(frame)
        source_frame.grid(row=0, column=1, columnspan=2, sticky='w')
        ttk.Radiobutton(source_frame, text="Local Video File", variable=self.restore_source_var, value="local", command=self.toggle_restore_source).pack(side='left', padx=5)
        ttk.Radiobutton(source_frame, text="YouTube Link/ID", variable=self.restore_source_var, value="youtube", command=self.toggle_restore_source).pack(side='left', padx=5)

        # Input Frame (Dynamic)
        self.restore_input_frame = ttk.Frame(frame)
        self.restore_input_frame.grid(row=1, column=0, columnspan=3, sticky='ew')
        self.restore_input_frame.columnconfigure(1, weight=1)

        # -- Local File Widgets --
        self.lbl_local = ttk.Label(self.restore_input_frame, text="Select Video:")
        self.restore_video_path = tk.StringVar()
        self.ent_local = ttk.Entry(self.restore_input_frame, textvariable=self.restore_video_path)
        self.btn_local = ttk.Button(self.restore_input_frame, text="Browse", command=self.browse_restore_video, bootstyle="secondary-outline")
        
        # -- YouTube Widgets --
        self.lbl_yt = ttk.Label(self.restore_input_frame, text="YouTube URL/ID:")
        self.restore_youtube_url = tk.StringVar()
        self.ent_yt = ttk.Entry(self.restore_input_frame, textvariable=self.restore_youtube_url)
        self.lbl_yt_hint = ttk.Label(self.restore_input_frame, text="(e.g. dQw4w9WgXcQ or https://youtu.be/...)", font=("Arial", 8), foreground="gray")

        # -- YouTube Cookies (Optional) --
        self.restore_cookie_file_path = tk.StringVar()
        self.lbl_cookie = ttk.Label(self.restore_input_frame, text="Cookies (Optional):")
        self.ent_cookie = ttk.Entry(self.restore_input_frame, textvariable=self.restore_cookie_file_path)
        self.btn_cookie = ttk.Button(self.restore_input_frame, text="Select cookies.txt", command=self.browse_restore_cookie_file, bootstyle="secondary-outline")
        self.lbl_cookie_hint = ttk.Label(self.restore_input_frame, text="(Required for Private/Age-gated videos)", font=("Arial", 8), foreground="gray")

        # Initial Toggle
        self.toggle_restore_source()
        
        # Output Directory
        ttk.Label(frame, text="Output Directory:").grid(row=2, column=0, sticky='w', padx=5, pady=5)
        self.restore_output_dir = tk.StringVar(value=os.path.join(os.getcwd(), "restored_files"))
        ttk.Entry(frame, textvariable=self.restore_output_dir).grid(row=2, column=1, sticky='ew', padx=5, pady=5)
        ttk.Button(frame, text="Browse", command=self.browse_restore_output, bootstyle="secondary-outline").grid(row=2, column=2, padx=5, pady=5)
        
        # Password
        ttk.Label(frame, text="Password (Optional):").grid(row=3, column=0, sticky='w', padx=5, pady=5)
        self.restore_password = tk.StringVar()
        ttk.Entry(frame, textvariable=self.restore_password, show="*").grid(row=3, column=1, sticky='ew', padx=5, pady=5)
        
        # Action Buttons
        action_frame = ttk.Frame(frame)
        action_frame.grid(row=4, column=0, columnspan=3, pady=20)
        
        ttk.Button(action_frame, text="Start Decoding", command=lambda: self.start_decode_extract_wrapper(queue=False), bootstyle="success").pack(side='left', padx=10)
        ttk.Button(action_frame, text="Add to Queue", command=lambda: self.start_decode_extract_wrapper(queue=True), bootstyle="info").pack(side='left', padx=10)

    def browse_restore_cookie_file(self):
        filename = filedialog.askopenfilename(filetypes=[("Text Files", "*.txt"), ("All Files", "*.*")])
        if filename:
            self.restore_cookie_file_path.set(filename)

    def toggle_restore_source(self):
        source = self.restore_source_var.get()
        
        # Clear Grid
        for widget in self.restore_input_frame.winfo_children():
            widget.grid_forget()

        if source == "local":
            self.lbl_local.grid(row=0, column=0, sticky='w', padx=5, pady=5)
            self.ent_local.grid(row=0, column=1, sticky='ew', padx=5, pady=5)
            self.btn_local.grid(row=0, column=2, padx=5, pady=5)
        else:
            self.lbl_yt.grid(row=0, column=0, sticky='w', padx=5, pady=5)
            self.ent_yt.grid(row=0, column=1, sticky='ew', padx=5, pady=5)
            self.lbl_yt_hint.grid(row=1, column=1, sticky='w', padx=5)
            
            # Cookies
            self.lbl_cookie.grid(row=2, column=0, sticky='w', padx=5, pady=5)
            self.ent_cookie.grid(row=2, column=1, sticky='ew', padx=5, pady=5)
            self.btn_cookie.grid(row=2, column=2, padx=5, pady=5)
            self.lbl_cookie_hint.grid(row=3, column=1, sticky='w', padx=5)

        
    def start_decode_extract_wrapper(self, queue=False):
        output_dir = self.restore_output_dir.get()
        password = self.restore_password.get()
        source = self.restore_source_var.get()
        auto_cleanup = self.setting_auto_cleanup.get()
        
        if source == "local":
            video_paths_str = self.restore_video_path.get()
            # Split by semicolon and strip
            video_paths = [p.strip() for p in video_paths_str.split(";") if p.strip()]
            
            if not video_paths:
                messagebox.showwarning("Warning", "Please select valid video file(s).")
                return
            
            # Validate existence
            valid_paths = []
            for p in video_paths:
                if os.path.exists(p):
                    valid_paths.append(p)
                else:
                    self.log(f"Warning: File not found: {p}")
            
            if not valid_paths:
                messagebox.showwarning("Warning", "No valid files found.")
                return

            if queue:
                # Add as a single batch job to support auto-join
                self.add_to_queue('decode', video_paths=valid_paths, output_dir=output_dir, password=password, auto_cleanup=auto_cleanup)
                messagebox.showinfo("Queue", f"Added batch restore job for {len(valid_paths)} files.")
            else:
                threading.Thread(target=self.batch_restore_task, args=(valid_paths, output_dir, password, auto_cleanup), daemon=True).start()
        
        else: # YouTube
            video_id_or_url = self.restore_youtube_url.get().strip()
            if not video_id_or_url:
                messagebox.showwarning("Warning", "Please enter a YouTube URL or Video ID.")
                return

            # Check if playlist
            is_playlist = "list=" in video_id_or_url
            
            if is_playlist:
                # For playlists, we need an output DIRECTORY, not a file
                output_path = filedialog.askdirectory(title="Select Output Directory for Restored Files", initialdir=output_dir)
            else:
                # Ask for output file location
                output_path = filedialog.asksaveasfilename(
                    title="Save Restored File As...",
                    defaultextension=".zip",
                    initialdir=output_dir,
                    filetypes=[("Zip Archive", "*.zip"), ("All Files", "*.*")]
                )
            
            if not output_path:
                return

            if queue:
                 self.add_to_queue('restore_youtube', video_id=video_id_or_url, output_path=output_path, password=password, auto_cleanup=auto_cleanup, is_playlist=is_playlist)
                 messagebox.showinfo("Queue", "Added YouTube restore job to queue.")
            else:
                 threading.Thread(target=self.restore_from_youtube, args=(video_id_or_url, output_path, password, auto_cleanup, is_playlist), daemon=True).start()

    def restore_from_youtube(self, video_id, output_path, password, auto_cleanup=True, is_playlist=False):
        import time
        import uuid
        import re
        
        self.cancel_event.clear()
        self.msg_queue.put(("set_cancel_state", "normal"))
        
        def check_cancel():
            if self.cancel_event.is_set():
                raise Exception("Process Cancelled")
        
        cookie_file = self.restore_cookie_file_path.get()
        try:
            threads = self.setting_threads.get()
        except:
            threads = max(1, os.cpu_count() - 1)
            
        restored_files = [] # Track files for auto-join
        
        try:
            # Prepare list of videos to process
            videos_to_process = []
            
            if is_playlist:
                self.log(f"Resolving playlist: {video_id}")
                self.update_progress(0, "Fetching playlist info...")
                
                yt_helper = YouTubeStorage()
                playlist_items = yt_helper.get_playlist_info(video_id)
                
                if not playlist_items:
                    raise Exception("No videos found in playlist or failed to fetch info.")
                
                self.log(f"Found {len(playlist_items)} videos in playlist.")
                
                # Sanitize filenames and prepare tasks
                for item in playlist_items:
                    vid_url = item.get('url')
                    vid_title = item.get('title', 'Unknown')
                    
                    # Sanitize title for filename
                    safe_title = "".join([c for c in vid_title if c.isalpha() or c.isdigit() or c in (' ', '.', '_', '-')]).rstrip()
                    if not safe_title:
                        safe_title = f"video_{item.get('id')}"
                    
                    # Output path is a directory for playlist mode
                    # We'll use the title as the filename
                    # Note: We don't know the extension, so we default to .restored or just no extension?
                    # Or maybe .zip? Let's use .restored to be safe, user can rename.
                    # Actually, if the title already has extension (e.g. "MyFile.zip.001"), use it.
                    # But if title is "My Video", we append .restored
                    
                    # Check if title looks like a filename
                    if "." in safe_title:
                        final_name = safe_title
                    else:
                        final_name = f"{safe_title}.restored"
                        
                    out_file = os.path.join(output_path, final_name)
                    videos_to_process.append((vid_url, out_file, vid_title))
                    
            else:
                # Single video
                videos_to_process.append((video_id, output_path, "Single Video"))

            total_videos = len(videos_to_process)
            
            for idx, (vid_url, out_file, vid_title) in enumerate(videos_to_process):
                timestamp = int(time.time())
                unique_id = uuid.uuid4().hex[:8]
                download_dir = os.path.join("data", "temp", f"restore_{unique_id}_{timestamp}")
                
                try:
                    check_cancel()
                    
                    # Calculate base progress for this video
                    base_pct = (idx / total_videos) * 100
                    chunk_pct = 100 / total_videos
                    
                    self.log(f"Processing ({idx+1}/{total_videos}): {vid_title}")
                    
                    # 1. Download
                    self.update_progress(base_pct, f"Downloading ({idx+1}/{total_videos})...")
                    
                    yt = YouTubeStorage()
                    kwargs = {}
                    if cookie_file:
                        kwargs['cookies_file'] = cookie_file
                    
                    success = yt.download(vid_url, download_dir, check_cancel=check_cancel, **kwargs)
                    
                    if not success:
                        self.log(f"Error: Download failed for {vid_title}")
                        continue
                    
                    # 2. Decode
                    self.update_progress(base_pct + (chunk_pct * 0.5), f"Decoding ({idx+1}/{total_videos})...")
                    
                    def decode_cb(pct):
                        # Map 0-100 to base_pct + 50% of chunk -> base_pct + 100% of chunk
                        # Actually Download is 0-50% of chunk, Decode is 50-100% of chunk
                        current_video_progress = 50 + (pct * 0.5)
                        total_progress = base_pct + (current_video_progress / 100 * chunk_pct)
                        self.update_progress(total_progress, f"Decoding ({idx+1}/{total_videos})... {int(pct)}%")
                    
                    decoder = Decoder(download_dir, out_file, password=password, progress_callback=decode_cb, threads=threads, check_cancel=check_cancel)
                    decoder.run()
                    
                    self.log(f"Restored: {out_file}")
                    restored_files.append(out_file)
                    
                except Exception as e:
                    self.log(f"Error processing {vid_title}: {e}")
                finally:
                    # Cleanup per video
                    try:
                        if auto_cleanup and os.path.exists(download_dir):
                            shutil.rmtree(download_dir)
                    except:
                        pass
            
            # Auto-Join Logic (Only if multiple files or playlist)
            if is_playlist or len(restored_files) > 1:
                self.log("Checking for split files to join...")
                try:
                    from .file_utils import auto_join_restored_files
                    
                    def join_progress(processed, total):
                        if total > 0:
                            pct = (processed / total) * 100
                            self.update_progress(95 + (pct * 0.05), f"Joining Files... {int(pct)}%")
                        
                    final_files = auto_join_restored_files(
                        restored_files, 
                        log_callback=self.log, 
                        progress_callback=join_progress,
                        auto_cleanup=auto_cleanup
                    )
                    
                    # Update restored_files list
                    restored_files = final_files
                    
                except Exception as e:
                    self.log(f"Auto-join warning: {e}")

            self.update_progress(100, "Restore Complete")
            
            msg = f"Restored {len(restored_files)} files to:\n{output_path if is_playlist else os.path.dirname(output_path)}"
            self.msg_queue.put(("success", ("Success", msg)))
            
        except Exception as e:
            if str(e) == "Process Cancelled":
                self.log("Process cancelled by user.")
                self.update_progress(0, "Cancelled")
            else:
                self.log(f"Error: {e}")
                self.msg_queue.put(("error", ("Error", str(e))))
                self.update_progress(0, "Error")
        finally:
            self.msg_queue.put(("set_cancel_state", "disabled"))



    # --- Tools Tab ---
    def setup_tools_tab(self):
        # Use ScrolledFrame to prevent overflow on smaller screens
        scrolled_frame = ScrolledFrame(self.tab_tools, autohide=True)
        scrolled_frame.pack(fill='both', expand=True, padx=5, pady=5)
        
        frame = scrolled_frame
        
        # --- Appearance ---
        app_frame = ttk.LabelFrame(frame, text="Appearance")
        app_frame.pack(fill='x', padx=10, pady=10)
        
        ttk.Label(app_frame, text="Theme:").pack(side='left', padx=5, pady=5)
        
        # Define Light/Dark themes for labeling
        light_themes = ["cosmo", "flatly", "journal", "literal", "lumen", "minty", "pulse", "sandstone", "united", "yeti", "morph", "simplex", "cerculean"]
        dark_themes = ["solar", "superhero", "cyborg", "darkly", "vapor"]
        
        available_themes = sorted(ttk.Style().theme_names())
        theme_display_names = []
        theme_map = {}
        
        for t in available_themes:
            if t in light_themes:
                display = f"{t} (Light)"
            elif t in dark_themes:
                display = f"{t} (Dark)"
            else:
                display = t
            theme_display_names.append(display)
            theme_map[display] = t
            
        # Determine current display value
        current_real = self.setting_theme.get()
        current_display = next((k for k, v in theme_map.items() if v == current_real), current_real)
        
        self.theme_display_var = tk.StringVar(value=current_display)
        
        def update_theme(event):
            selected = self.theme_display_var.get()
            real = theme_map.get(selected, selected)
            self.setting_theme.set(real)
            ttk.Style().theme_use(real)
            
        theme_cb = ttk.Combobox(app_frame, textvariable=self.theme_display_var, values=theme_display_names, state="readonly", width=20)
        theme_cb.pack(side='left', padx=5, pady=5)
        theme_cb.bind("<<ComboboxSelected>>", update_theme)
        
        # --- Advanced Encoding Settings ---
        settings_frame = ttk.LabelFrame(frame, text="Advanced Encoding Settings")
        settings_frame.pack(fill='x', padx=10, pady=10)
        
        # Video Encoder
        enc_frame = ttk.Frame(settings_frame)
        enc_frame.pack(fill='x', padx=5, pady=5)
        ttk.Label(enc_frame, text="Video Encoder:").pack(side='left', padx=5)
        encoders = ["libx264 (Software)", "h264_nvenc (NVIDIA)", "h264_qsv (Intel)", "h264_amf (AMD)"]
        # Map friendly names to values if needed, but for now we'll just store the value.
        # Ideally we store "h264_nvenc" but show "NVIDIA (h264_nvenc)"
        # Let's use simple values for now to avoid mapping logic complexity
        
        # Clean list for value matching
        encoder_values = ["libx264", "h264_nvenc", "h264_qsv", "h264_amf"]
        
        encoder_cb = ttk.Combobox(enc_frame, textvariable=self.setting_encoder, values=encoder_values, state="readonly", width=20)
        encoder_cb.pack(side='left', padx=5)
        ttk.Label(enc_frame, text="(Hardware acceleration requires supported GPU)").pack(side='left', padx=5)
        
        # Compression Level
        comp_frame = ttk.Frame(settings_frame)
        comp_frame.pack(fill='x', padx=5, pady=5)
        ttk.Label(comp_frame, text="Compression:").pack(side='left', padx=5)
        
        comp_options = ["Store (No Compression)", "Fast (Deflate)", "Best (LZMA)", "BZIP2"]
        comp_cb = ttk.Combobox(comp_frame, textvariable=self.setting_compression, values=comp_options, state="readonly", width=25)
        comp_cb.pack(side='left', padx=5)
        ttk.Label(comp_frame, text="(Trade-off: Speed vs Size)").pack(side='left', padx=5)

        # Split Size
        split_frame = ttk.Frame(settings_frame)
        split_frame.pack(fill='x', padx=5, pady=5)
        ttk.Label(split_frame, text="Split Output:").pack(side='left', padx=5)
        
        split_options = ["No Split", "100 MB", "1 GB", "2 GB", "4 GB", "10 GB", "20 GB", "50 GB"]
        split_cb = ttk.Combobox(split_frame, textvariable=self.setting_split_size, values=split_options, state="readonly", width=25)
        split_cb.pack(side='left', padx=5)
        ttk.Label(split_frame, text="(Split large files into multiple videos)").pack(side='left', padx=5)

        # Block Size
        bs_frame = ttk.Frame(settings_frame)
        bs_frame.pack(fill='x', padx=5, pady=5)
        ttk.Label(bs_frame, text="Block Size (pixels):").pack(side='left', padx=5)
        ttk.Entry(bs_frame, textvariable=self.setting_block_size, width=10).pack(side='left', padx=5)
        ttk.Label(bs_frame, text="(Recommended: 4, Min: 2)").pack(side='left', padx=5)
        
        # ECC Bytes
        ecc_frame = ttk.Frame(settings_frame)
        ecc_frame.pack(fill='x', padx=5, pady=5)
        ttk.Label(ecc_frame, text="ECC Bytes (per 255):").pack(side='left', padx=5)
        ttk.Entry(ecc_frame, textvariable=self.setting_ecc_bytes, width=10).pack(side='left', padx=5)
        ttk.Label(ecc_frame, text="(Default: 16)").pack(side='left', padx=5)
        
        # Threads
        thread_frame = ttk.Frame(settings_frame)
        thread_frame.pack(fill='x', padx=5, pady=5)
        ttk.Label(thread_frame, text="CPU Threads:").pack(side='left', padx=5)
        ttk.Entry(thread_frame, textvariable=self.setting_threads, width=10).pack(side='left', padx=5)
        ttk.Label(thread_frame, text=f"(Max: {os.cpu_count()})").pack(side='left', padx=5)
        
        # Auto Cleanup
        cleanup_frame = ttk.Frame(settings_frame)
        cleanup_frame.pack(fill='x', padx=5, pady=5)
        ttk.Checkbutton(cleanup_frame, text="Auto-Cleanup Temporary Files (Zip/Frames)", variable=self.setting_auto_cleanup).pack(side='left', padx=5)

        ttk.Button(settings_frame, text="Save Settings", command=self.save_settings).pack(anchor='w', padx=10, pady=10)

        # --- File Tools ---
        file_tools_frame = ttk.LabelFrame(frame, text="File Tools")
        file_tools_frame.pack(fill='x', padx=10, pady=10)
        
        ttk.Label(file_tools_frame, text="Join Split Files:").pack(side='left', padx=5, pady=5)
        ttk.Button(file_tools_frame, text="Select Files & Join...", command=self.open_join_tool).pack(side='left', padx=5, pady=5)
        ttk.Label(file_tools_frame, text="(Combine .001, .002... parts back into original file)").pack(side='left', padx=5)

        # Verify Video Tool
        verify_frame = ttk.LabelFrame(frame, text="Verification")
        verify_frame.pack(fill='x', padx=10, pady=5)
        
        ttk.Label(verify_frame, text="Check if a video file is a valid YotuDrive archive.").pack(anchor='w', padx=5, pady=5)
        ttk.Button(verify_frame, text="Verify Video Integrity...", command=self.open_verify_tool).pack(anchor='w', padx=5, pady=5)

        # --- Maintenance Tools ---
        ttk.Label(frame, text="Maintenance Tools", font=("Arial", 12, "bold")).pack(anchor='w', padx=10, pady=10)
        
        # Clear Cache
        cache_frame = ttk.LabelFrame(frame, text="Disk Cleanup")
        cache_frame.pack(fill='x', padx=10, pady=5)
        
        ttk.Label(cache_frame, text="Clear temporary files created during encoding and restoration.").pack(anchor='w', padx=5, pady=5)
        ttk.Button(cache_frame, text="Clear Cache (data/temp, data/processing)", command=self.clear_cache).pack(anchor='w', padx=5, pady=5)
        
        # Diagnostics
        diag_frame = ttk.LabelFrame(frame, text="Diagnostics")
        diag_frame.pack(fill='x', padx=10, pady=5)
        
        ttk.Label(diag_frame, text="View application logs for troubleshooting.").pack(anchor='w', padx=5, pady=5)
        ttk.Button(diag_frame, text="Open Log File", command=self.open_log_file).pack(anchor='w', padx=5, pady=5)
        
        # Help / About
        help_frame = ttk.LabelFrame(frame, text="About")
        help_frame.pack(fill='x', padx=10, pady=10)
        ttk.Label(help_frame, text="YotuDrive v1.1 (Header Redundancy)\nStore files on YouTube as video.").pack(anchor='w', padx=5, pady=5)
        
    def load_settings(self):
        try:
            if os.path.exists("settings.json"):
                with open("settings.json", "r") as f:
                    data = json.load(f)
                    if "block_size" in data: self.setting_block_size.set(data["block_size"])
                    if "ecc_bytes" in data: self.setting_ecc_bytes.set(data["ecc_bytes"])
                    if "threads" in data: self.setting_threads.set(data["threads"])
                    if "auto_cleanup" in data: self.setting_auto_cleanup.set(data["auto_cleanup"])
                    if "encoder" in data: self.setting_encoder.set(data["encoder"])
                    if "theme" in data: self.setting_theme.set(data["theme"])
                    if "compression" in data: self.setting_compression.set(data["compression"])
                    if "split_size" in data: self.setting_split_size.set(data["split_size"])
                    
                    # Apply theme
                    ttk.Style().theme_use(self.setting_theme.get())
                    
                    self.log("Settings loaded from settings.json")
        except Exception as e:
            self.log(f"Error loading settings: {e}")

    def save_settings(self):
        try:
            data = {
                "block_size": self.setting_block_size.get(),
                "ecc_bytes": self.setting_ecc_bytes.get(),
                "threads": self.setting_threads.get(),
                "auto_cleanup": self.setting_auto_cleanup.get(),
                "encoder": self.setting_encoder.get(),
                "theme": self.setting_theme.get(),
                "compression": self.setting_compression.get(),
                "split_size": self.setting_split_size.get()
            }
            with open("settings.json", "w") as f:
                json.dump(data, f, indent=4)
            messagebox.showinfo("Success", "Settings saved successfully.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save settings: {e}")

    def clear_cache(self):
        if not messagebox.askyesno("Confirm Cleanup", "This will delete all temporary files in 'data/temp' and 'data/processing'.\n\nEnsure no operations are currently running.\n\nContinue?"):
            return
            
        dirs_to_clean = [
            os.path.join("data", "temp"),
            os.path.join("data", "processing")
        ]
        
        deleted_count = 0
        errors = 0
        
        import shutil
        
        for d in dirs_to_clean:
            if os.path.exists(d):
                for item in os.listdir(d):
                    item_path = os.path.join(d, item)
                    try:
                        if os.path.isfile(item_path) or os.path.islink(item_path):
                            os.unlink(item_path)
                        elif os.path.isdir(item_path):
                            shutil.rmtree(item_path)
                        deleted_count += 1
                    except Exception as e:
                        print(f"Failed to delete {item_path}. Reason: {e}")
                        errors += 1
                        
        msg = f"Cleanup complete.\nDeleted {deleted_count} items."
        if errors > 0:
            msg += f"\nEncountered {errors} errors (files might be in use)."
            
        self.log("Cache cleared.")
        messagebox.showinfo("Cleanup", msg)

    def open_log_file(self):
        if self.log_file and os.path.exists(self.log_file):
            try:
                if os.name == 'nt':
                    os.startfile(self.log_file)
                else:
                    subprocess.call(('xdg-open', self.log_file))
            except Exception as e:
                messagebox.showerror("Error", f"Failed to open log file: {e}")
        else:
            messagebox.showwarning("Warning", "Log file not found.")

    def open_join_tool(self):
        # Ask for files
        files = filedialog.askopenfilenames(title="Select Split Files (e.g. .001, .002)", filetypes=[("All Files", "*.*")])
        if not files:
            return
            
        # Confirm action
        if not messagebox.askyesno("Confirm Auto-Join", f"Selected {len(files)} files.\n\nThe tool will automatically group files by name (e.g. file.zip.001, file.zip.002) and join them.\n\nOriginal split parts will be deleted if 'Auto-Cleanup' is enabled in settings.\n\nProceed?"):
            return

        # Run in thread
        threading.Thread(target=self.run_auto_join_task, args=(files,), daemon=True).start()

    def open_verify_tool(self):
        video_path = filedialog.askopenfilename(title="Select Video File to Verify", filetypes=[("Video Files", "*.mp4;*.mkv;*.webm;*.avi"), ("All Files", "*.*")])
        if not video_path:
            return
            
        self.log(f"Starting verification for: {os.path.basename(video_path)}")
        self.update_progress(0, "Verifying Video...")
        
        def task():
            try:
                from src.verifier import verify_video
                report = verify_video(video_path)
                
                # Format Report
                msg = f"Filename: {report['filename']}\n"
                msg += f"Size: {report['original_size'] / (1024*1024):.2f} MB\n"
                msg += f"Version: {report['version']}\n"
                msg += f"Encrypted: {'Yes' if report['encrypted'] else 'No'}\n"
                msg += f"Compressed: {'Yes' if report['compressed'] else 'No'}\n"
                msg += f"Chunked: {'Yes' if report['chunked_encryption'] else 'No'}\n"
                msg += f"Block Size: {report['block_size']}\n"
                msg += f"ECC Bytes: {report['ecc_bytes']}\n"
                msg += f"Header Integrity: {'OK' if report['header_crc_valid'] else 'FAIL'}\n"
                
                self.msg_queue.put(("success", ("Valid YotuDrive Archive", msg)))
                self.log(f"Verification Success: {report['filename']}")
                
            except Exception as e:
                self.log(f"Verification Failed: {e}")
                self.msg_queue.put(("error", ("Verification Failed", str(e))))
            finally:
                self.update_progress(0, "Idle")
                
        threading.Thread(target=task, daemon=True).start()

    def run_auto_join_task(self, files):
        try:
            self.msg_queue.put(("set_cancel_state", "normal"))
            self.update_progress(0, "Analyzing files...")
            self.log(f"Starting Auto-Join for {len(files)} files...")
            
            from src.file_utils import auto_join_restored_files
            
            auto_cleanup = self.setting_auto_cleanup.get()
            
            def progress(processed, total):
                if total > 0:
                    pct = (processed / total) * 100
                    self.update_progress(pct, f"Joining... {int(pct)}%")
                
            # We need to adapt the progress callback because auto_join_restored_files might call join_files multiple times
            # Actually auto_join_restored_files accepts a progress_callback that is passed to join_files.
            # But if there are multiple groups, the progress will jump 0-100 multiple times.
            # That's acceptable for now, or we can wrap it.
            
            final_files = auto_join_restored_files(
                list(files), 
                log_callback=self.log, 
                progress_callback=progress,
                auto_cleanup=auto_cleanup
            )
            
            self.update_progress(100, "Join Complete")
            self.log(f"Auto-Join complete. Resulting files: {len(final_files)}")
            
            msg = f"Auto-Join Complete.\nProcessed {len(files)} input files.\nResulting files:\n"
            # Show top 5 results
            for f in final_files[:5]:
                msg += f"- {os.path.basename(f)}\n"
            if len(final_files) > 5:
                msg += f"...and {len(final_files)-5} more."
                
            self.msg_queue.put(("success", ("Success", msg)))
            
        except Exception as e:
            self.log(f"Join Error: {e}")
            self.msg_queue.put(("error", ("Error", str(e))))
            self.update_progress(0, "Error")
        finally:
            self.msg_queue.put(("set_cancel_state", "disabled"))

if __name__ == "__main__":
    root = tk.Tk()
    app = YotuDriveGUI(root)
    root.mainloop()
