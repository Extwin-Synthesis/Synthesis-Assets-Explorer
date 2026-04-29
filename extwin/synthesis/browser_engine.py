from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Literal, Optional, Set, Tuple

import carb

from .data_manager import ASSET_TYPES, DATA_MANAGER, TOKEN_EXPIRED_MESSAGE

UiEventLevel = Literal["info", "warning", "error"]


@dataclass(frozen=True)
class UiEvent:
    code: str
    message: str
    level: UiEventLevel = "info"


@dataclass(frozen=True)
class QueryContext:
    generation: int
    asset_type_id: str
    visibility_tab_id: str
    category_id: str
    page_index: int
    page_size: int
    keyword: str


@dataclass(frozen=True)
class AssetPageResult:
    displayed_assets: List[Dict[str, Any]]
    total_pages: int
    total_count: int
    has_more: bool
    is_append: bool
    thumbnail_url: str
    stale: bool = False


def _build_params(ctx: QueryContext) -> Dict[str, Any]:
    return {
        "CategoryId": "" if ctx.category_id == "All" else ctx.category_id,
        "PageIndex": ctx.page_index,
        "PageSize": ctx.page_size,
        "OrderByType": -1,
        "Key": ctx.keyword,
    }


def _normalize_assets(asset_type_id: str, raw_list: Any) -> List[Dict[str, Any]]:
    if not isinstance(raw_list, list):
        return []
    if asset_type_id == "Scene":
        return raw_list
    if asset_type_id == "_3dGS":
        return [x for x in raw_list if x.get("IsHasUsdFile") is True]
    out: List[Dict[str, Any]] = []
    for item in raw_list:
        try:
            parsed = json.loads(item.get("UsdCurrentPath", ""))
        except Exception:
            parsed = ""
        if parsed and item.get("IsHasUsdFile") is True:
            out.append({**item, "UsdCurrentPath": parsed})
    return out


def _merge_page(
    displayed: List[Dict[str, Any]],
    incoming: List[Dict[str, Any]],
    page_index: int,
    page_count: int,
    total_count: int,
) -> Tuple[List[Dict[str, Any]], bool, bool]:
    if page_index == 1:
        next_list = incoming.copy()
    else:
        next_list = displayed + incoming
    has_more = not (page_index >= page_count or total_count <= 0)
    is_append = page_index > 1
    return next_list, has_more, is_append


async def _load_asset_page(
    *,
    ctx: QueryContext,
    current_generation: int,
    displayed_assets: List[Dict[str, Any]],
) -> Optional[AssetPageResult]:
    selected_asset_type = next((x for x in ASSET_TYPES if x["Id"] == ctx.asset_type_id), None)
    if not selected_asset_type:
        return None

    result = await DATA_MANAGER.get_asset_list(
        ctx.asset_type_id, _build_params(ctx), ctx.visibility_tab_id
    )
    if ctx.generation != current_generation:
        return AssetPageResult(
            displayed_assets=displayed_assets,
            total_pages=0,
            total_count=0,
            has_more=False,
            is_append=False,
            thumbnail_url=selected_asset_type["ThumbnailUrl"],
            stale=True,
        )

    raw_list = result.get("List", [])
    total_pages = result.get("PageCount", 0)
    total_count = result.get("Count", 0)
    normalized = _normalize_assets(ctx.asset_type_id, raw_list)
    merged_displayed, has_more, is_append = _merge_page(
        displayed_assets,
        normalized,
        ctx.page_index,
        total_pages,
        total_count,
    )
    return AssetPageResult(
        displayed_assets=merged_displayed,
        total_pages=total_pages,
        total_count=total_count,
        has_more=has_more,
        is_append=is_append,
        thumbnail_url=selected_asset_type["ThumbnailUrl"],
    )


@dataclass
class BrowserState:
    asset_type_id: str = ASSET_TYPES[0]["Id"]
    visibility_tab_id: str = "Public"
    category_id: Optional[str] = None
    selected_asset: Optional[Dict[str, Any]] = None
    displayed_assets: List[Dict[str, Any]] = field(default_factory=list)
    current_page: int = 1
    total_pages: int = 1
    total_count: int = 0
    has_more: bool = True
    generation: int = 0


@dataclass(frozen=True)
class BrowserLoadResult:
    page: Optional[AssetPageResult]
    event: Optional[UiEvent] = None


class BrowserController:
    def __init__(self, page_size_resolver: Callable[[], int]):
        self.state = BrowserState()
        self._page_size_resolver = page_size_resolver
        self._loading_keys: Set[tuple[int, int]] = set()
        self._loading = False

    @property
    def loading(self) -> bool:
        return self._loading

    def reset_query_state(self) -> None:
        self.state.category_id = None
        self.state.displayed_assets = []
        self.state.current_page = 1
        self.state.total_pages = 1
        self.state.total_count = 0
        self.state.has_more = True
        self.state.selected_asset = None

    def switch_asset_type(self, asset_type_id: str) -> None:
        self.state.asset_type_id = asset_type_id
        self.state.generation += 1
        self.reset_query_state()
        carb.log_info(f"[BrowserController] Switched asset type to {asset_type_id}")

    def switch_visibility_tab(self, visibility_tab_id: str) -> None:
        self.state.visibility_tab_id = visibility_tab_id
        self.state.generation += 1
        self.reset_query_state()
        carb.log_info(f"[BrowserController] Switched visibility tab to {visibility_tab_id}")

    def begin_category_selection(self, category_id: Optional[str]) -> None:
        self.state.generation += 1
        self.state.category_id = category_id
        self.state.displayed_assets = []
        self.state.current_page = 1
        self.state.total_pages = 1
        self.state.total_count = 0
        self.state.has_more = True
        self.state.selected_asset = None
        carb.log_info(f"[BrowserController] Begin category selection: {category_id}")

    def build_context(self, *, page_index: int, keyword: str = "") -> QueryContext:
        return QueryContext(
            generation=self.state.generation,
            asset_type_id=self.state.asset_type_id,
            visibility_tab_id=self.state.visibility_tab_id,
            category_id=self.state.category_id or "All",
            page_index=page_index,
            page_size=self._page_size_resolver(),
            keyword=keyword,
        )

    async def load_for_context(self, ctx: QueryContext) -> BrowserLoadResult:
        request_key = (ctx.generation, ctx.page_index)
        if request_key in self._loading_keys:
            carb.log_info(f"[BrowserController] Skip duplicated request: {request_key}")
            return BrowserLoadResult(page=None)

        self._loading_keys.add(request_key)
        self._loading = True
        carb.log_info(
            f"[BrowserController] Load page start: gen={ctx.generation}, page={ctx.page_index}, size={ctx.page_size}, category={ctx.category_id}"
        )
        try:
            try:
                page = await _load_asset_page(
                    ctx=ctx,
                    current_generation=self.state.generation,
                    displayed_assets=self.state.displayed_assets,
                )
            except Exception as e:
                if str(e) == TOKEN_EXPIRED_MESSAGE:
                    carb.log_warn("[BrowserController] Token expired during page load.")
                    return BrowserLoadResult(
                        page=None,
                        event=UiEvent(
                            code="TOKEN_EXPIRED",
                            message="The token has expired. Please log in again. Now, you will continue browsing as a free user.",
                            level="warning",
                        ),
                    )
                return BrowserLoadResult(
                    page=None,
                    event=UiEvent(code="BROWSER_LOAD_FAILED", message=str(e), level="error"),
                )

            if page is None or page.stale:
                return BrowserLoadResult(page=page)

            self.state.displayed_assets = page.displayed_assets
            self.state.total_pages = page.total_pages
            self.state.total_count = page.total_count
            self.state.has_more = page.has_more
            self.state.current_page = ctx.page_index
            carb.log_info(
                f"[BrowserController] Load page success: page={ctx.page_index}, displayed={len(self.state.displayed_assets)}, has_more={self.state.has_more}"
            )
            return BrowserLoadResult(page=page)
        finally:
            self._loading_keys.discard(request_key)
            self._loading = bool(self._loading_keys)


async def load_asset_page(
    *,
    ctx: QueryContext,
    current_generation: int,
    displayed_assets: List[Dict[str, Any]],
) -> Optional[AssetPageResult]:
    """Compatibility API used by window layer."""
    return await _load_asset_page(
        ctx=ctx,
        current_generation=current_generation,
        displayed_assets=displayed_assets,
    )
