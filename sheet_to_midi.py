#!/usr/bin/env python3
"""
sheet_to_midi.py — Convert sheet music images/PDFs to MIDI.

Usage:
    python sheet_to_midi.py <input> [output.mid] [options]

Supports: PNG, JPG, BMP, TIFF, PDF
OMR engine: Audiveris 5.10.2
"""

import argparse
import os
import shutil
import sys
import tempfile
from pathlib import Path


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def log(msg: str) -> None:
    print(f"[sheet_to_midi] {msg}", flush=True)


def pdf_to_images(pdf_path: Path, dpi: int = 300) -> list[Path]:
    """Render each PDF page to a PNG in a temp directory."""
    try:
        from pdf2image import convert_from_path
    except ImportError:
        sys.exit("pdf2image is not installed. Run: pip install pdf2image")

    tmp = Path(tempfile.mkdtemp(prefix="s2m_pdf_"))
    log(f"Rendering PDF at {dpi} DPI → {tmp}")
    pages = convert_from_path(str(pdf_path), dpi=dpi)
    paths: list[Path] = []
    for i, page in enumerate(pages):
        out = tmp / f"page_{i+1:03d}.png"
        page.save(str(out), "PNG")
        log(f"  Page {i+1}/{len(pages)} → {out.name}")
        paths.append(out)
    return paths


AUDIVERIS_EXE = Path(r"C:\Program Files\Audiveris\Audiveris.exe")


def run_audiveris(image_path: Path, out_dir: Path) -> Path:
    """Run Audiveris OMR on a single image; return path to produced MXL file."""
    import subprocess
    import zipfile

    if not AUDIVERIS_EXE.exists():
        sys.exit(
            f"Audiveris not found at {AUDIVERIS_EXE}. "
            "Download from https://github.com/Audiveris/audiveris/releases"
        )

    log(f"Running OMR on {image_path.name} …")
    cmd = [
        str(AUDIVERIS_EXE),
        "-batch",
        "-export",
        "-output", str(out_dir),
        "--", str(image_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.stdout.strip():
        for line in result.stdout.strip().splitlines():
            log(f"  {line}")
    if result.returncode != 0:
        sys.exit(f"Audiveris failed (exit {result.returncode}):\n{result.stderr}")

    # Audiveris outputs a .mxl (zipped MusicXML) — extract it
    mxl_files = list(out_dir.rglob("*.mxl"))
    if not mxl_files:
        sys.exit(
            "Audiveris did not produce an MXL file. "
            "Check that the image is a clear scan of printed sheet music."
        )
    mxl_path = mxl_files[0]
    xml_path = mxl_path.with_suffix(".musicxml")
    with zipfile.ZipFile(mxl_path, "r") as z:
        # The MusicXML file inside the zip is typically named container.xml or the score xml
        xml_entries = [n for n in z.namelist() if n.endswith(".xml") and not n.startswith("META")]
        if not xml_entries:
            sys.exit("Could not find MusicXML inside the Audiveris MXL archive.")
        with z.open(xml_entries[0]) as src, open(xml_path, "wb") as dst:
            dst.write(src.read())

    return xml_path


def merge_musicxml(xml_paths: list[Path], merged_path: Path) -> Path:
    """Concatenate multiple MusicXML scores into one using music21 parts."""
    import copy
    import music21 as m21

    if len(xml_paths) == 1:
        return xml_paths[0]

    log(f"Merging {len(xml_paths)} MusicXML files …")
    base = m21.converter.parse(str(xml_paths[0]))
    for xp in xml_paths[1:]:
        extra = m21.converter.parse(str(xp))
        for i, part in enumerate(extra.parts):
            if i < len(base.parts):
                for measure in part.getElementsByClass(m21.stream.Measure):
                    base.parts[i].append(copy.deepcopy(measure))
            else:
                base.append(copy.deepcopy(part))

    base.write("musicxml", fp=str(merged_path))
    return merged_path


def musicxml_to_midi(xml_path: Path, midi_path: Path) -> None:
    """Convert a MusicXML file to MIDI using music21."""
    try:
        import music21 as m21
    except ImportError:
        sys.exit("music21 is not installed. Run: pip install music21")

    log(f"Parsing MusicXML: {xml_path.name}")
    score = m21.converter.parse(str(xml_path))

    log(f"Writing MIDI → {midi_path}")
    score.write("midi", fp=str(midi_path))


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def process(input_path: Path, output_path: Path, dpi: int, keep_xml: bool) -> None:
    suffix = input_path.suffix.lower()
    tmp_dirs: list[Path] = []

    try:
        # --- Step 1: resolve images ---
        if suffix == ".pdf":
            image_paths = pdf_to_images(input_path, dpi=dpi)
            tmp_dirs.append(image_paths[0].parent)
        elif suffix in {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff"}:
            image_paths = [input_path]
        elif suffix in {".xml", ".musicxml", ".mxl"}:
            # Skip OMR entirely — go straight to MIDI
            log("Input is already MusicXML — skipping OMR step.")
            musicxml_to_midi(input_path, output_path)
            log(f"Done. MIDI saved to: {output_path}")
            return
        else:
            sys.exit(f"Unsupported input format: {suffix}")

        # --- Step 2: OMR each image ---
        omr_out = Path(tempfile.mkdtemp(prefix="s2m_omr_"))
        tmp_dirs.append(omr_out)

        xml_paths: list[Path] = []
        for img in image_paths:
            xml_paths.append(run_audiveris(img, omr_out))

        # --- Step 3: merge if multi-page ---
        if len(xml_paths) > 1:
            merged_xml = omr_out / "merged.musicxml"
            final_xml = merge_musicxml(xml_paths, merged_xml)
        else:
            final_xml = xml_paths[0]

        # Optionally preserve the MusicXML beside the MIDI
        if keep_xml:
            kept = output_path.with_suffix(".musicxml")
            shutil.copy(str(final_xml), str(kept))
            log(f"MusicXML saved to: {kept}")

        # --- Step 4: MIDI conversion ---
        musicxml_to_midi(final_xml, output_path)
        log(f"Done. MIDI saved to: {output_path}")

    finally:
        for d in tmp_dirs:
            shutil.rmtree(d, ignore_errors=True)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Convert sheet music (image/PDF) to MIDI.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python sheet_to_midi.py score.pdf
  python sheet_to_midi.py page.png output.mid
  python sheet_to_midi.py score.pdf song.mid --dpi 400 --keep-xml
  python sheet_to_midi.py score.musicxml output.mid
        """,
    )
    parser.add_argument("input", help="Input file: image (PNG/JPG/BMP/TIFF) or PDF or MusicXML")
    parser.add_argument(
        "output",
        nargs="?",
        help="Output MIDI path (default: <input>.mid next to the input file)",
    )
    parser.add_argument(
        "--dpi",
        type=int,
        default=300,
        help="DPI for PDF rendering (default: 300; try 400 for dense scores)",
    )
    parser.add_argument(
        "--keep-xml",
        action="store_true",
        help="Save the intermediate MusicXML file alongside the MIDI",
    )

    args = parser.parse_args()

    input_path = Path(args.input).resolve()
    if not input_path.exists():
        sys.exit(f"Input file not found: {input_path}")

    if args.output:
        output_path = Path(args.output).resolve()
    else:
        output_path = input_path.with_suffix(".mid")

    output_path.parent.mkdir(parents=True, exist_ok=True)

    log(f"Input:  {input_path}")
    log(f"Output: {output_path}")

    process(input_path, output_path, dpi=args.dpi, keep_xml=args.keep_xml)


if __name__ == "__main__":
    main()
