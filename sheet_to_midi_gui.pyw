#!/usr/bin/env python3
"""
sheet_to_midi_gui.py — GUI front-end for sheet_to_midi.py
"""

import sys
import tempfile
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, ttk
from pathlib import Path


# Ensure the script directory is on the path so sheet_to_midi imports cleanly
sys.path.insert(0, str(Path(__file__).parent))


# ---------------------------------------------------------------------------
# Worker thread
# ---------------------------------------------------------------------------

def run_conversion(input_path, output_path, dpi, keep_xml, log_fn, done_fn):
    """Runs the conversion pipeline in a background thread."""
    import io
    import contextlib

    # Redirect sheet_to_midi's print output to the GUI log
    class LogWriter(io.TextIOBase):
        def write(self, s):
            if s.strip():
                log_fn(s.rstrip())
            return len(s)

    writer = LogWriter()
    try:
        import sheet_to_midi as s2m
        # Monkey-patch log() to route through GUI
        original_log = s2m.log
        s2m.log = lambda msg: log_fn(f"[sheet_to_midi] {msg}")
        try:
            s2m.process(
                input_path=Path(input_path),
                output_path=Path(output_path),
                dpi=dpi,
                keep_xml=keep_xml,
            )
            done_fn(success=True)
        finally:
            s2m.log = original_log
    except SystemExit as e:
        log_fn(f"[error] {e}")
        done_fn(success=False)
    except Exception as e:
        log_fn(f"[error] {type(e).__name__}: {e}")
        done_fn(success=False)


# ---------------------------------------------------------------------------
# GUI
# ---------------------------------------------------------------------------

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Sheet Music → MIDI")
        self.resizable(True, True)
        self.minsize(580, 520)
        self._build_ui()
        self._center()

    def _center(self):
        self.update_idletasks()
        w, h = 640, 580
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        self.geometry(f"{w}x{h}+{(sw-w)//2}+{(sh-h)//2}")

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self):
        pad = dict(padx=12, pady=6)

        # ── Input file ──────────────────────────────────────────────
        frm_in = ttk.LabelFrame(self, text="Input (image / PDF / MusicXML)")
        frm_in.pack(fill="x", **pad)

        self._input_var = tk.StringVar()
        ttk.Entry(frm_in, textvariable=self._input_var, width=60).pack(
            side="left", fill="x", expand=True, padx=(8, 4), pady=8
        )
        ttk.Button(frm_in, text="Browse…", command=self._browse_input).pack(
            side="left", padx=(0, 4), pady=8
        )
        ttk.Button(frm_in, text="Paste", command=self._paste_clipboard).pack(
            side="left", padx=(0, 8), pady=8
        )

        # ── Output file ─────────────────────────────────────────────
        frm_out = ttk.LabelFrame(self, text="Output MIDI")
        frm_out.pack(fill="x", **pad)

        self._output_var = tk.StringVar()
        ttk.Entry(frm_out, textvariable=self._output_var, width=60).pack(
            side="left", fill="x", expand=True, padx=(8, 4), pady=8
        )
        ttk.Button(frm_out, text="Browse…", command=self._browse_output).pack(
            side="left", padx=(0, 8), pady=8
        )

        # ── Options ─────────────────────────────────────────────────
        frm_opts = ttk.LabelFrame(self, text="Options")
        frm_opts.pack(fill="x", **pad)

        # DPI row
        dpi_row = ttk.Frame(frm_opts)
        dpi_row.pack(fill="x", padx=8, pady=(8, 4))
        ttk.Label(dpi_row, text="PDF render DPI:").pack(side="left")
        self._dpi_var = tk.IntVar(value=300)
        self._dpi_label = ttk.Label(dpi_row, text="300", width=4)
        self._dpi_label.pack(side="right")
        dpi_scale = ttk.Scale(
            dpi_row, from_=150, to=600, orient="horizontal",
            variable=self._dpi_var, command=self._on_dpi_change
        )
        dpi_scale.pack(side="left", fill="x", expand=True, padx=8)

        # Checkboxes row
        chk_row = ttk.Frame(frm_opts)
        chk_row.pack(fill="x", padx=8, pady=(4, 8))
        self._keep_xml_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            chk_row, text="Keep intermediate MusicXML file",
            variable=self._keep_xml_var
        ).pack(side="left")

        # ── Convert button ──────────────────────────────────────────
        self._convert_btn = ttk.Button(
            self, text="Convert", command=self._start_conversion
        )
        self._convert_btn.pack(pady=(4, 0))

        # ── Progress bar ────────────────────────────────────────────
        self._progress = ttk.Progressbar(self, mode="indeterminate")
        self._progress.pack(fill="x", padx=12, pady=(4, 0))

        # ── Log output ──────────────────────────────────────────────
        frm_log = ttk.LabelFrame(self, text="Log")
        frm_log.pack(fill="both", expand=True, **pad)

        self._log = scrolledtext.ScrolledText(
            frm_log, state="disabled", height=12,
            font=("Consolas", 9), wrap="word"
        )
        self._log.pack(fill="both", expand=True, padx=4, pady=4)

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    def _on_dpi_change(self, value):
        self._dpi_label.config(text=str(int(float(value))))

    def _browse_input(self):
        path = filedialog.askopenfilename(
            title="Select sheet music file",
            filetypes=[
                ("All supported", "*.png *.jpg *.jpeg *.bmp *.tif *.tiff *.pdf *.xml *.musicxml *.mxl"),
                ("Images", "*.png *.jpg *.jpeg *.bmp *.tif *.tiff"),
                ("PDF", "*.pdf"),
                ("MusicXML", "*.xml *.musicxml *.mxl"),
                ("All files", "*.*"),
            ],
        )
        if path:
            self._input_var.set(path)
            # Auto-fill output if blank
            if not self._output_var.get():
                self._output_var.set(str(Path(path).with_suffix(".mid")))

    def _paste_clipboard(self):
        try:
            from PIL import ImageGrab
            img = ImageGrab.grabclipboard()
        except Exception as e:
            messagebox.showerror("Clipboard error", str(e))
            return

        if img is None:
            messagebox.showwarning(
                "Nothing to paste",
                "No image found on the clipboard.\n"
                "Copy an image (e.g. screenshot or scan) first, then click Paste."
            )
            return

        # Save to a temp PNG so the pipeline can read it as a normal file
        tmp = Path(tempfile.mktemp(prefix="s2m_paste_", suffix=".png"))
        img.save(str(tmp), "PNG")
        self._input_var.set(str(tmp))
        if not self._output_var.get():
            self._output_var.set(str(Path.home() / "output.mid"))
        self._append_log(f"Clipboard image saved to: {tmp}")

    def _browse_output(self):
        initial = self._output_var.get() or str(
            Path(self._input_var.get()).with_suffix(".mid")
            if self._input_var.get() else Path.home() / "output.mid"
        )
        path = filedialog.asksaveasfilename(
            title="Save MIDI as…",
            initialfile=Path(initial).name,
            initialdir=str(Path(initial).parent),
            defaultextension=".mid",
            filetypes=[("MIDI files", "*.mid *.midi"), ("All files", "*.*")],
        )
        if path:
            self._output_var.set(path)

    def _start_conversion(self):
        input_path = self._input_var.get().strip()
        output_path = self._output_var.get().strip()

        if not input_path:
            messagebox.showerror("Missing input", "Please select an input file.")
            return
        if not Path(input_path).exists():
            messagebox.showerror("File not found", f"Cannot find:\n{input_path}")
            return
        if not output_path:
            messagebox.showerror("Missing output", "Please specify an output MIDI path.")
            return

        self._log_clear()
        self._set_busy(True)

        threading.Thread(
            target=run_conversion,
            args=(
                input_path,
                output_path,
                self._dpi_var.get(),
                self._keep_xml_var.get(),
                self._append_log,
                self._on_done,
            ),
            daemon=True,
        ).start()

    # ------------------------------------------------------------------
    # Thread-safe UI helpers
    # ------------------------------------------------------------------

    def _append_log(self, msg: str):
        self.after(0, self._append_log_main, msg)

    def _append_log_main(self, msg: str):
        self._log.config(state="normal")
        self._log.insert("end", msg + "\n")
        self._log.see("end")
        self._log.config(state="disabled")

    def _log_clear(self):
        self._log.config(state="normal")
        self._log.delete("1.0", "end")
        self._log.config(state="disabled")

    def _set_busy(self, busy: bool):
        self.after(0, self._set_busy_main, busy)

    def _set_busy_main(self, busy: bool):
        if busy:
            self._convert_btn.config(state="disabled")
            self._progress.start(12)
        else:
            self._convert_btn.config(state="normal")
            self._progress.stop()
            self._progress["value"] = 0

    def _on_done(self, success: bool):
        self._set_busy(False)
        if success:
            out = self._output_var.get()
            self._append_log(f"\n✓ Conversion complete → {out}")
            self.after(0, lambda: messagebox.showinfo(
                "Done", f"MIDI saved to:\n{out}"
            ))
        else:
            self._append_log("\n✗ Conversion failed — see log above.")
            self.after(0, lambda: messagebox.showerror(
                "Error", "Conversion failed. Check the log for details."
            ))


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    app = App()
    app.mainloop()
