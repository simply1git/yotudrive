from __future__ import annotations

import os
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from .engine import YotuDriveEngine, EncodeSettings, DecodeSettings


class YotuDriveGUI(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("YotuDrive")
        self.geometry("960x640")

        self.engine = YotuDriveEngine()

        self._build_ui()

    # --------------------------------------------------------------------- UI
    def _build_ui(self) -> None:
        notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True)

        self.my_files_frame = ttk.Frame(notebook)
        self.encode_frame = ttk.Frame(notebook)
        self.decode_frame = ttk.Frame(notebook)
        self.tools_frame = ttk.Frame(notebook)
        self.settings_frame = ttk.Frame(notebook)

        notebook.add(self.my_files_frame, text="My Files")
        notebook.add(self.encode_frame, text="Encode (Upload)")
        notebook.add(self.decode_frame, text="Decode (Restore)")
        notebook.add(self.tools_frame, text="Tools")
        notebook.add(self.settings_frame, text="Settings")

        self._build_my_files_tab()
        self._build_encode_tab()
        self._build_decode_tab()
        self._build_tools_tab()
        self._build_settings_tab()

    # --------------------------------------------------------------- My Files
    def _build_my_files_tab(self) -> None:
        toolbar = ttk.Frame(self.my_files_frame)
        toolbar.pack(fill="x", pady=4)

        refresh_btn = ttk.Button(toolbar, text="Refresh", command=self.refresh_files)
        refresh_btn.pack(side="left", padx=4)

        self.files_tree = ttk.Treeview(
            self.my_files_frame,
            columns=("name", "size", "video", "meta"),
            show="headings",
        )
        self.files_tree.heading("name", text="File Name")
        self.files_tree.heading("size", text="Size (bytes)")
        self.files_tree.heading("video", text="Video / ID")
        self.files_tree.heading("meta", text="Metadata")
        self.files_tree.pack(fill="both", expand=True, padx=4, pady=4)

        self.refresh_files()

    def refresh_files(self) -> None:
        for item in self.files_tree.get_children():
            self.files_tree.delete(item)
        for entry in self.engine.db.list_files():
            meta = entry.get("metadata", {})
            self.files_tree.insert(
                "",
                "end",
                values=(
                    entry.get("file_name", ""),
                    entry.get("file_size", 0),
                    entry.get("video_id", "") or meta.get("video_path", ""),
                    f"owner={meta.get('owner_id', '')}, parts={meta.get('part', '')}/{meta.get('total_parts', '')}",
                ),
            )

    # --------------------------------------------------------------- Encode
    def _build_encode_tab(self) -> None:
        frame = self.encode_frame

        path_row = ttk.Frame(frame)
        path_row.pack(fill="x", pady=8, padx=8)

        ttk.Label(path_row, text="Input file:").pack(side="left")
        self.encode_path_var = tk.StringVar()
        ttk.Entry(path_row, textvariable=self.encode_path_var, width=60).pack(
            side="left", padx=4
        )
        ttk.Button(path_row, text="Browse...", command=self._choose_encode_file).pack(
            side="left"
        )

        options_row = ttk.Frame(frame)
        options_row.pack(fill="x", pady=4, padx=8)

        self.block_size_var = tk.IntVar(value=2)
        self.ecc_bytes_var = tk.IntVar(value=32)
        self.split_size_var = tk.IntVar(value=0)

        ttk.Label(options_row, text="Block size:").grid(row=0, column=0, sticky="w")
        ttk.Entry(options_row, textvariable=self.block_size_var, width=5).grid(
            row=0, column=1, padx=4, sticky="w"
        )

        ttk.Label(options_row, text="ECC bytes:").grid(row=0, column=2, sticky="w")
        ttk.Entry(options_row, textvariable=self.ecc_bytes_var, width=5).grid(
            row=0, column=3, padx=4, sticky="w"
        )

        ttk.Label(options_row, text="Split size (MB, 0=off):").grid(
            row=1, column=0, sticky="w", pady=4
        )
        ttk.Entry(options_row, textvariable=self.split_size_var, width=8).grid(
            row=1, column=1, padx=4, sticky="w"
        )

        self.encode_status_var = tk.StringVar()
        ttk.Label(frame, textvariable=self.encode_status_var).pack(
            fill="x", padx=8, pady=4
        )

        ttk.Button(frame, text="Encode", command=self._start_encode_thread).pack(
            pady=8
        )

    def _choose_encode_file(self) -> None:
        path = filedialog.askopenfilename()
        if path:
            self.encode_path_var.set(path)

    def _start_encode_thread(self) -> None:
        path = self.encode_path_var.get().strip()
        if not path:
            messagebox.showerror("Error", "Please select a file to encode.")
            return

        try:
            block_size = int(self.block_size_var.get())
            ecc_bytes = int(self.ecc_bytes_var.get())
            split_mb = int(self.split_size_var.get())
        except ValueError:
            messagebox.showerror("Error", "Invalid numeric options.")
            return

        def worker() -> None:
            try:
                self.encode_status_var.set("Encoding...")
                settings = EncodeSettings(
                    block_size=block_size,
                    ecc_bytes=ecc_bytes,
                    split_size_mb=split_mb,
                )
                result = self.engine.encode_file(path, settings=settings)
                parts = ", ".join(Path(p.video_path).name for p in result.parts)
                self.encode_status_var.set(f"Done. Created videos: {parts}")
                self.refresh_files()
            except Exception as exc:
                self.encode_status_var.set("")
                messagebox.showerror("Encode error", str(exc))

        threading.Thread(target=worker, daemon=True).start()

    # --------------------------------------------------------------- Decode
    def _build_decode_tab(self) -> None:
        frame = self.decode_frame

        src_row = ttk.Frame(frame)
        src_row.pack(fill="x", pady=8, padx=8)

        ttk.Label(src_row, text="YouTube URL or local video:").pack(side="left")
        self.decode_src_var = tk.StringVar()
        ttk.Entry(src_row, textvariable=self.decode_src_var, width=60).pack(
            side="left", padx=4
        )
        ttk.Button(src_row, text="Browse...", command=self._choose_decode_video).pack(
            side="left"
        )

        pwd_row = ttk.Frame(frame)
        pwd_row.pack(fill="x", pady=4, padx=8)
        ttk.Label(pwd_row, text="Password (optional):").pack(side="left")
        self.decode_pwd_var = tk.StringVar()
        ttk.Entry(pwd_row, textvariable=self.decode_pwd_var, width=30, show="*").pack(
            side="left", padx=4
        )

        self.decode_status_var = tk.StringVar()
        ttk.Label(frame, textvariable=self.decode_status_var).pack(
            fill="x", padx=8, pady=4
        )

        ttk.Button(frame, text="Restore", command=self._start_decode_thread).pack(
            pady=8
        )

    def _choose_decode_video(self) -> None:
        path = filedialog.askopenfilename(
            filetypes=[("Video files", "*.mp4;*.mkv;*.webm"), ("All files", "*.*")]
        )
        if path:
            self.decode_src_var.set(path)

    def _start_decode_thread(self) -> None:
        src = self.decode_src_var.get().strip()
        password = self.decode_pwd_var.get() or None
        if not src:
            messagebox.showerror("Error", "Please enter a URL or choose a file.")
            return

        def worker() -> None:
            try:
                self.decode_status_var.set("Restoring...")
                settings = DecodeSettings(password=password)
                if os.path.exists(src):
                    # Local video path: user must have extracted frames separately,
                    # so for now we treat this as a YouTube-like flow by requiring
                    # the user to supply a YouTube URL, or extend engine later.
                    messagebox.showerror(
                        "Not implemented",
                        "Direct restore from local videos is not yet wired. "
                        "Use YouTube URLs or frames + Decoder for now.",
                    )
                    self.decode_status_var.set("")
                    return

                result = self.engine.recover_any(src, settings=settings)
                self.decode_status_var.set(f"Restored to: {result.output_path}")
                self.refresh_files()
            except Exception as exc:
                self.decode_status_var.set("")
                messagebox.showerror("Restore error", str(exc))

        threading.Thread(target=worker, daemon=True).start()

    # --------------------------------------------------------------- Tools
    def _build_tools_tab(self) -> None:
        frame = self.tools_frame
        ttk.Label(
            frame,
            text=(
                "Tools like video integrity verification and manual auto-join\n"
                "can be added here. The core engine already exposes helpers\n"
                "for playlist-based auto-join via recover_any()."
            ),
            justify="left",
        ).pack(padx=8, pady=8, anchor="w")

    # -------------------------------------------------------------- Settings
    def _build_settings_tab(self) -> None:
        frame = self.settings_frame

        ttk.Label(frame, text="Basic settings (per session):").pack(
            anchor="w", padx=8, pady=4
        )
        ttk.Label(
            frame,
            text="Most low-level tuning is managed via settings.json and environment variables.",
            wraplength=720,
            justify="left",
        ).pack(anchor="w", padx=8, pady=4)


def main() -> None:
    app = YotuDriveGUI()
    app.mainloop()


if __name__ == "__main__":
    main()

