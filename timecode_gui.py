#!/usr/bin/env python3
# /// script
# requires-python = ">=3.14"
# dependencies = [
#     "numpy",
# ]
# ///
"""Minimal cross-platform GUI for LTC→SMPTE injection.

Features:
- Drag & drop a video file (if tkinterdnd2 available) OR use "Select File" button.
- Automatically generates output filename with _tc suffix (e.g. clip.mp4 -> clip_tc.mp4).
- Displays log/progress messages.
- Runs processing in a background thread to keep UI responsive.

Dependencies: only standard library + numpy (already used by backend). Optional: tkinterdnd2.

Usage:
    python timecode_gui.py

On macOS you may need: `pip install tkinterdnd2` for native drag & drop.
If tkinterdnd2 is not installed, drag & drop is disabled but selection button works.
"""
from __future__ import annotations
import threading
import queue
import sys
from pathlib import Path
from ltc_to_smpte import process_video  # type: ignore

try:
    import tkinter as tk
    from tkinter import ttk, filedialog, messagebox
except Exception:  # pragma: no cover
    print("Tkinter is required to run the GUI.", file=sys.stderr)
    raise

# Optional drag & drop support
_DND_AVAILABLE = False
try:  # pragma: no cover - optional dependency
    from tkinterdnd2 import DND_FILES, TkinterDnD  # type: ignore
    _DND_AVAILABLE = True
except Exception:  # pragma: no cover
    # Provide simple fallbacks so name references exist (type hints only)
    class _Dummy:  # noqa: D401
        """Fallback dummy for drag & drop when tkinterdnd2 missing."""
        pass
    DND_FILES = "DND_FALLBACK"  # type: ignore
    TkinterDnD = _Dummy  # type: ignore
    _DND_AVAILABLE = False


class TimecodeGUI:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("LTC → SMPTE Timecode")
        self.root.geometry("580x360")
        self.root.minsize(520, 320)

        self.log_queue: queue.Queue[str] = queue.Queue()
        self.processing_thread: threading.Thread | None = None
        self.current_input: Path | None = None

        self._build_ui()
        self._poll_log_queue()

    def _build_ui(self):
        style = ttk.Style()
        if sys.platform == "darwin":  # macOS nicer defaults
            style.configure("TButton", padding=6)

        wrapper = ttk.Frame(self.root, padding=12)
        wrapper.pack(fill="both", expand=True)

        title = ttk.Label(wrapper, text="Drag & Drop Video or Select File", font=("Helvetica", 14, "bold"))
        title.pack(pady=(0, 8))

        drop_style = {
            "relief": "ridge",
            "borderwidth": 2,
            "padding": 12
        }
        self.drop_area = ttk.Frame(wrapper, **drop_style)
        self.drop_area.pack(fill="x")

        self.drop_label = ttk.Label(self.drop_area, text=("Drop file here" if _DND_AVAILABLE else "Drag & drop unavailable (install tkinterdnd2)"))
        self.drop_label.pack(pady=8)

        btn_bar = ttk.Frame(wrapper)
        btn_bar.pack(fill="x", pady=10)

        self.select_btn = ttk.Button(btn_bar, text="Select File…", command=self._select_file)
        self.select_btn.pack(side="left")

        self.process_btn = ttk.Button(btn_bar, text="Process", command=self._start_processing, state="disabled")
        self.process_btn.pack(side="left", padx=(10,0))

        self.open_dir_btn = ttk.Button(btn_bar, text="Show in Finder" if sys.platform == "darwin" else "Open Folder", command=self._open_output_folder, state="disabled")
        self.open_dir_btn.pack(side="right")

        self.status_var = tk.StringVar(value="Idle")
        status = ttk.Label(wrapper, textvariable=self.status_var, foreground="#333")
        status.pack(anchor="w", pady=(0,4))

        self.log = tk.Text(wrapper, height=10, wrap="word", state="disabled")
        self.log.pack(fill="both", expand=True)

        self.progress = ttk.Progressbar(wrapper, mode="indeterminate")
        self.progress.pack(fill="x", pady=(8,0))

        if _DND_AVAILABLE:
            # Guard attribute presence (linters may not know custom methods)
            if hasattr(self.root, 'drop_target_register'):
                try:
                    self.root.drop_target_register(DND_FILES)  # type: ignore[attr-defined]
                except Exception:
                    pass
            if hasattr(self.root, 'dnd_bind'):
                try:
                    self.root.dnd_bind('<<Drop>>', self._on_drop_event)  # type: ignore[attr-defined]
                except Exception:
                    pass
            if hasattr(self.drop_area, 'drop_target_register'):
                try:
                    self.drop_area.drop_target_register(DND_FILES)  # type: ignore[attr-defined]
                except Exception:
                    pass
            if hasattr(self.drop_area, 'dnd_bind'):
                try:
                    self.drop_area.dnd_bind('<<Drop>>', self._on_drop_event)  # type: ignore[attr-defined]
                except Exception:
                    pass

    def _append_log(self, text: str):
        self.log.configure(state="normal")
        self.log.insert("end", text + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def _queue_log(self, text: str):
        self.log_queue.put(text)

    def _poll_log_queue(self):
        while True:
            try:
                msg = self.log_queue.get_nowait()
            except queue.Empty:
                break
            else:
                self._append_log(msg)
        self.root.after(150, self._poll_log_queue)

    def _set_input(self, path: Path):
        self.current_input = path
        self.drop_label.configure(text=f"Selected: {path.name}")
        self.process_btn.configure(state="normal")
        self.status_var.set("Ready to process")

    def _select_file(self):
        filetypes = [
            ("Video Files", "*.mp4 *.mov *.mxf *.mkv *.avi"),
            ("All Files", "*.*")
        ]
        filename = filedialog.askopenfilename(title="Select video file", filetypes=filetypes)
        if filename:
            self._set_input(Path(filename))

    def _on_drop_event(self, event):  # pragma: no cover - GUI event
        # event.data may contain space-delimited list; only take first for simplicity
        dropped = event.data.strip().strip('{}')  # On Windows braces sometimes
        if ' ' in dropped and not Path(dropped).exists():
            # Likely list of files, take first token
            dropped = dropped.split()[0]
        p = Path(dropped)
        if p.exists():
            self._set_input(p)
        else:
            messagebox.showerror("Invalid file", f"File does not exist: {p}")

    def _start_processing(self):
        if not self.current_input:
            return
        if self.processing_thread and self.processing_thread.is_alive():
            messagebox.showinfo("Busy", "Already processing a file.")
            return
        self.status_var.set("Processing…")
        self.progress.start(10)
        self.process_btn.configure(state="disabled")
        self.open_dir_btn.configure(state="disabled")
        self._queue_log(f"Starting processing: {self.current_input}")
        self.processing_thread = threading.Thread(target=self._process_worker, daemon=True)
        self.processing_thread.start()

    def _process_worker(self):
        assert self.current_input is not None
        input_path = str(self.current_input)
        # Stream object to capture stdout/stderr and forward lines into GUI queue
        class QueueStream:
            def __init__(self, q: queue.Queue[str], tag: str):
                self.q = q
                self.tag = tag
                self._buffer = ""
            def write(self, data: str):  # pragma: no cover - simple passthrough
                if not data:
                    return
                self._buffer += data
                while '\n' in self._buffer:
                    line, self._buffer = self._buffer.split('\n', 1)
                    line = line.rstrip('\r')
                    if line.strip():
                        self.q.put(f"{self.tag} {line}")
            def flush(self):  # pragma: no cover - not used
                pass

        orig_stdout, orig_stderr = sys.stdout, sys.stderr
        sys.stdout = QueueStream(self.log_queue, "[stdout]")  # type: ignore
        sys.stderr = QueueStream(self.log_queue, "[stderr]")  # type: ignore
        self._queue_log("--- Backend log capture started ---")
        try:
            success = process_video(input_path)
        except Exception as e:  # pragma: no cover
            success = False
            # Ensure exception text visible
            self._queue_log(f"[exception] {e}")
        finally:
            # Flush any remainder
            try:
                sys.stdout.flush()
                sys.stderr.flush()
            except Exception:
                pass
            sys.stdout, sys.stderr = orig_stdout, orig_stderr
            self._queue_log("--- Backend log capture finished ---")

        if success:
            out_path = Path(input_path).with_name(Path(input_path).stem + '_tc' + Path(input_path).suffix)
            self._queue_log(f"✓ Done: {out_path}")
            self.root.after(0, lambda: self._on_done(True, out_path))
        else:
            self._queue_log("✗ Failed")
            self.root.after(0, lambda: self._on_done(False, None))

    def _on_done(self, success: bool, out_path: Path | None):
        self.progress.stop()
        self.status_var.set("Completed" if success else "Failed")
        self.process_btn.configure(state="normal")
        if success and out_path:
            self.last_output = out_path
            self.open_dir_btn.configure(state="normal")
        else:
            self.open_dir_btn.configure(state="disabled")

    def _open_output_folder(self):  # pragma: no cover - platform interaction
        out = getattr(self, 'last_output', None)
        if not out:
            return
        try:
            if sys.platform == 'darwin':
                import subprocess
                subprocess.run(['open', '--', str(out.parent)])
            elif sys.platform.startswith('win'):
                import subprocess
                subprocess.run(['explorer', str(out.parent)])
            else:  # linux
                import subprocess
                subprocess.run(['xdg-open', str(out.parent)])
        except Exception as e:
            messagebox.showerror("Open Folder", f"Could not open folder: {e}")


def run():  # pragma: no cover - entry point
    if _DND_AVAILABLE and hasattr(TkinterDnD, 'Tk'):
        try:
            root = TkinterDnD.Tk()  # type: ignore[attr-defined]
        except Exception:
            root = tk.Tk()
    else:
        root = tk.Tk()
    TimecodeGUI(root)
    root.mainloop()


if __name__ == '__main__':  # pragma: no cover
    run()
