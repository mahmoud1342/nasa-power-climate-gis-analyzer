"""Safe extraction of uploaded CSV files / ZIP archives into a folder (used by the web page).

Only .csv members are written, always flattened to a plain file name (no sub-folders), so a
malicious ZIP cannot write outside the target ('zip slip'). Size and count limits stop zip bombs.
"""
from __future__ import annotations

import io
import zipfile
from pathlib import Path, PurePosixPath

MAX_FILES = 5000
MAX_TOTAL_BYTES = 500 * 1024 * 1024


def _unique(target: Path, name: str, counter: int) -> Path:
    dest = target / name
    if dest.exists():
        dest = target / f"{Path(name).stem}_{counter}{Path(name).suffix}"
    return dest


def extract_uploads(items: list[tuple[str, bytes]], target: Path) -> int:
    """items = [(file_name, raw_bytes)]. Returns the number of CSV files written.

    Raises ValueError for an invalid ZIP or when limits are exceeded.
    """
    target = Path(target)
    count, total = 0, 0

    def write(name: str, data: bytes) -> None:
        nonlocal count, total
        total += len(data)
        if count + 1 > MAX_FILES or total > MAX_TOTAL_BYTES:
            raise ValueError("upload too large (too many files or too many bytes)")
        _unique(target, name, count).write_bytes(data)
        count += 1

    for raw_name, raw in items:
        name = PurePosixPath(str(raw_name).replace("\\", "/")).name
        if name.lower().endswith(".zip"):
            try:
                with zipfile.ZipFile(io.BytesIO(raw)) as z:
                    for info in z.infolist():
                        member = PurePosixPath(info.filename.replace("\\", "/")).name
                        if info.is_dir() or not member.lower().endswith(".csv"):
                            continue
                        if total + info.file_size > MAX_TOTAL_BYTES:
                            raise ValueError("ZIP content too large")
                        write(member, z.read(info))
            except zipfile.BadZipFile:
                raise ValueError(f"invalid ZIP file: {name}") from None
        elif name.lower().endswith(".csv"):
            write(name, raw)
    return count
