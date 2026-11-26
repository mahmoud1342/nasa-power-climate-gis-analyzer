"""Central configuration. Edit values here, nowhere else."""
from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import quote

APP_NAME = "NASA POWER Climate & GIS Analyzer"
DEVELOPER = "Mahmoud Mohamed Atia"
DEVELOPER_AR = "محمود محمد عطية"
# Copied as supplied by the developer; verify it opens in a browser before release.
LINKEDIN_URL = "https://www.linkedin.com/in/𝐌𝐚𝐡𝐦𝐨𝐮𝐝-𝐌𝐨𝐡𝐚𝐦𝐞𝐝-𝐀𝐭𝐢𝐚-57a9ba235"



def linkedin_href() -> str:
    """LinkedIn URL with non-ASCII characters percent-encoded, safe to use as a link target."""
    return quote(LINKEDIN_URL, safe=":/%")


POWER_BASE_URL = "https://power.larc.nasa.gov/api/temporal"
POWER_NODATA = -999.0
USER_AGENT = "npcga/0.1.0"


def cache_dir() -> Path:
    """Cache folder. Override with the NPCGA_CACHE_DIR environment variable."""
    env = os.environ.get("NPCGA_CACHE_DIR")
    return Path(env) if env else Path.home() / ".npcga" / "cache"
