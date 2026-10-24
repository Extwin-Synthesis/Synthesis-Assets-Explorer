from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from .app_state import APP_STATE
from .catalog import category_url, filter_categories, require_asset_type, session_view_from, with_all_root
from .data_manager import DATA_MANAGER


@dataclass(frozen=True)
class TreeLoadResult:
    category_list: list[dict[str, Any]]
    stale: bool = False


async def load_category_tree(
    *,
    asset_type_id: str,
    visibility_tab_id: str,
    request_generation: int,
    current_generation: int,
) -> Optional[TreeLoadResult]:
    asset = require_asset_type(asset_type_id)
    if asset is None:
        return None
    url = category_url(asset, visibility_tab_id, session_view_from(APP_STATE))
    if url is None:
        return None

    category_list = await DATA_MANAGER.get_json(url)
    if request_generation != current_generation:
        return TreeLoadResult(category_list=[], stale=True)
    return TreeLoadResult(
        category_list=with_all_root(filter_categories(category_list, visibility_tab_id)),
        stale=False,
    )
