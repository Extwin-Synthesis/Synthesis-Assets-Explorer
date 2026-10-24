from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from .config import APP_CONFIG, ASSET_TYPES, AssetType, find_asset_type

PUBLIC_DATA_TYPE = 1
PRIVATE_DATA_TYPE = 2


@dataclass(frozen=True)
class SessionView:
    is_system_admin: bool
    is_logged_in: bool
    is_token_expired: bool

    @property
    def uses_signed_in_library(self) -> bool:
        return (not self.is_token_expired) and self.is_logged_in


@dataclass(frozen=True)
class ListEndpoint:
    url: str
    data_type: int


def category_url(asset: AssetType, visibility: str, session: SessionView) -> str | None:
    if visibility == "Public":
        if session.is_system_admin:
            return asset.category_list_url
        if session.uses_signed_in_library:
            return asset.category_list_private_url
        return asset.category_list_free_url
    if visibility == "Private":
        return asset.category_list_private_url
    return None


def content_endpoint(asset: AssetType, visibility: str, session: SessionView) -> ListEndpoint | None:
    if visibility == "Public":
        if session.is_system_admin:
            url = asset.content_url
        elif session.uses_signed_in_library:
            url = asset.content_private_url
        else:
            url = asset.content_free_url
        return ListEndpoint(url, PUBLIC_DATA_TYPE)
    if visibility == "Private":
        return ListEndpoint(asset.content_private_url, PRIVATE_DATA_TYPE)
    return None


def filter_categories(items: Any, visibility: str) -> list[dict[str, Any]]:
    if not isinstance(items, list) or len(items) < 1:
        return []
    is_system = visibility == "Public"
    return [item for item in items if item.get("IsSystem") == is_system]


def with_all_root(category_list: list[dict[str, Any]]) -> list[dict[str, Any]]:
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


def list_params(
    *,
    category_id: str,
    page_index: int,
    page_size: int,
    keyword: str,
    data_type: int,
) -> dict[str, Any]:
    return {
        "CategoryId": "" if category_id == "All" else category_id,
        "PageIndex": page_index,
        "PageSize": page_size,
        "OrderByType": -1,
        "Key": keyword,
        "DataType": data_type,
    }


def normalize_assets(asset_type_id: str, raw_list: Any) -> list[dict[str, Any]]:
    if not isinstance(raw_list, list):
        return []
    if asset_type_id == "Scene":
        return raw_list
    if asset_type_id == "_3dGS":
        return [item for item in raw_list if item.get("IsHasUsdFile") is True]
    normalized: list[dict[str, Any]] = []
    for item in raw_list:
        try:
            parsed = json.loads(item.get("UsdCurrentPath", ""))
        except Exception:
            parsed = ""
        if parsed and item.get("IsHasUsdFile") is True:
            normalized.append({**item, "UsdCurrentPath": parsed})
    return normalized


def merge_page(
    displayed: list[dict[str, Any]],
    incoming: list[dict[str, Any]],
    page_index: int,
    page_count: int,
    total_count: int,
) -> tuple[list[dict[str, Any]], bool, bool]:
    if page_index == 1:
        next_list = incoming.copy()
    else:
        next_list = displayed + incoming
    has_more = not (page_index >= page_count or total_count <= 0)
    is_append = page_index > 1
    return next_list, has_more, is_append


def thumbnail_png_url(asset: AssetType, item_id: Any) -> str:
    return f"{asset.thumbnail_url}/{item_id}.png"


def drag_usd_url(asset_type_id: str, data: dict[str, Any], cache_bust: float) -> str:
    if not data.get("IsHasUsdFile"):
        return ""
    if asset_type_id == "_3dGS":
        item_id = data.get("Id")
        if not item_id:
            return ""
        return f"{APP_CONFIG.api_server}/api/Usd/UsdzFile/{item_id}.usdz?t={cache_bust}"
    usd_path = data.get("UsdCurrentPath")
    if isinstance(usd_path, list) and usd_path:
        path_part = str(usd_path[0]).replace("//", "/").lstrip("/")
        return f"{APP_CONFIG.usd_server}/{path_part}"
    return ""


def scene_usd_url(scene_id: Any, cache_bust: float) -> str:
    return f"{APP_CONFIG.usd_server}/Scene/{scene_id}/main_ov.usd?t={cache_bust}"


@dataclass
class BrowserState:
    asset_type_id: str = ASSET_TYPES[0].id
    visibility_tab_id: str = "Public"
    category_id: str | None = None
    keyword: str = ""
    selected_asset: dict[str, Any] | None = None
    displayed_assets: list[dict[str, Any]] = field(default_factory=list)
    current_page: int = 1
    total_pages: int = 1
    total_count: int = 0
    has_more: bool = True
    generation: int = 0


def reset_query(state: BrowserState) -> None:
    state.category_id = None
    state.keyword = ""
    state.selected_asset = None
    state.displayed_assets = []
    state.current_page = 1
    state.total_pages = 1
    state.total_count = 0
    state.has_more = True


def switch_asset_type(state: BrowserState, asset_type_id: str) -> None:
    state.asset_type_id = asset_type_id
    state.generation += 1
    reset_query(state)


def switch_visibility(state: BrowserState, visibility_tab_id: str) -> None:
    state.visibility_tab_id = visibility_tab_id
    state.generation += 1
    reset_query(state)


def select_category(state: BrowserState, category_id: str) -> None:
    state.generation += 1
    state.category_id = category_id
    state.keyword = ""
    state.selected_asset = None
    state.displayed_assets = []
    state.current_page = 1
    state.total_pages = 1
    state.total_count = 0
    state.has_more = True


def begin_search(state: BrowserState, keyword: str) -> bool:
    if state.category_id is None:
        return False
    state.generation += 1
    state.keyword = keyword
    state.selected_asset = None
    state.displayed_assets = []
    state.current_page = 1
    state.has_more = True
    return True


def session_view_from(app_state: Any) -> SessionView:
    return SessionView(
        is_system_admin=bool(app_state.is_system_admin),
        is_logged_in=bool(app_state.is_logged_in),
        is_token_expired=bool(app_state.is_token_expired),
    )


def require_asset_type(asset_type_id: str) -> AssetType | None:
    return find_asset_type(asset_type_id)
