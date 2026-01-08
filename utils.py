from __future__ import annotations

import hashlib
from typing import Iterable, Optional

from dotenv import load_dotenv

env_loaded = False

def ensure_env_loaded():
    global env_loaded
    if not env_loaded:
        load_dotenv()
        env_loaded = True


def _normalize_bbox(bbox: Iterable[float]) -> str:
    parts = []
    for value in bbox:
        if isinstance(value, (int, float)):
            parts.append(f"{value:.3f}")
    return "_".join(parts)


def generate_stable_element_id(
    element_type: str,
    page_number: int,
    *,
    content: str = "",
    span_offset: Optional[int] = None,
    span_length: Optional[int] = None,
    bbox: Optional[Iterable[float]] = None,
    anchor: Optional[str] = None,
    index: Optional[int] = None,
) -> str:
    """Generate a stable ID for an element using the most reliable anchors available."""
    if anchor:
        anchor_str = anchor
    elif span_offset is not None and span_length is not None:
        anchor_str = f"span:{span_offset}:{span_length}"
    elif bbox:
        anchor_str = f"bbox:{_normalize_bbox(bbox)}"
    elif content:
        anchor_str = f"content:{content.strip()}"
    elif index is not None:
        anchor_str = f"index:{index}"
    else:
        anchor_str = "fallback"

    hash_input = f"{element_type}|{page_number}|{anchor_str}"
    digest = hashlib.md5(hash_input.encode()).hexdigest()[:8]
    return f"{element_type}_{page_number}_{digest}"
