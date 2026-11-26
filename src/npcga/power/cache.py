"""Exact-request cache: Parquet files + a small SQLite index.

v0.1 caches whole requests only (same point, parameters, period, temporal, community).
Filling just the missing part of a period is planned for a later version.
"""
from __future__ import annotations

import contextlib
import hashlib
import json
import sqlite3
from pathlib import Path

import pandas as pd

from .. import config
from .client import PowerResult


def make_key(latitude, longitude, parameters, start, end, temporal, community) -> str:
    raw = json.dumps(
        [round(float(latitude), 4), round(float(longitude), 4), sorted(parameters),
         str(start), str(end), temporal, community],
        sort_keys=True,
    )
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


class PowerCache:
    def __init__(self, root: Path | str | None = None):
        self.root = Path(root) if root else config.cache_dir()
        self.root.mkdir(parents=True, exist_ok=True)
        self._db = self.root / "index.sqlite"
        with contextlib.closing(sqlite3.connect(self._db)) as con, con:
            con.execute("CREATE TABLE IF NOT EXISTS entries (key TEXT PRIMARY KEY, meta TEXT)")

    def _paths(self, key: str):
        return self.root / f"{key}.parquet", self.root / f"{key}.annual.parquet"

    def get(self, key: str) -> PowerResult | None:
        with contextlib.closing(sqlite3.connect(self._db)) as con:
            row = con.execute("SELECT meta FROM entries WHERE key=?", (key,)).fetchone()
        if not row:
            return None
        data_p, annual_p = self._paths(key)
        if not (data_p.exists() and annual_p.exists()):
            self.delete(key)
            return None
        meta = json.loads(row[0])
        return PowerResult(
            data=pd.read_parquet(data_p), annual=pd.read_parquet(annual_p),
            units=meta["units"], nodata_counts=meta["nodata_counts"],
            latitude=meta["latitude"], longitude=meta["longitude"], elevation=meta["elevation"],
            temporal=meta["temporal"], community=meta["community"],
            fetched_at=meta["fetched_at"], from_cache=True,
        )

    def put(self, key: str, result: PowerResult) -> None:
        data_p, annual_p = self._paths(key)
        result.data.to_parquet(data_p, index=False)
        result.annual.to_parquet(annual_p, index=False)
        meta = {
            "units": result.units, "nodata_counts": result.nodata_counts,
            "latitude": result.latitude, "longitude": result.longitude,
            "elevation": result.elevation, "temporal": result.temporal,
            "community": result.community, "fetched_at": result.fetched_at,
        }
        with contextlib.closing(sqlite3.connect(self._db)) as con, con:
            con.execute("INSERT OR REPLACE INTO entries (key, meta) VALUES (?, ?)",
                        (key, json.dumps(meta)))

    def delete(self, key: str) -> None:
        for p in self._paths(key):
            p.unlink(missing_ok=True)
        with contextlib.closing(sqlite3.connect(self._db)) as con, con:
            con.execute("DELETE FROM entries WHERE key=?", (key,))

    def clear(self) -> None:
        with contextlib.closing(sqlite3.connect(self._db)) as con:
            keys = [r[0] for r in con.execute("SELECT key FROM entries")]
        for k in keys:
            self.delete(k)
