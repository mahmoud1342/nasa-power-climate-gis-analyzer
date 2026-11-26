import io
import zipfile

import pytest

from npcga.io import extract_uploads
from npcga.io import upload as up


def make_zip(entries):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for name, data in entries.items():
            z.writestr(name, data)
    return buf.getvalue()


def test_plain_csv_and_non_csv(tmp_path):
    n = extract_uploads([("a.csv", b"1"), ("notes.txt", b"x"), ("C:\\temp\\b.CSV", b"2")], tmp_path)
    assert n == 2 and sorted(p.name for p in tmp_path.iterdir()) == ["a.csv", "b.CSV"]


def test_zip_slip_and_folders_are_flattened(tmp_path):
    z = make_zip({"../../evil.csv": b"x", "/abs/path/abs.csv": b"y", "folder/sub/ok.csv": b"z", "readme.md": b"n"})
    inner = tmp_path / "target"
    inner.mkdir()
    assert extract_uploads([("data.zip", z)], inner) == 3
    assert sorted(p.name for p in inner.iterdir()) == ["abs.csv", "evil.csv", "ok.csv"]
    assert not (tmp_path / "evil.csv").exists() and not (tmp_path.parent / "evil.csv").exists()


def test_duplicate_names_are_kept_not_overwritten(tmp_path):
    extract_uploads([("a.csv", b"1"), ("a.csv", b"2")], tmp_path)
    assert len(list(tmp_path.iterdir())) == 2


def test_bad_zip_and_limits(tmp_path, monkeypatch):
    with pytest.raises(ValueError, match="invalid ZIP"):
        extract_uploads([("x.zip", b"not a zip")], tmp_path)
    monkeypatch.setattr(up, "MAX_FILES", 2)
    with pytest.raises(ValueError, match="too large"):
        extract_uploads([("a.csv", b"1"), ("b.csv", b"2"), ("c.csv", b"3")], tmp_path)
    monkeypatch.setattr(up, "MAX_FILES", 5000)
    monkeypatch.setattr(up, "MAX_TOTAL_BYTES", 10)
    with pytest.raises(ValueError, match="too large"):
        extract_uploads([("a.csv", b"x" * 11)], tmp_path / "..")
