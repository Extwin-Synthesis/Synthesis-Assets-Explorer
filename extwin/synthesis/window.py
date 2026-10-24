import asyncio
import base64
import json
import os
import time
import webbrowser
from typing import Any, Optional

import carb
import omni.kit.app
import omni.kit.notification_manager as nm
import omni.ui as ui
from omni.ui import color as cl

from .app_state import APP_STATE
from .asset_grid_runtime import populate_grid_items_into_container, release_thumbnail_providers
from .browser_engine import Browser, load_record_url
from .catalog import drag_usd_url
from .config import APP_CONFIG, ASSET_TYPES, find_asset_type
from .data_manager import DATA_MANAGER, TOKEN_EXPIRED_MESSAGE
from .login_listener import LoginListener
from .scene_runtime import load_scene
from .setting_modal import SettingModal
from .style import get_style
from .tree_models import CategoryDelegate, CategoryItem, CategoryModel
from .tree_service import load_category_tree
from .util import on_copy_to_clipboard

ASSETS_EXPLORER_NAME = "Extwin Assets"
EXT_PATH = os.path.dirname(__file__)
IMAGE_EMPTY_PATH = os.path.join(EXT_PATH, "asset", "empty.png")
GLOBAL_STYLE = get_style()
VISIBILITY_TABS = [{"Id": "Public", "Name": "Public"}, {"Id": "Private", "Name": "Private"}]
IMAGE_STYLE_UNSELECTED = {"border_width": 0, "border_radius": 4}
IMAGE_STYLE_SELECTED = {"border_width": 2, "border_radius": 4, "border_color": cl("#34c7ff")}


class SynthesisAssetsWindow(ui.Window):
    def __init__(self, visible=True):
        super().__init__(ASSETS_EXPLORER_NAME, visible=visible)
        self.frame.set_build_fn(self._build_main_view)
        self.frame.set_style(GLOBAL_STYLE)
        self._browser = Browser(page_size=60)
        self.state = self._browser.state
        self._gap = 6
        self._btn_size = 24
        self._managed_tasks: set[asyncio.Task] = set()
        self._is_cleaning_up = False
        self._login_listener = LoginListener(self._on_login)

        self._category_view_frame: Optional[ui.Frame] = None
        self._tree_panel_frame: Optional[ui.ScrollingFrame] = None
        self._grid_panel_frame: Optional[ui.ScrollingFrame] = None
        self._detail_panel_frame: Optional[ui.Frame] = None
        self._tree_widget: Optional[ui.TreeView] = None
        self._grid_vgrid_container: Optional[ui.VGrid] = None
        self._current_selected_thumb = None
        self._thumbnail_provider_refs: dict[int, Any] = {}
        self._detail_provider = None
        self._grid_rendered_count = 0
        self._search_bar = None

        self.deferred_dock_in("Console", active_window=ui.DockPolicy.CURRENT_WINDOW_IS_ACTIVE)
        self._spawn(self._login_listener.start(), "start_login_listener")

    def _spawn(self, coro, name: str) -> asyncio.Task:
        task = asyncio.ensure_future(coro)
        self._managed_tasks.add(task)

        def _done(done_task: asyncio.Task):
            self._managed_tasks.discard(done_task)
            if done_task.cancelled():
                return
            exc = done_task.exception()
            if exc:
                carb.log_error(f"[{name}] {exc}")

        task.add_done_callback(_done)
        return task

    def _cancel_all_tasks(self):
        for task in list(self._managed_tasks):
            if not task.done():
                task.cancel()
        self._managed_tasks.clear()

    def _on_login(self, token: str, user_info: dict):
        if not APP_STATE.apply_login(token, user_info):
            nm.post_notification(
                "Invalid auth info format.",
                duration=2.0,
                status=nm.NotificationStatus.WARNING,
            )
            return
        self.state.visibility_tab_id = VISIBILITY_TABS[0]["Id"]
        self.state.generation += 1
        self._browser.reset_query()
        self._spawn(self._delayed_rebuild_main_view(), "rebuild_after_login")
        nm.post_notification(
            "Auth info updated successfully.",
            duration=2.0,
            status=nm.NotificationStatus.INFO,
        )

    def _release_grid_providers(self):
        release_thumbnail_providers(self._thumbnail_provider_refs)
        self._current_selected_thumb = None

    def _release_detail_provider(self):
        self._detail_provider = None

    def _rebuild_main_view(self):
        self.frame.clear()
        self._release_grid_providers()
        self._release_detail_provider()
        self._grid_vgrid_container = None
        self._grid_rendered_count = 0
        self._build_main_view()

    def _on_asset_type_click(self, asset_type):
        self._browser.switch_asset_type(asset_type.id)
        self._spawn(self._delayed_rebuild_main_view(), "rebuild_main")

    async def _delayed_rebuild_main_view(self):
        await omni.kit.app.get_app().next_update_async()
        self._rebuild_main_view()

    def _rebuild_tab_view(self):
        if self._category_view_frame:
            self._category_view_frame.clear()
        self._release_grid_providers()
        self._release_detail_provider()
        self._grid_vgrid_container = None
        self._grid_rendered_count = 0
        self._build_category_view()

    def _on_visibility_tab_click(self, tab: dict[str, str]):
        self._browser.switch_visibility(tab["Id"])
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
        self._release_grid_providers()
        self._release_detail_provider()

        async def _cleanup():
            try:
                await self._login_listener.stop()
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
                            selected = asset_type_item.id == self.state.asset_type_id
                            ui.Button(
                                asset_type_item.name,
                                height=self._btn_size,
                                selected=selected,
                                checked=selected,
                                clicked_fn=lambda a_type=asset_type_item: self._on_asset_type_click(a_type),
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
        asset = find_asset_type(self.state.asset_type_id)
        selected = self.state.selected_asset or {}
        if asset is None:
            carb.log_error("Invalid asset type selection.")
            return
        final_url_to_open = (
            f"{APP_CONFIG.web_server}/#/home?id={selected.get('Id', '')}&t={asset.type_in_browser}"
        )
        webbrowser.open(final_url_to_open)

    def _handle_setting(self):
        carb.log_info("Settings button clicked.")
        field_defs = [
            SettingModal.FieldDef("usd_server", "Server", ui.StringField, APP_CONFIG.usd_server),
            SettingModal.FieldDef("auth_info", "Auth Info", ui.StringField, ""),
        ]

        def _handle_form_submit(dialog: SettingModal):
            values = dialog.get_values()
            new_usd_server = values.get("usd_server", APP_CONFIG.usd_server).strip()
            if not new_usd_server:
                nm.post_notification(
                    "Server can not be empty",
                    duration=2.0,
                    status=nm.NotificationStatus.WARNING,
                )
                return
            if new_usd_server != APP_CONFIG.usd_server:
                APP_CONFIG.usd_server = new_usd_server
                msg = f"Server updated to: {new_usd_server}"
                carb.log_info(msg)
                nm.post_notification(msg, duration=2.0, status=nm.NotificationStatus.INFO)
            else:
                nm.post_notification(
                    "Server unchanged",
                    duration=2.0,
                    status=nm.NotificationStatus.INFO,
                )

            auth_info = values.get("auth_info", "").strip()
            if auth_info:
                try:
                    decoded = base64.b64decode(auth_info).decode("utf-8")
                    auth_data = json.loads(decoded)
                except (json.JSONDecodeError, UnicodeDecodeError, ValueError):
                    nm.post_notification(
                        "Failed to parse auth info.",
                        duration=2.0,
                        status=nm.NotificationStatus.WARNING,
                    )
                else:
                    token = auth_data.get("Token")
                    login_user_info = auth_data.get("LoginUserInfo", None)
                    if APP_STATE.apply_login(token, login_user_info):
                        self.state.visibility_tab_id = VISIBILITY_TABS[0]["Id"]
                        self.state.generation += 1
                        self._browser.reset_query()
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

            async def _close_dialog():
                await omni.kit.app.get_app().next_update_async()
                dialog.destroy()

            self._spawn(_close_dialog(), "close_setting_dialog")

        dialog = SettingModal(
            width=400,
            title="Settings",
            field_defs=field_defs,
            ok_handler=lambda dialog: _handle_form_submit(dialog),
        )
        dialog.window.height = 0
        dialog.show()

    def _build_category_header(self):
        with ui.HStack(spacing=self._gap, height=0):
            if APP_STATE.is_logged_in and not APP_STATE.is_system_admin:
                for tab_item in VISIBILITY_TABS:
                    checked = tab_item.get("Id") == self.state.visibility_tab_id
                    ui.Button(
                        tab_item.get("Name"),
                        width=ui.Length(120),
                        height=self._btn_size,
                        checked=checked,
                        selected=checked,
                        clicked_fn=lambda tab=tab_item: self._on_visibility_tab_click(tab),
                    )

            ui.Spacer()
            ui.Button(
                "Setting",
                width=80,
                height=self._btn_size,
                clicked_fn=self._handle_setting,
            )

    def _build_category_toolbar(self):
        with ui.HStack(spacing=4, height=24):
            self._btn_toggle_tree = ui.Button(text="Toggle Tree", width=ui.Length(100))
            self._search_bar = ui.StringField(
                style={"background_color": cl("#333333")},
                width=ui.Fraction(1),
            )
            ui.Button(
                "Search",
                width=80,
                height=self._btn_size,
                clicked_fn=self._submit_search,
            )
            self._btn_toggle_detail = ui.Button(text="Toggle Detail", width=ui.Length(100))

            self._btn_toggle_tree.set_mouse_pressed_fn(
                lambda a, b, c, d: setattr(
                    self._tree_panel_frame, "visible", not self._tree_panel_frame.visible
                )
            )

            def _toggle_detail():
                if self._detail_panel_frame:
                    self._detail_panel_frame.visible = not self._detail_panel_frame.visible

            self._btn_toggle_detail.set_mouse_pressed_fn(lambda a, b, c, d: _toggle_detail())
            self._search_bar.set_key_pressed_fn(self._on_search_key_pressed)

    def _set_search_text(self, text: str):
        if not self._search_bar:
            return
        self._search_bar.model.set_value(text)

    def _on_search_key_pressed(self, key: int, modifiers: int, is_down: bool):
        if not is_down:
            return
        if key not in (
            int(carb.input.KeyboardInput.ENTER),
            int(carb.input.KeyboardInput.NUMPAD_ENTER),
        ):
            return
        self._submit_search()

    def _submit_search(self):
        if not self._search_bar:
            return
        keyword = self._search_bar.model.get_value_as_string().strip()
        carb.log_info(f"Search submitted: '{keyword}'")
        if not self._browser.begin_search(keyword):
            carb.log_info("Search triggered, but no category is currently selected.")
            return
        self._show_grid_loading_hint()
        self._spawn(
            self._load_assets_for_context(self._browser.context(page_index=1)),
            "search",
        )

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
                self._detail_panel_frame = ui.Frame(width=ui.Length(400))
                self._build_detail_panel(None, None)

    def _set_lazy_load_callback(self, scrolling_frame: ui.ScrollingFrame):
        def on_scrolling(scroll_pos_y):
            if self._browser.loading or not self.state.has_more or not self._grid_panel_frame:
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

    def _place_detail_image(self, img_url: str):
        if img_url and img_url != IMAGE_EMPTY_PATH:
            provider = ui.RasterImageProvider(img_url)
            try:
                provider.max_mip_levels = 1
            except Exception:
                pass
            self._detail_provider = provider
            image = ui.ImageWithProvider(
                provider,
                height=300,
                style={"border_radius": 4},
            )
            try:
                image.fill_policy = ui.FillPolicy.PRESERVE_ASPECT_FIT
            except Exception:
                pass
            return
        ui.Image(
            img_url or IMAGE_EMPTY_PATH,
            height=300,
            fill_policy=ui.FillPolicy.PRESERVE_ASPECT_FIT,
            style={"border_radius": 4},
        )

    def _build_detail_panel(self, asset_data: Optional[dict[str, Any]], img_url):
        if not self._detail_panel_frame:
            return

        self._detail_panel_frame.clear()
        self._release_detail_provider()

        with self._detail_panel_frame:
            if asset_data:
                asset_type_id = self.state.asset_type_id
                with ui.HStack(height=ui.Fraction(1)):
                    ui.Spacer(width=14)
                    with ui.VStack(spacing=0, height=ui.Fraction(1), style={"color": cl("#ffffffff")}):
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
                                clicked_fn=lambda: self._on_copy_name_to_clipboard(asset_data.get("Name")),
                            )
                            if asset_type_id == "SimReady" or asset_type_id == "Robot":
                                with ui.HStack(height=24, spacing=0):
                                    ui.Label("Articulated:", width=0, height=24)
                                    checkbox = ui.CheckBox(
                                        style={"color": cl.green, "margin": 6},
                                        enabled=False,
                                    )
                                    checkbox.model.set_value(asset_data.get("IsHasArticulus", False))

                        self._place_detail_image(img_url)
                        ui.Label(
                            asset_data.get("Name", "Unnamed"),
                            alignment=ui.Alignment.CENTER,
                            word_wrap=True,
                            height=0,
                        )
                        ui.Spacer(height=6)

                        with ui.ScrollingFrame(
                            height=ui.Fraction(1),
                            horizontal_scrollbar_policy=ui.ScrollBarPolicy.SCROLLBAR_ALWAYS_OFF,
                            vertical_scrollbar_policy=ui.ScrollBarPolicy.SCROLLBAR_AS_NEEDED,
                        ):
                            with ui.CollapsableFrame("Asset Info"):
                                with ui.VStack(spacing=12):
                                    if asset_type_id != "Scene":
                                        with ui.VStack(spacing=6):
                                            ui.Label("Description:", height=0)
                                            ui.Label(
                                                asset_data.get("Comment") or "",
                                                alignment=ui.Alignment.LEFT_TOP,
                                                word_wrap=True,
                                                height=0,
                                            )
            else:
                ui.Label(
                    "Select an asset to view details.",
                    alignment=ui.Alignment.CENTER,
                )

    def _load_scene(self):
        load_scene(self)

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

    def _on_selection_changed(self, items: list[CategoryItem]):
        if self._tree_widget:
            self._tree_widget.selection = items

        selected_item = items[0] if len(items) > 0 else None
        if selected_item and selected_item.category_id:
            self._browser.select_category(selected_item.category_id)
            self._show_grid_loading_hint()
            self._build_detail_panel(None, None)
            self._set_search_text("")
            self._spawn(
                self._load_assets_for_context(self._browser.context(page_index=1)),
                "load_assets_page1",
            )
        else:
            self._browser.reset_query()
            self._clear_and_build_asset_grid([], "")
            self._build_detail_panel(None, None)

    def _update_tree_panel_with_error(self, error_message: str):
        async def _async_update():
            await omni.kit.app.get_app().next_update_async()
            self._tree_panel_frame.clear()
            with self._tree_panel_frame:
                ui.Label(error_message, style={"color": cl.red})

        self._spawn(_async_update(), "tree_error_update")

    async def _load_assets_for_context(self, ctx):
        try:
            page = await self._browser.load(ctx)
            if page is None or page.stale:
                return
            self._build_or_update_asset_grid(
                page.displayed_assets,
                page.thumbnail_url,
                is_append=page.is_append,
            )
        except Exception as e:
            if str(e) == TOKEN_EXPIRED_MESSAGE:
                self._notify_token_expired()
            self._update_grid_with_error(str(e))

    async def _lazy_load_next_page_if_needed(self):
        if (
            not self._browser.loading
            and self.state.has_more
            and self.state.current_page < self.state.total_pages
            and self.state.category_id is not None
        ):
            next_page = self.state.current_page + 1
            notice = nm.post_notification(
                "Loading more...",
                hide_after_timeout=False,
                status=nm.NotificationStatus.INFO,
            )
            try:
                await self._load_assets_for_context(
                    self._browser.context(next_page, keyword=self.state.keyword)
                )
            finally:
                if notice:
                    notice.destroy()

    def _show_grid_loading_hint(self, text: str = "Loading assets...") -> None:
        if not self._grid_panel_frame:
            return
        self._grid_panel_frame.clear()
        self._release_grid_providers()
        self._grid_vgrid_container = None
        self._grid_rendered_count = 0
        with self._grid_panel_frame:
            ui.Label(
                text,
                style={"color": cl.green},
                alignment=ui.Alignment.CENTER,
            )

    def _clear_and_build_asset_grid(self, asset_items: list, thumbnail_api_url: str):
        if not self._grid_panel_frame:
            carb.log_warn("Grid content frame not found.")
            return

        self._grid_panel_frame.clear()
        self._release_grid_providers()
        self.state.selected_asset = None
        self._build_detail_panel(None, None)
        self._grid_vgrid_container = None
        self._grid_rendered_count = 0

        with self._grid_panel_frame:
            if not asset_items:
                ui.Label(
                    "No assets found",
                    style={"color": cl.gray},
                    alignment=ui.Alignment.CENTER,
                )
                return

            self._grid_vgrid_container = ui.VGrid(
                column_width=210,
                row_height=180,
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
            new_items_to_render = asset_items[self._grid_rendered_count :]
            if new_items_to_render:
                self._populate_grid_items_into_container(
                    self._grid_vgrid_container, new_items_to_render, thumbnail_api_url
                )
                self._grid_rendered_count += len(new_items_to_render)

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
        )

    def _get_asset_usd_path(self, data: dict, preview_provider=None):
        asset_name = data.get("Name", "Unnamed")
        if not data.get("IsHasUsdFile", False):
            nm.post_notification(
                f"Asset '{asset_name}' has no USD file available.",
                duration=2.0,
                status=nm.NotificationStatus.WARNING,
            )
            return ""

        with ui.VStack(spacing=6):
            if preview_provider is not None:
                image = ui.ImageWithProvider(
                    preview_provider,
                    width=ui.Length(200),
                    height=ui.Length(150),
                )
                try:
                    image.fill_policy = ui.FillPolicy.PRESERVE_ASPECT_FIT
                except Exception:
                    pass
            else:
                ui.Image(
                    IMAGE_EMPTY_PATH,
                    width=200,
                    height=150,
                    fill_policy=ui.FillPolicy.PRESERVE_ASPECT_FIT,
                )
            ui.Label(asset_name, alignment=ui.Alignment.CENTER, word_wrap=True)

        usd_url = drag_usd_url(self.state.asset_type_id, data, time.time())
        if usd_url:
            self._spawn(self._log_asset_load_record(data), "log_load_record")
        return usd_url

    async def _log_asset_load_record(self, data: dict):
        asset = find_asset_type(self.state.asset_type_id)
        if asset is None:
            return
        await DATA_MANAGER.post_json(
            load_record_url(),
            {
                "RelationObjectId": data.get("Id", ""),
                "UserName": "Free Extension User",
                "ModelBusinessType": asset.model_business_type,
            },
        )

    def _update_grid_with_error(self, error_message: str):
        if not self._grid_panel_frame:
            return
        self._grid_panel_frame.clear()
        self._release_grid_providers()
        self._grid_vgrid_container = None
        self._grid_rendered_count = 0
        with self._grid_panel_frame:
            ui.Label(error_message, style={"color": cl.red}, alignment=ui.Alignment.CENTER)
