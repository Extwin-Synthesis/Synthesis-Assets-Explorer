import asyncio
import base64
import json
import os
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

import carb
import omni.kit.app
import omni.kit.notification_manager as nm
import omni.ui as ui
from aiohttp import web
from omni.ui import color as cl

from .app_state import APP_STATE
from .asset_grid_runtime import populate_grid_items_into_container
from .browser_engine import QueryContext, load_asset_page
from .data_manager import ASSET_TYPES, BASE_URL1, BASE_URL2, BASE_URL3, DATA_MANAGER, TOKEN_EXPIRED_MESSAGE
from .scene_runtime import load_scene
from .setting_modal import SettingModal
from .style import get_style
from .thumbnail_strategy import ThumbnailStrategy
from .tree_models import CategoryDelegate, CategoryItem, CategoryModel
from .tree_service import load_category_tree
from .util import on_copy_to_clipboard

ASSETS_EXPLORER_NAME = "Extwin Assets"
EXT_PATH = os.path.dirname(__file__)
IMAGE_EMPTY_PATH = os.path.join(EXT_PATH, "asset", "empty.png")
GLOBAL_STYLE = get_style()
LOGIN_RESULT_LISTEN_PORT = 8090
VISIBILITY_TABS = [{"Id": "Public", "Name": "Public"}, {"Id": "Private", "Name": "Private"}]
ALLOWED_ORIGINS = {"http://localhost:5173", "http://127.0.0.1:5173", "https://synthesis.extwin.com"}
IMAGE_STYLE_UNSELECTED = {"border_width": 0, "border_radius": 4}
IMAGE_STYLE_SELECTED = {"border_width": 2, "border_radius": 4, "border_color": cl("#34c7ff")}
THUMBNAIL_RENDER_STRATEGY = ThumbnailStrategy.provider
GRID_COLUMN_WIDTH = 210
GRID_ROW_HEIGHT = 180
GRID_PRELOAD_EXTRA_ROWS = 2
DEFAULT_PAGE_SIZE = 60
MIN_PAGE_SIZE = 24
MAX_PAGE_SIZE = 180

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


class SynthesisAssetsWindow(ui.Window):
    def __init__(self, visible=True):
        super().__init__(ASSETS_EXPLORER_NAME, visible=visible)
        self.frame.set_build_fn(self._build_main_view)
        self.frame.set_style(GLOBAL_STYLE)
        self.state = BrowserState()
        self._gap = 6
        self._btn_size = 24
        self._default_page_size = DEFAULT_PAGE_SIZE
        self._managed_tasks: Set[asyncio.Task] = set()
        self._loading = False
        self._loading_keys: Set[tuple] = set()
        self._web_runner: Optional[web.AppRunner] = None
        self._is_cleaning_up = False

        self._category_view_frame: Optional[ui.Frame] = None
        self._tree_panel_frame: Optional[ui.ScrollingFrame] = None
        self._grid_panel_frame: Optional[ui.ScrollingFrame] = None
        self._detail_panel_frame: Optional[ui.ScrollingFrame] = None
        self._tree_widget: Optional[ui.TreeView] = None
        self._grid_vgrid_container: Optional[ui.VGrid] = None
        self._current_selected_thumb: Optional[ui.Image] = None
        self._thumbnail_provider_refs: Dict[int, Any] = {}
        self._grid_rendered_count = 0
        self._active_search_keyword = ""

        self.deferred_dock_in("Console", active_window=ui.DockPolicy.CURRENT_WINDOW_IS_ACTIVE)
        self._spawn(self._start_login_result_listener(), "start_login_listener")

    def _spawn(self, coro, name: str) -> asyncio.Task:
        task = asyncio.ensure_future(coro)
        self._managed_tasks.add(task)
        def _done(t: asyncio.Task):
            self._managed_tasks.discard(t)
            if t.cancelled():
                return
            exc = t.exception()
            if exc:
                carb.log_error(f"[{name}] {exc}")
        task.add_done_callback(_done)
        return task

    def _cancel_all_tasks(self):
        for task in list(self._managed_tasks):
            if not task.done():
                task.cancel()
        self._managed_tasks.clear()

    async def _start_login_result_listener(self):
        if self._web_runner:
            await self._web_runner.cleanup()
            self._web_runner = None
        app = web.Application()
        app.router.add_options("/", self._handle_cors_preflight)
        app.router.add_post("/", self._handle_receive_login_result)
        self._web_runner = web.AppRunner(app)
        await self._web_runner.setup()
        site = web.TCPSite(
            self._web_runner,
            "127.0.0.1",
            LOGIN_RESULT_LISTEN_PORT,
        )
        try:
            await site.start()
            carb.log_info(f"Login listener on 127.0.0.1:{LOGIN_RESULT_LISTEN_PORT}")
        except OSError as e:
            carb.log_warn(f"Login listener start failed: {e}")

    async def _handle_cors_preflight(self, request: web.Request):
        origin = request.headers.get("Origin")
        if origin not in ALLOWED_ORIGINS:
            return web.Response(status=403)

        return web.Response(
            status=204,
            headers={
                "Access-Control-Allow-Origin": origin,
                "Access-Control-Allow-Methods": "POST, OPTIONS",
                "Access-Control-Allow-Headers": "Content-Type",
            },
        )

    async def _handle_receive_login_result(self, request: web.Request):
        origin = str(request.headers.get("Origin")).lower()
        if origin not in ALLOWED_ORIGINS:
            return web.json_response(
                {"error": "Origin not allowed"},
                status=403,
                headers={"Access-Control-Allow-Origin": origin},
            )
        try:
            data = await request.json()
        except Exception as e:
            carb.log_error(f"Failed to parse login result JSON: {e}")
            return web.json_response(
                {"error": "Invalid JSON"},
                status=400,
                headers={"Access-Control-Allow-Origin": origin},
            )

        token = data.get("Token")
        login_user_info = data.get("LoginUserInfo")

        if token and login_user_info:
            APP_STATE.user_info = login_user_info
            APP_STATE.token = token
            APP_STATE.is_token_expired = False
            user_type = login_user_info.get("UserType", 5)
            APP_STATE.is_system_admin = user_type <= 2
            self.state.visibility_tab_id = VISIBILITY_TABS[0]["Id"]
            self._spawn(self._delayed_rebuild_main_view(), "rebuild_after_login")
            nm.post_notification(
                "Auth info updated successfully.",
                duration=2.0,
                status=nm.NotificationStatus.INFO,
            )
            return web.json_response(
                {"status": "success"},
                headers={"Access-Control-Allow-Origin": origin},
            )
        else:
            carb.log_warn("Login result missing Token or LoginUserInfo")
            nm.post_notification(
                "Invalid auth info format.",
                duration=2.0,
                status=nm.NotificationStatus.WARNING,
            )
            return web.json_response(
                {"error": "Missing Token or UserInfo"},
                status=400,
                headers={"Access-Control-Allow-Origin": origin},
            )

    def _rebuild_main_view(self):
        self.frame.clear()
        self._build_main_view()

    def _on_asset_type_click(self, asset_type: Dict[str, Any]):
        self.state.asset_type_id = asset_type["Id"]
        self.state.generation += 1
        self._reset_query_state()
        self._spawn(self._delayed_rebuild_main_view(), "rebuild_main")

    async def _delayed_rebuild_main_view(self):
        await omni.kit.app.get_app().next_update_async()
        self._rebuild_main_view()

    def _rebuild_tab_view(self):
        if self._category_view_frame:
            self._category_view_frame.clear()
        self._build_category_view()

    def _on_visibility_tab_click(self, tab: Dict[str, str]):
        self.state.visibility_tab_id = tab["Id"]
        self.state.generation += 1
        self._reset_query_state()
        self._spawn(self._delayed_rebuild_tab_view(), "rebuild_tab")

    async def _delayed_rebuild_tab_view(self):
        await omni.kit.app.get_app().next_update_async()
        self._rebuild_tab_view()

    def destroy(self):
        self.clean_up()
        super().destroy()

    def clean_up(self):
        if self._is_cleaning_up:
            return
        self._is_cleaning_up = True
        self._cancel_all_tasks()

        async def _cleanup():
            runner = self._web_runner
            self._web_runner = None
            if runner:
                try:
                    await runner.cleanup()
                except Exception as e:
                    carb.log_warn(f"Ignore web runner cleanup error: {e}")
            try:
                await DATA_MANAGER.close()
            finally:
                self._is_cleaning_up = False

        self._spawn(_cleanup(), "window_cleanup")

    def _build_main_view(self):
        with self.frame:
            with ui.HStack(spacing=0):
                with ui.ScrollingFrame(
                    width=ui.Length(150),
                    horizontal_scrollbar_policy=ui.ScrollBarPolicy.SCROLLBAR_ALWAYS_OFF,
                    vertical_scrollbar_policy=ui.ScrollBarPolicy.SCROLLBAR_AS_NEEDED,
                ):
                    with ui.VStack(spacing=self._gap):
                        for asset_type_item in ASSET_TYPES:
                            ui.Button(
                                asset_type_item.get("Name"),
                                height=self._btn_size,
                                selected=asset_type_item["Id"] == self.state.asset_type_id,
                                checked=asset_type_item["Id"] == self.state.asset_type_id,
                                clicked_fn=lambda a_type=asset_type_item: self._on_asset_type_click(
                                    a_type
                                ),
                            )

                ui.Line(
                    alignment=ui.Alignment.H_CENTER,
                    width=ui.Length(4),
                    style={"color": cl("#4e5152"), "border_width": 4},
                )
                ui.Spacer(width=ui.Length(18))

                self._category_view_frame = ui.Frame()
                self._build_category_view()

    def _build_category_view(self):
        if not self._category_view_frame:
            return

        with self._category_view_frame:
            with ui.VStack(spacing=0, width=ui.Fraction(1)):
                self._build_category_header()
                ui.Line(
                    height=24,
                    alignment=ui.Alignment.V_CENTER,
                    style={"color": cl("#4e5152"), "border_width": 4},
                )
                self._build_category_toolbar()
                ui.Line(
                    height=4,
                    alignment=ui.Alignment.V_CENTER,
                    style={"color": cl("#4e5152"), "border_width": 4},
                )
                ui.Spacer(height=6)
                self._build_category_content_panels()
                self._spawn(self._load_and_build_asset_tree(self.state.generation), "load_tree")

    def _handle_open_in_browser(self):
        """Handles the 'Open In Browser' button click event."""
        import webbrowser

        selected_asset_type = next(
            (
                item
                for item in ASSET_TYPES
                if item["Id"] == self.state.asset_type_id
            ),
            None,
        )
        if not selected_asset_type:
            carb.log_error("Invalid asset type selection.")
            return

        final_url_to_open = f'{BASE_URL3}/#/home?id={self.state.selected_asset.get("Id","")}&t={selected_asset_type.get("TypeInBrowser","")}'
        webbrowser.open(final_url_to_open)

    def _handle_setting(self):
        """Handles the settings button click event."""
        carb.log_info("Settings button clicked.")
        field_defs = [
            SettingModal.FieldDef("usd_server", "Server", ui.StringField, BASE_URL2),
            SettingModal.FieldDef("auth_info", "Auth Info", ui.StringField, ""),
        ]

        def _handle_form_submit(dialog: SettingModal):
            values = dialog.get_values()
            new_usd_server = values.get("usd_server", BASE_URL2).strip()
            if not new_usd_server:
                nm.post_notification(
                    "Server can not be empty",
                    duration=2.0,
                    status=nm.NotificationStatus.WARNING,
                )
                return
            if new_usd_server != BASE_URL2:
                import extwin.synthesis.data_manager as dm
                dm.BASE_URL2 = new_usd_server
                msg = f"Server updated to: {new_usd_server}"
                carb.log_info(msg)
                nm.post_notification(
                    msg, duration=2.0, status=nm.NotificationStatus.INFO
                )
            else:
                nm.post_notification(
                    "Server unchanged",
                    duration=2.0,
                    status=nm.NotificationStatus.INFO,
                )

            auth_info = values.get("auth_info", "").strip()
            if auth_info:
                try:
                    decoded_bytes = base64.b64decode(auth_info)
                    auth_info = decoded_bytes.decode("utf-8")
                    auth_data = json.loads(auth_info)
                    token = auth_data.get("Token")
                    login_user_info = auth_data.get("LoginUserInfo", None)
                    if token and login_user_info:
                        APP_STATE.user_info = login_user_info
                        APP_STATE.token = token
                        APP_STATE.is_token_expired = False
                        user_type = login_user_info.get("UserType", 5)
                        APP_STATE.is_system_admin = user_type <= 2
                        self.state.visibility_tab_id = VISIBILITY_TABS[0]["Id"]
                        self._spawn(self._delayed_rebuild_main_view(), "rebuild_after_setting")
                        nm.post_notification(
                            "Auth info updated successfully.",
                            duration=2.0,
                            status=nm.NotificationStatus.INFO,
                        )
                    else:
                        nm.post_notification(
                            "Invalid auth info format.",
                            duration=2.0,
                            status=nm.NotificationStatus.WARNING,
                        )
                except json.JSONDecodeError:
                    nm.post_notification(
                        "Failed to parse auth info.",
                        duration=2.0,
                        status=nm.NotificationStatus.WARNING,
                    )
            dialog.destroy()

        dialog = SettingModal(
            width=400,
            title="Settings",
            field_defs=field_defs,
            ok_handler=lambda dialog: _handle_form_submit(dialog),
        )
        dialog.window.height = 0  # Auto-size height
        dialog.show()

    def _build_category_header(self):
        """Builds the fixed header containing tabs and logout button."""
        with ui.HStack(spacing=self._gap, height=0):
            if APP_STATE.is_logged_in and not APP_STATE.is_system_admin:
                for tab_item in VISIBILITY_TABS:
                    ui.Button(
                        tab_item.get("Name"),
                        width=ui.Length(120),
                        height=self._btn_size,
                        checked=tab_item.get("Id") == self.state.visibility_tab_id,
                        selected=tab_item.get("Id") == self.state.visibility_tab_id,
                        clicked_fn=lambda tab=tab_item: self._on_visibility_tab_click(
                            tab
                        ),
                    )

            ui.Spacer()
            ui.Button(
                "Setting",
                width=80,
                height=self._btn_size,
                clicked_fn=self._handle_setting,
            )

    def _build_category_toolbar(self):
        """Builds the toolbar with toggle buttons and search bar."""
        with ui.HStack(spacing=4, height=24):
            self._btn_toggle_tree = ui.Button(text="Toggle Tree", width=ui.Length(100))
            self._search_bar = ui.StringField(style={"background_color": cl("#333333")})
            self._btn_search = ui.Button(text="Search", width=ui.Length(72))
            self._btn_toggle_detail = ui.Button(
                text="Toggle Detail", width=ui.Length(100)
            )

            self._btn_toggle_tree.set_mouse_pressed_fn(
                lambda a, b, c, d: setattr(self._tree_panel_frame, "visible", not self._tree_panel_frame.visible)
            )

            def _toggle_detail():
                if self._detail_panel_frame:
                    self._detail_panel_frame.visible = (
                        not self._detail_panel_frame.visible
                    )
            self._btn_toggle_detail.set_mouse_pressed_fn(
                lambda a, b, c, d: _toggle_detail()
            )

            try:
                # Pressing Enter in StringField ends edit in omni.ui, trigger search immediately.
                self._search_bar.model.add_end_edit_fn(self._on_search_submit)
            except Exception:
                # Keep search button as fallback if end-edit callback is unavailable.
                pass
            self._btn_search.set_mouse_pressed_fn(
                lambda x, y, btn, mod: self._on_search_submit(self._search_bar.model)
                if btn == 0
                else None
            )

    async def _perform_search(self, keyword_model: ui.SimpleStringModel, trigger: str) -> None:
        keyword = keyword_model.get_value_as_string().strip()
        self._active_search_keyword = keyword
        carb.log_info(f"Search keyword ({trigger}): '{keyword}'")
        category_id = self.state.category_id
        if category_id is not None:
            self.state.generation += 1
            # Keep current category, reset paging, then issue page-1 search request.
            self._prepare_query_for_selected_category(category_id)
            self._show_grid_loading_hint("Searching assets...")
            await self._load_assets_for_context(
                self._build_context(page_index=1, keyword=keyword)
            )
        else:
            carb.log_info(
                "Search triggered, but no category is currently selected."
            )

    def _on_search_submit(self, keyword_model: ui.SimpleStringModel):
        self._spawn(self._perform_search(keyword_model, "submit"), "submit_search")

    def _build_category_content_panels(self):
        with ui.HStack(spacing=0):
            self._tree_panel_frame = ui.ScrollingFrame(
                width=ui.Length(240),
                horizontal_scrollbar_policy=ui.ScrollBarPolicy.SCROLLBAR_AS_NEEDED,
                vertical_scrollbar_policy=ui.ScrollBarPolicy.SCROLLBAR_AS_NEEDED,
            )
            with self._tree_panel_frame:
                ui.Label(
                    "Loading...",
                    name="loading_label",
                    alignment=ui.Alignment.CENTER,
                    style={"color": cl.green},
                )

            ui.Line(width=ui.Length(4), style={"color": cl("#4e5152"), "border_width": 4})

            with ui.HStack(spacing=0):
                self._grid_panel_frame = ui.ScrollingFrame(
                    width=ui.Fraction(1),
                    horizontal_scrollbar_policy=ui.ScrollBarPolicy.SCROLLBAR_AS_NEEDED,
                    vertical_scrollbar_policy=ui.ScrollBarPolicy.SCROLLBAR_AS_NEEDED,
                )

                self._set_lazy_load_callback(self._grid_panel_frame)
                ui.Line(width=ui.Length(4), style={"color": cl("#4e5152"), "border_width": 4})
                self._detail_panel_frame = ui.ScrollingFrame(
                    width=ui.Length(400),
                    horizontal_scrollbar_policy=ui.ScrollBarPolicy.SCROLLBAR_AS_NEEDED,
                    vertical_scrollbar_policy=ui.ScrollBarPolicy.SCROLLBAR_AS_NEEDED,
                )
                self._build_detail_panel(None, None)

    def _set_lazy_load_callback(self, scrolling_frame: ui.ScrollingFrame):
        def on_scrolling(scroll_pos_y):
            if (
                self._loading
                or not self.state.has_more
                or not self._grid_panel_frame
            ):
                return
            max_scroll = scrolling_frame.scroll_y_max
            if max_scroll <= 0:
                return
            if scroll_pos_y / max_scroll >= 0.8:
                carb.log_info("Lazy Load triggered by scroll.")
                self._spawn(self._lazy_load_next_page_if_needed(), "lazy_load")

        scrolling_frame.set_scroll_y_changed_fn(on_scrolling)

    def _on_copy_name_to_clipboard(self, name: str):
        result = on_copy_to_clipboard(to_copy=name)
        if result == 1:
            nm.post_notification(
                "Name copied to clipboard successfully.",
                duration=2.0,
                status=nm.NotificationStatus.INFO,
            )

    def _build_detail_panel(self, asset_data: Optional[Dict[str, Any]], img_url):
        if not self._detail_panel_frame:
            return

        self._detail_panel_frame.clear()

        with self._detail_panel_frame:
            if asset_data:
                asset_type_id = self.state.asset_type_id
                with ui.HStack():
                    ui.Spacer(width=14)
                    with ui.VStack(
                        spacing=0,
                        style={"color": cl("#ffffffff")},
                    ):
                        ui.Spacer(height=2)
                        with ui.HStack(height=0, spacing=6):
                            if asset_type_id == "Scene":
                                ui.Button(
                                    "Load",
                                    width=100,
                                    height=self._btn_size,
                                    clicked_fn=self._load_scene,
                                )
                            ui.Button(
                                "View In Browser",
                                width=120,
                                height=self._btn_size,
                                clicked_fn=self._handle_open_in_browser,
                            )
                            ui.Button(
                                "Copy Name",
                                width=80,
                                height=24,
                                clicked_fn=lambda: self._on_copy_name_to_clipboard(
                                    asset_data.get("Name")
                                ),
                            )
                            if (
                                asset_type_id == "SimReady"
                                or asset_type_id == "Robot"
                            ):
                                with ui.HStack(height=24, spacing=0):
                                    ui.Label("Articulated:", width=0, height=24)
                                    checkbox = ui.CheckBox(
                                        style={
                                            "color": cl.green,
                                            "margin": 6,
                                        },
                                        enabled=False,
                                    )
                                    checkbox.model.set_value(
                                        asset_data.get("IsHasArticulus", False)
                                    )

                        ui.Image(
                            img_url,
                            height=300,
                            alignment=ui.Alignment.LEFT,
                            fill_policy=ui.FillPolicy.PRESERVE_ASPECT_FIT,
                            style={"border_radius": 4},
                        )
                        ui.Label(
                            asset_data.get("Name", "Unnamed"),
                            alignment=ui.Alignment.LEFT,
                            word_wrap=True,
                            height=0,
                        )
                        ui.Spacer(height=6)

                        with ui.CollapsableFrame("Asset Info"):
                            with ui.VStack(spacing=12):
                                if asset_type_id != "Scene":
                                    with ui.HStack():
                                        ui.Spacer(width=6)
                                        ui.Label("Description:", width=0, height=0)
                                        ui.Spacer(width=6)
                                        ui.Label(
                                            asset_data.get("Comment"),
                                            alignment=ui.Alignment.TOP,
                                        )

            else:
                ui.Label(
                    "Select an asset to view details.",
                    alignment=ui.Alignment.CENTER,
                )

    def _load_scene(self):
        load_scene(self)

    def _build_context(self, page_index: int, keyword: Optional[str] = None) -> QueryContext:
        kw = keyword if keyword is not None else self._active_search_keyword
        return QueryContext(
            generation=self.state.generation,
            asset_type_id=self.state.asset_type_id,
            visibility_tab_id=self.state.visibility_tab_id,
            category_id=self.state.category_id or "All",
            page_index=page_index,
            page_size=self._resolve_page_size(),
            keyword=kw,
        )

    @staticmethod
    def _as_float_dimension(value: Any) -> float:
        if isinstance(value, (int, float)):
            return float(value)
        raw = getattr(value, "value", None)
        if isinstance(raw, (int, float)):
            return float(raw)
        return 0.0

    def _resolve_page_size(self) -> int:
        frame = self._grid_panel_frame
        if not frame:
            return self._default_page_size

        width = self._as_float_dimension(getattr(frame, "computed_width", 0))
        height = self._as_float_dimension(getattr(frame, "computed_height", 0))

        if width <= 0 or height <= 0:
            return self._default_page_size

        columns = max(1, int(width // GRID_COLUMN_WIDTH))
        visible_rows = max(1, int(height // GRID_ROW_HEIGHT))
        target_page_size = columns * (visible_rows + GRID_PRELOAD_EXTRA_ROWS)
        return max(MIN_PAGE_SIZE, min(MAX_PAGE_SIZE, target_page_size))

    def _reset_query_state(self):
        self.state.category_id = None
        self.state.displayed_assets = []
        self.state.current_page = 1
        self.state.total_pages = 1
        self.state.total_count = 0
        self.state.has_more = True
        self.state.selected_asset = None
        self._active_search_keyword = ""

    def _prepare_query_for_selected_category(self, category_id: str) -> None:
        """Reset paging state before loading assets for a selected category."""
        self.state.category_id = category_id
        self.state.displayed_assets = []
        self.state.current_page = 1
        self.state.has_more = True

    def _show_grid_loading_hint(self, text: str = "Loading assets...") -> None:
        if not self._grid_panel_frame:
            return
        self._grid_panel_frame.clear()
        with self._grid_panel_frame:
            ui.Label(
                text,
                style={"color": cl.green},
                alignment=ui.Alignment.CENTER,
            )

    async def _load_and_build_asset_tree(self, generation: int):
        try:
            tree_result = await load_category_tree(
                asset_type_id=self.state.asset_type_id,
                visibility_tab_id=self.state.visibility_tab_id,
                request_generation=generation,
                current_generation=self.state.generation,
            )
            if tree_result is None:
                self._update_tree_panel_with_error("Invalid asset type selection.")
                return
            if tree_result.stale:
                return

            await omni.kit.app.get_app().next_update_async()

            self._tree_panel_frame.clear()
            with self._tree_panel_frame:
                with ui.VStack():
                    category_list = tree_result.category_list
                    if len(category_list) > 0:
                        self._category_model = CategoryModel(category_list)
                        self._category_delegate = CategoryDelegate()
                        self._tree_widget = ui.TreeView(
                            self._category_model,
                            delegate=self._category_delegate,
                            root_visible=False,
                            header_visible=False,
                            height=ui.Fraction(1),
                        )
                        self._tree_widget.set_selection_changed_fn(self._on_selection_changed)
                        target_category = self._category_model._root.children[0]
                        self._tree_widget.call_selection_changed_fn([target_category])
                    else:
                        ui.Label(
                            "No categories found",
                            style={"color": cl.gray},
                            alignment=ui.Alignment.CENTER,
                        )

        except Exception as e:
            if str(e) == TOKEN_EXPIRED_MESSAGE:
                self._notify_token_expired()
            carb.log_error(f"Failed to build asset tree view: {e}")
            self._update_tree_panel_with_error(f"Failed to load assets: {str(e)}")

    def _notify_token_expired(self):
        nm.post_notification(
            "The token has expired. Please log in again. Now, you will continue browsing as a free user.",
            duration=5.0,
            status=nm.NotificationStatus.WARNING,
        )

    def _on_selection_changed(self, items: List[CategoryItem]):
        if self._tree_widget:
            self._tree_widget.selection = items

        selected_item = items[0] if len(items) > 0 else None

        if selected_item:
            category_id = selected_item.category_id
            self.state.generation += 1
            self._prepare_query_for_selected_category(category_id)
            self._show_grid_loading_hint()
            if self._search_bar:
                self._search_bar.model.set_value("")
            self._active_search_keyword = ""
            self._spawn(self._load_assets_for_context(self._build_context(page_index=1)), "load_assets_page1")
        else:
            self._reset_query_state()
            self._clear_and_build_asset_grid([], "")
            self._build_detail_panel(None, None)  # Clear detail

    def _update_tree_panel_with_error(self, error_message: str):
        """Helper to update the tree panel frame with an error message."""

        async def _async_update():
            await omni.kit.app.get_app().next_update_async()
            self._tree_panel_frame.clear()
            with self._tree_panel_frame:
                ui.Label(error_message, style={"color": cl.red})
        self._spawn(_async_update(), "tree_error_update")

    async def _load_assets_for_context(self, ctx: QueryContext):
        request_key = (ctx.generation, ctx.page_index)
        if request_key in self._loading_keys:
            return
        self._loading_keys.add(request_key)
        self._loading = True
        try:
            page = await load_asset_page(
                ctx=ctx,
                current_generation=self.state.generation,
                displayed_assets=self.state.displayed_assets,
            )
            if page is None or page.stale:
                return

            self.state.displayed_assets = page.displayed_assets
            self.state.total_pages = page.total_pages
            self.state.total_count = page.total_count
            self.state.has_more = page.has_more
            self.state.current_page = ctx.page_index
            self._build_or_update_asset_grid(
                self.state.displayed_assets,
                page.thumbnail_url,
                is_append=page.is_append,
            )
        except Exception as e:
            if str(e) == TOKEN_EXPIRED_MESSAGE:
                self._notify_token_expired()
            self._update_grid_with_error(str(e))
        finally:
            self._loading_keys.discard(request_key)
            self._loading = bool(self._loading_keys)

    async def _lazy_load_next_page_if_needed(self):
        if (
            not self._loading
            and self.state.has_more
            and self.state.current_page < self.state.total_pages
            and self.state.category_id is not None
        ):
            next_page = self.state.current_page + 1
            await self._load_assets_for_context(self._build_context(page_index=next_page))

    def _clear_and_build_asset_grid(self, asset_items: list, thumbnail_api_url: str):
        if not self._grid_panel_frame:
            carb.log_warn("Grid content frame not found.")
            return

        self._grid_panel_frame.clear()
        self._current_selected_thumb = None
        self._thumbnail_provider_refs.clear()
        self.state.selected_asset = None
        self._build_detail_panel(None, None)
        self._grid_vgrid_container = None
        self._grid_rendered_count = 0

        with self._grid_panel_frame:
            if not asset_items or len(asset_items) < 1:
                ui.Label(
                    "No assets found",
                    style={"color": cl.gray},
                    alignment=ui.Alignment.CENTER,
                )
                return

            self._grid_vgrid_container = ui.VGrid(
                column_width=GRID_COLUMN_WIDTH,
                row_height=GRID_ROW_HEIGHT,
                width=ui.Fraction(1),
            )

            self._populate_grid_items_into_container(
                self._grid_vgrid_container, asset_items, thumbnail_api_url
            )

    def _build_or_update_asset_grid(self, asset_items: list, thumbnail_api_url: str, is_append: bool = False):
        if not self._grid_panel_frame:
            carb.log_warn("Grid content frame not found.")
            return

        if not is_append or self._grid_vgrid_container is None:
            self._clear_and_build_asset_grid(asset_items, thumbnail_api_url)
            self._grid_rendered_count = len(asset_items)
            return

        if self._grid_vgrid_container and len(asset_items) > 0:
            num_existing_rendered_items = self._grid_rendered_count
            new_items_to_render = asset_items[num_existing_rendered_items:]

            if new_items_to_render:
                self._populate_grid_items_into_container(
                    self._grid_vgrid_container, new_items_to_render, thumbnail_api_url
                )
                self._grid_rendered_count = num_existing_rendered_items + len(
                    new_items_to_render
                )

    def _populate_grid_items_into_container(self, container: ui.VGrid, asset_items: list, thumbnail_api_url: str):
        populate_grid_items_into_container(
            self,
            container,
            asset_items,
            thumbnail_api_url,
            image_style_unselected=IMAGE_STYLE_UNSELECTED,
            image_style_selected=IMAGE_STYLE_SELECTED,
            image_empty_path=IMAGE_EMPTY_PATH,
            gap=self._gap,
            thumbnail_strategy=THUMBNAIL_RENDER_STRATEGY,
        )

    def _get_asset_usd_path(self, data: dict, thumbnail_url: str):
        _asset_name = data.get("Name", "Unnamed")
        _asset_type_id = self.state.asset_type_id
        _has_usd_file = data.get("IsHasUsdFile", False)

        if not _has_usd_file:
            nm.post_notification(
                f"Asset '{_asset_name}' has no USD file available.",
                duration=2.0,
                status=nm.NotificationStatus.WARNING,
            )
            return ""

        with ui.VStack(spacing=6):
            ui.Image(
                thumbnail_url,
                width=200,
                height=150,
                fill_policy=ui.FillPolicy.PRESERVE_ASPECT_FIT,
            )
            ui.Label(_asset_name, alignment=ui.Alignment.CENTER, word_wrap=True)

        if _asset_type_id == "_3dGS":
            if data and data.get("Id"):
                self._spawn(self._log_asset_load_record(data), "log_load_record_gs")
                return f"{BASE_URL1}/api/Usd/UsdzFile/{data['Id']}.usdz?t={time.time()}"
            else:
                return ""
        else:
            if data:
                _usd_path = data.get("UsdCurrentPath", None)
                if isinstance(_usd_path, list) and len(_usd_path) > 0:
                    self._spawn(self._log_asset_load_record(data), "log_load_record_asset")
                    path_part = _usd_path[0].replace("//", "/").lstrip("/")
                    return f"{BASE_URL2}/{path_part}"
                else:
                    return ""
            else:
                return ""

    async def _log_asset_load_record(self, data: dict):
        selected_asset_type = next(
            (
                item
                for item in ASSET_TYPES if item["Id"] == self.state.asset_type_id
            ),
            None,
        )
        if not selected_asset_type:
            return
        _data = {
            "RelationObjectId": data.get("Id", ""),
            "UserName": "Free Extension User",
            "ModelBusinessType": selected_asset_type.get("ModelBusinessType", ""),
        }
        await DATA_MANAGER.log_asset_load_record(_data)

    def _update_grid_with_error(self, error_message: str):
        if not self._grid_panel_frame:
            return
        self._grid_panel_frame.clear()
        with self._grid_panel_frame:
            ui.Label(
                error_message, style={"color": cl.red}, alignment=ui.Alignment.CENTER
            )
