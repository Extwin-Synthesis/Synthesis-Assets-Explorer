from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from .data_manager import ASSET_TYPES, DATA_MANAGER


@dataclass(frozen=True)
class TreeLoadResult:
    category_list: List[Dict[str, Any]]
    stale: bool = False


def resolve_asset_type(asset_type_id: str) -> Optional[Dict[str, Any]]:
    return next((item for item in ASSET_TYPES if item["Id"] == asset_type_id), None)


def with_all_root(category_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not category_list:
        return []
    return [
        {
            "CategoryId": "All",
            "CategoryLists": [],
            "CategoryName": "All",
            "Comment": "",
            "IsSystem": False,
            "ParentCategoryId": None,
        },
        *category_list,
    ]


async def load_category_tree(
    *,
    asset_type_id: str,
    visibility_tab_id: str,
    request_generation: int,
    current_generation: int,
) -> Optional[TreeLoadResult]:
    selected_asset_type = resolve_asset_type(asset_type_id)
    if not selected_asset_type:
        return None

    category_list = await DATA_MANAGER.get_category_tree(asset_type_id, visibility_tab_id)
    if request_generation != current_generation:
        return TreeLoadResult(category_list=[], stale=True)
    return TreeLoadResult(category_list=with_all_root(category_list), stale=False)

