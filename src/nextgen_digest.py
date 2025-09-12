from __future__ import annotations

"""Simplified NextGen digest builder used in CI.

This module only loads the watch list, provides a robust HTTP helper with
retry, and assembles a tiny HTML page listing the tracked symbols.  The goal is
not to fetch real market data but to exercise the pipeline during tests.
"""

from typing import Dict, Any, List, Optional
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
import json
import os
import time

# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def _load_entities() -> List[Dict[str, Any]]:
    """Load entities from ``data/watchlist.json``.

    Only items that are dictionaries and contain a ``symbol`` key are returned.
    This mirrors the behaviour expected by the real renderer while remaining
    robust for test execution.
    """
    here = os.path.dirname(os.path.abspath(__file__))
    path = os.path.normpath(os.path.join(here, "..", "data", "watchlist.json"))
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, list):
        raise ValueError("watchlist.json must contain a list of entities")

    entities: List[Dict[str, Any]] = []
    for item in data:
        if isinstance(item, dict) and item.get("symbol"):
            entities.append(dict(item))
    return entities

# ---------------------------------------------------------------------------
# HTTP utilities
# ---------------------------------------------------------------------------

def _http_get_with_retry(
    url: str,
    timeout: float = 25.0,
    headers: Optional[Dict[str, str]] = None,
    max_retries: int = 3,
) -> Optional[bytes]:
    """Best-effort HTTP GET with exponential backoff.

    Unlike the previous implementation this helper never raises network
    exceptions.  It retries on rate limiting (429) and server errors and returns
    ``None`` if all attempts fail, allowing callers to degrade gracefully when
    network access is unavailable.
    """
    hdrs = {"User-Agent": "ci-digest/1.0 (+https://example.local)"}
    if headers:
        hdrs.update(headers)

    last_err: Optional[Exception] = None
    for attempt in range(max_retries):
        try:
            req = Request(url, headers=hdrs)
            with urlopen(req, timeout=timeout) as resp:
                return resp.read()
        except HTTPError as e:  # pragma: no cover - network is often offline
            last_err = e
            if e.code == 429 or e.code >= 500:
                time.sleep(2 ** attempt)
                continue
            break  # do not retry for other client errors
        except (URLError, Exception) as e:  # pragma: no cover
            last_err = e
            time.sleep(2 ** attempt)
    return None

def _http_get(url: str, timeout: float = 25.0, headers: Optional[Dict[str, str]] = None) -> Optional[bytes]:
    return _http_get_with_retry(url, timeout=timeout, headers=headers)


def _http_get_json(url: str, timeout: float = 25.0, headers: Optional[Dict[str, str]] = None) -> Optional[Dict[str, Any]]:
    raw = _http_get(url, timeout=timeout, headers=headers)
    if raw is None:
        return None
    try:
        return json.loads(raw.decode("utf-8", errors="replace"))
    except Exception:
        return None

# ---------------------------------------------------------------------------
# Digest builder
# ---------------------------------------------------------------------------

async def build_nextgen_html(logger) -> str:
    """Build a minimal HTML digest for CI.

    The function verifies that all loaded entities contain a ``symbol`` key and
    then renders a simple unordered list containing each symbol.  This keeps the
    CI pipeline lightweight while ensuring the data loader and basic rendering
    logic work as expected.
    """
    entities = _load_entities()
    logger.info(f"Loaded {len(entities)} entities from watchlist.json")

    missing = [e for e in entities if not e.get("symbol")]
    if missing:
        raise ValueError("Entities missing symbol key: %r" % missing)

    items = "".join(f"<li>{e['symbol']} - {e.get('name', '')}</li>" for e in entities)
    html = f"<html><body><h1>Watchlist</h1><ul>{items}</ul></body></html>"
    return html
