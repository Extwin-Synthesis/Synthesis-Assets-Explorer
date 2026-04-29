from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ThumbnailStrategy:
    # Render real URL immediately.
    direct_url: str = "direct_url"
    # Render placeholder first, then switch to real URL next frame.
    placeholder_then_update: str = "placeholder_then_update"
    # Reserved provider-based strategy (currently safe-fallback to direct_url).
    provider: str = "provider"

