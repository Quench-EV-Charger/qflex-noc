"""Export the qflex-charging project, keeping only .py, .json, .js, and .html files.

Produces two outputs in the parent directory of the project:
  1. A folder:  <module>_opentest/                       (raw filtered tree)
  2. A zip:     <module>_dtd_DDMMYY_HHMMSS.zip           (timestamped archive)

Where <module> is the project root folder name (e.g. "qflex-charging").

Usage:
    python scripts/zip_source.py                       # builds folder + zip
    python scripts/zip_source.py --dry-run             # list what would be exported
    python scripts/zip_source.py --include-ext .py .json .js .html .yaml
    python scripts/zip_source.py --out-dir D:\\releases # write outputs elsewhere
    python scripts/zip_source.py --skip-folder         # only build the zip
    python scripts/zip_source.py --skip-zip            # only build the folder
"""

from __future__ import annotations

import argparse
import os
import shutil
import sys
import zipfile
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
MODULE_NAME = PROJECT_ROOT.name  # "qflex-charging"

DEFAULT_INCLUDE_EXTS = {".py", ".json", ".js", ".html", ".css"}

EXCLUDED_DIR_NAMES = {
    "__pycache__",
    ".git",
    ".venv",
    "venv",
    "env",
    "node_modules",
    "build",
    "dist",
    ".eggs",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".tox",
    ".idea",
    ".vscode",
    ".serena",
    "graphify-out",
    "simulator",
    "test_dashboard",
    "tests",
    "docs",
    "doc",
    "scripts",
}

EXCLUDED_FILE_NAMES = {
    ".mcp.json",
    "pyrightconfig.json",
}


def iter_matching_files(root: Path, include_exts: set[str]):
    """Yield files under ``root`` whose suffix is in ``include_exts``.

    Skips any directory in EXCLUDED_DIR_NAMES plus hidden dirs starting with '.',
    and any file whose basename is in EXCLUDED_FILE_NAMES.
    """
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [
            d for d in dirnames
            if d not in EXCLUDED_DIR_NAMES and not d.startswith(".")
        ]
        for name in filenames:
            if name in EXCLUDED_FILE_NAMES:
                continue
            ext = os.path.splitext(name)[1].lower()
            if ext in include_exts:
                yield Path(dirpath) / name


def copy_to_folder(files: list[Path], folder_root: Path) -> int:
    """Copy each file under ``folder_root`` preserving its path relative to PROJECT_ROOT.

    If ``folder_root`` already exists, it is removed first so the export is clean.
    Returns total bytes written.
    """
    if folder_root.exists():
        shutil.rmtree(folder_root)
    folder_root.mkdir(parents=True)

    total_bytes = 0
    for src in files:
        rel = src.relative_to(PROJECT_ROOT)
        dst = folder_root / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        total_bytes += src.stat().st_size
    return total_bytes


def write_zip(files: list[Path], zip_path: Path, arc_root: str) -> int:
    """Write ``files`` to ``zip_path`` under a top-level directory ``arc_root``.

    Returns total uncompressed bytes added.
    """
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    total_bytes = 0
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for src in files:
            rel = src.relative_to(PROJECT_ROOT)
            arcname = f"{arc_root}/{rel.as_posix()}"
            zf.write(src, arcname)
            total_bytes += src.stat().st_size
    return total_bytes


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=("Export qflex-charging as a folder (_opentest) and a "
                     "timestamped zip (_dtd_DDMMYY_HHMMSS).")
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=PROJECT_ROOT.parent,
        help="Directory to place the folder and zip into (default: project's parent dir)",
    )
    parser.add_argument(
        "--include-ext",
        nargs="+",
        default=sorted(DEFAULT_INCLUDE_EXTS),
        help="File extensions to include, with leading dot (default: .py .json .js .html)",
    )
    parser.add_argument(
        "--skip-folder",
        action="store_true",
        help="Skip producing the _opentest folder",
    )
    parser.add_argument(
        "--skip-zip",
        action="store_true",
        help="Skip producing the timestamped zip",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="List files that would be exported without writing anything",
    )
    args = parser.parse_args(argv)

    include_exts = {e.lower() if e.startswith(".") else f".{e.lower()}"
                    for e in args.include_ext}

    files = sorted(iter_matching_files(PROJECT_ROOT, include_exts))
    raw_bytes = sum(f.stat().st_size for f in files)

    folder_name = f"{MODULE_NAME}_opentest"
    timestamp = datetime.now().strftime("%d%m%y_%H%M%S")
    zip_name = f"{MODULE_NAME}_dtd_{timestamp}.zip"

    folder_path = args.out_dir / folder_name
    zip_path = args.out_dir / zip_name

    if args.dry_run:
        for f in files:
            rel = f.relative_to(PROJECT_ROOT)
            print(f"{f.stat().st_size:>10}  {folder_name}/{rel.as_posix()}")
        print(f"\n[dry-run] {len(files)} files, {raw_bytes:,} bytes")
        if not args.skip_folder:
            print(f"  would write folder: {folder_path}")
        if not args.skip_zip:
            print(f"  would write zip   : {zip_path}")
        return 0

    if not args.skip_folder:
        copied = copy_to_folder(files, folder_path)
        print(f"Wrote folder {folder_path}")
        print(f"  files     : {len(files)}")
        print(f"  raw bytes : {copied:,}")

    if not args.skip_zip:
        written = write_zip(files, zip_path, arc_root=folder_name)
        zip_size = zip_path.stat().st_size
        print(f"Wrote zip    {zip_path}")
        print(f"  files     : {len(files)}")
        print(f"  raw bytes : {written:,}")
        print(f"  zip bytes : {zip_size:,}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
