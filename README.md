# Sheet Music to MIDI

Convert scanned or photographed sheet music into playable MIDI files. Supports images, multi-page PDFs, clipboard pastes, and MusicXML files.

---

## How it works

The pipeline has up to four stages depending on the input:

```
PDF input   →  pdf2image (poppler)  →  PNG pages  ┐
Image input                                        ├→  oemer (OMR)  →  MusicXML  →  music21  →  .mid
Clipboard   →  saved as temp PNG   ────────────────┘

MusicXML input  ──────────────────────────────────────────────────────────────────→  music21  →  .mid
```

1. **PDF rendering** — PDFs are rasterized page-by-page at a configurable DPI using `pdf2image` (backed by poppler).
2. **Optical Music Recognition (OMR)** — each image is passed through `oemer`, a deep-learning OMR engine that detects staves, noteheads, accidentals, rhythms, and other notation symbols and produces a MusicXML file.
3. **Multi-page merge** — if the input was a multi-page PDF, the per-page MusicXML outputs are merged into a single score using `music21`.
4. **MIDI export** — `music21` parses the final MusicXML and writes a standard `.mid` file.

MusicXML inputs skip stages 1–3 entirely and go straight to MIDI export.

---

## Requirements

- **Windows 10/11**
- **Python 3.12+**
- **poppler** (for PDF support) — installed to `C:\poppler`

### Python packages

| Package | Purpose |
|---|---|
| `oemer` | Optical Music Recognition |
| `music21` | MusicXML parsing and MIDI export |
| `pdf2image` | PDF-to-image rendering |
| `Pillow` | Image handling and clipboard support |
| `opencv-python-headless` | Image preprocessing (oemer dependency) |
| `onnxruntime-gpu` | Neural network inference (oemer dependency) |

Install all at once:

```bash
pip install oemer music21 pdf2image Pillow
```

---

## Installation

1. Install Python 3.12 or later from [python.org](https://python.org). Check **"Add Python to PATH"** during setup.
2. Install poppler via winget:
   ```
   winget install oschwartz10612.poppler
   ```
3. Install Python dependencies:
   ```
   pip install oemer music21 pdf2image Pillow
   ```
4. Place `sheet_to_midi.py` and `sheet_to_midi_gui.pyw` in the same folder.

---

## Usage

### GUI (recommended)

Double-click `sheet_to_midi_gui.pyw`. No console window appears.

**Input section**
- **Browse** — open a file picker to select an image, PDF, or MusicXML file.
- **Paste** — grab an image directly from the clipboard (e.g. a screenshot or a scan copied from another app). The image is automatically saved to a temporary file and used as the input.

**Output section**
- **Browse** — choose where to save the `.mid` file. Defaults to the same folder and name as the input.

**Options**
- **PDF render DPI** — slider from 150 to 600. Higher DPI improves OMR accuracy on dense or small-print scores at the cost of speed. 300 is a good default; try 400 for complex scores.
- **Keep intermediate MusicXML** — saves the MusicXML produced by the OMR step alongside the final MIDI file. Useful for inspection or editing in notation software like MuseScore.

**Convert** — starts the pipeline in a background thread. The progress bar animates while work is in progress and a log panel streams output in real time. A dialog confirms success or failure when the run completes.

---

### Command line

```bash
python sheet_to_midi.py <input> [output.mid] [--dpi N] [--keep-xml]
```

**Arguments**

| Argument | Description |
|---|---|
| `input` | Path to an image (PNG/JPG/BMP/TIFF), PDF, or MusicXML file |
| `output` | Output `.mid` path. Defaults to `<input>.mid` in the same directory |
| `--dpi N` | DPI for PDF rendering (default: 300) |
| `--keep-xml` | Save the intermediate MusicXML file alongside the MIDI |

**Examples**

```bash
# Image input, output saved next to the image
python sheet_to_midi.py scan.png

# PDF input with explicit output path
python sheet_to_midi.py score.pdf output.mid

# PDF with higher DPI and keep the MusicXML
python sheet_to_midi.py score.pdf song.mid --dpi 400 --keep-xml

# MusicXML input — skips OMR entirely
python sheet_to_midi.py score.musicxml output.mid
```

---

## Supported input formats

| Format | Extension(s) | Notes |
|---|---|---|
| PNG image | `.png` | Best quality for OMR |
| JPEG image | `.jpg`, `.jpeg` | Compression artifacts may reduce accuracy |
| BMP image | `.bmp` | |
| TIFF image | `.tif`, `.tiff` | |
| PDF | `.pdf` | Multi-page supported; each page processed independently |
| MusicXML | `.xml`, `.musicxml`, `.mxl` | Skips OMR — direct MIDI conversion |
| Clipboard | — | GUI only; paste any copied image |

---

## Tips for best results

- **Use clean, high-contrast scans.** OMR accuracy degrades significantly with shadows, skew, coffee stains, or low resolution. Aim for 300 DPI or above.
- **Typeset music works best.** `oemer` was trained on printed/engraved notation. Handwritten scores will produce poor results.
- **Increase DPI for dense scores.** If a score has small noteheads, many ledger lines, or complex rhythms, try `--dpi 400`.
- **Check the MusicXML if MIDI sounds wrong.** Use `--keep-xml` and open the `.musicxml` in [MuseScore](https://musescore.org) to see exactly what the OMR detected and correct any errors before re-exporting to MIDI.
- **Multi-page PDFs are merged automatically.** Each page is processed independently and the results are stitched together in order. Very long scores may take several minutes.

---

## Project structure

```
SheetToMidi/
├── sheet_to_midi.py       # Core pipeline (PDF rendering, OMR, MIDI export)
├── sheet_to_midi_gui.pyw  # Tkinter GUI front-end (no console window)
└── README.md
```

---

## Limitations

- Handwritten or non-standard notation is not supported.
- Guitar tabs, chord diagrams, and lead sheets with chord symbols are not reliably recognized.
- Lyrics and text annotations are not carried through to MIDI.
- Very complex orchestral scores with many simultaneous parts may produce reduced accuracy.
- GPU acceleration is used automatically if a CUDA-compatible GPU is present; CPU inference is slower but fully supported.
