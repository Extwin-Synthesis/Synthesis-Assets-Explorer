from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from .app_state import APP_STATE
from .catalog import (
    BrowserState,
    begin_search,
    content_endpoint,
    list_params,
    merge_page,
    normalize_assets,
    require_asset_type,
    reset_query,
    select_category,
    session_view_from,
    switch_asset_type,
    switch_visibility,
)
from .config import APP_CONFIG
from .data_manager import DATA_MANAGER


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
    displayed_assets: list[dict[str, Any]]
    total_pages: int
    total_count: int
    has_more: bool
    is_append: bool
    thumbnail_url: str
    stale: bool = False


class Browser:
    def __init__(self, page_size: int):
        self.state = BrowserState()
        self.page_size = page_size
        self._loading_keys: set[tuple[int, int]] = set()
        self._loading = False

    @property
    def loading(self) -> bool:
        return self._loading

    def switch_asset_type(self, asset_type_id: str) -> None:
        switch_asset_type(self.state, asset_type_id)

    def switch_visibility(self, visibility_tab_id: str) -> None:
        switch_visibility(self.state, visibility_tab_id)

    def select_category(self, category_id: str) -> None:
        select_category(self.state, category_id)

    def begin_search(self, keyword: str) -> bool:
        return begin_search(self.state, keyword)

    def reset_query(self) -> None:
        reset_query(self.state)

    def context(self, page_index: int, keyword: str | None = None) -> QueryContext:
        state = self.state
        return QueryContext(
            generation=state.generation,
            asset_type_id=state.asset_type_id,
            visibility_tab_id=state.visibility_tab_id,
            category_id=state.category_id or "All",
            page_index=page_index,
            page_size=self.page_size,
            keyword=state.keyword if keyword is None else keyword,
        )

    async def load(self, ctx: QueryContext) -> Optional[AssetPageResult]:
        request_key = (ctx.generation, ctx.page_index)
        if request_key in self._loading_keys:
            return None

        asset = require_asset_type(ctx.asset_type_id)
        if asset is None:
            return None
        endpoint = content_endpoint(asset, ctx.visibility_tab_id, session_view_from(APP_STATE))
        if endpoint is None:
            return None

        self._loading_keys.add(request_key)
        self._loading = True
        try:
            result = await DATA_MANAGER.get_json(
                endpoint.url,
                list_params(
                    category_id=ctx.category_id,
                    page_index=ctx.page_index,
                    page_size=ctx.page_size,
                    keyword=ctx.keyword,
                    data_type=endpoint.data_type,
                ),
            )
            if ctx.generation != self.state.generation:
                return AssetPageResult(
                    displayed_assets=self.state.displayed_assets,
                    total_pages=self.state.total_pages,
                    total_count=self.state.total_count,
                    has_more=False,
                    is_append=False,
                    thumbnail_url=asset.thumbnail_url,
                    stale=True,
                )

            raw_list = result.get("List", []) if isinstance(result, dict) else []
            total_pages = result.get("PageCount", 0) if isinstance(result, dict) else 0
            total_count = result.get("Count", 0) if isinstance(result, dict) else 0
            incoming = normalize_assets(ctx.asset_type_id, raw_list)
            merged, has_more, is_append = merge_page(
                self.state.displayed_assets,
                incoming,
                ctx.page_index,
                total_pages,
                total_count,
            )
            self.state.displayed_assets = merged
            self.state.total_pages = total_pages
            self.state.total_count = total_count
            self.state.has_more = has_more
            self.state.current_page = ctx.page_index
            return AssetPageResult(
                displayed_assets=merged,
                total_pages=total_pages,
                total_count=total_count,
                has_more=has_more,
                is_append=is_append,
                thumbnail_url=asset.thumbnail_url,
            )
        finally:
            self._loading_keys.discard(request_key)
            self._loading = bool(self._loading_keys)


def load_record_url() -> str:
    return f"{APP_CONFIG.api_server}/api/Global/AddLoadRecord"
