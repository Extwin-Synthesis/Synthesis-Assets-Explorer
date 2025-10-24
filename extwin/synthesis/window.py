import asyncio
import time
import carb
from omni.ui import color as cl
from typing import List, Optional, Dict, Any
import omni.ui as ui
import omni.kit.app
from .app_state import APP_STATE
from .data_manager import DATA_MANAGER
from .aes import encrypt_aes
from .style import get_style
import os
import json
import omni.kit.notification_manager as nm
import omni.usd
from pxr import Sdf
import omni.kit.window.file
from .setting_modal import SettingModal
from omni.kit.window.popup_dialog import MessageDialog
from .util import on_copy_to_clipboard

# from .loading_fullscreen import FullScreenLoading

# --- Constants and Configuration ---
EXT_PATH = os.path.dirname(__file__)
GLOBAL_STYLE = get_style()

ASSETS_EXPLORER_NAME = "Extwin Assets"
BASE_URL1 = "https://synthesis-server.extwin.com"
BASE_URL2 = "https://multiverse-server.vothing.com"
BASE_URL3 = "https://synthesis.extwin.com"

# Asset type definitions for browsing
ASSET_TYPES: list = [
    {
        "Id": "SimReady",
        "Name": "Sim Ready",
        "CategoryListUrl": f"{BASE_URL1}/api/SimReady/GetCategoryList",
        "CategoryItemContentUrl": f"{BASE_URL1}/api/SimReady/GetSimReadyList",
        "CategoryListUrlFree": f"{BASE_URL1}/api/Global/GetCategoryList",
        "CategoryItemContentUrlFree": f"{BASE_URL1}/api/Global/GetSimReadyList",
        "ThumbnailUrl": f"{BASE_URL1}/api/Usd/SimReady/Image",
        "TypeInBrowser": "assets-simready",
        "ModelBusinessType": 1,
    },
    {
        "Id": "Model",
        "Name": "Model",
        "CategoryListUrl": f"{BASE_URL1}/api/Model/GetCategoryList",
        "CategoryItemContentUrl": f"{BASE_URL1}/api/Model/GetModelList",
        "CategoryListUrlFree": f"{BASE_URL1}/api/Global/GetModelCategoryList",
        "CategoryItemContentUrlFree": f"{BASE_URL1}/api/Global/GetModelList",
        "ThumbnailUrl": f"{BASE_URL1}/api/Usd/Model/Image",
        "TypeInBrowser": "assets-model",
        "ModelBusinessType": 2,
    },
    {
        "Id": "_3dGS",
        "Name": "3D Gauss Splatting",
        "CategoryListUrl": f"{BASE_URL1}/api/Gs/GetCategoryList",
        "CategoryItemContentUrl": f"{BASE_URL1}/api/Gs/GetGsList",
        "CategoryListUrlFree": f"{BASE_URL1}/api/Global/GetGsCategoryList",
        "CategoryItemContentUrlFree": f"{BASE_URL1}/api/Global/GetGsList",
        "ThumbnailUrl": f"{BASE_URL1}/api/Usd/Gs/Image",
        "TypeInBrowser": "assets-gs",
        "ModelBusinessType": 3,
    },
    {
        "Id": "Robot",
        "Name": "Robot",
        "CategoryListUrl": f"{BASE_URL1}/api/Noumen/GetCategoryList",
        "CategoryItemContentUrl": f"{BASE_URL1}/api/Robot/GetRobotList",
        "CategoryListUrlFree": f"{BASE_URL1}/api/Global/GetRobotCategoryList",
        "CategoryItemContentUrlFree": f"{BASE_URL1}/api/Global/GetRobotList",
        "ThumbnailUrl": f"{BASE_URL1}/api/Usd/Robot/Image",
        "TypeInBrowser": "assets-ontology",
        "ModelBusinessType": 5,
    },
    {
        "Id": "Scene",
        "Name": "Scene",
        "CategoryListUrl": f"{BASE_URL1}/api/Scene/GetCategoryList",
        "CategoryItemContentUrl": f"{BASE_URL1}/api/Scene/GetSceneList",
        "CategoryListUrlFree": f"{BASE_URL1}/api/Global/GetSceneCategoryList",
        "CategoryItemContentUrlFree": f"{BASE_URL1}/api/Global/GetSceneList",
        "ThumbnailUrl": f"{BASE_URL1}/api/Usd/Scene/Image",
        "TypeInBrowser": "assets-scene",
        "ModelBusinessType": 6,
    },
]

LOGIN_URL = f"{BASE_URL1}/api/User/Login"

VISIBILITY_TABS: list = [
    {"Id": "Public", "Name": "Public"},
    {"Id": "Private", "Name": "Private"},
]

# --- UI Styling Constants ---
SEPARATOR_COLOR = cl("#4e5152")
SEPARATOR_SIZE = 4
LEFT_SIDEBAR_WIDTH = 150
CATEGORY_TREE_DEFAULT_WIDTH = 240
CATEGORY_TREE_MIN_WIDTH = 200
CATEGORY_TREE_MAX_WIDTH = 800

ASSET_DETAIL_MIN_WIDTH = 400
ASSET_DETAIL_MAX_WIDTH = 500

IMAGE_STYLE_UNSELECTED = {
    "border_width": 0,
    "border_radius": 4,
}
IMAGE_STYLE_SELECTED = {
    "border_width": 2,
    "border_radius": 4,
    "border_color": cl("#34c7ff"),
}

IMAGE_EMPTY_PATH = os.path.join(EXT_PATH, "asset", "empty.png")


# --- Data Models ---
class CategoryItem(ui.AbstractItem):
    """
    Represents a category in the asset browser tree view.
    """

    def __init__(self, data: dict, parent: Optional["CategoryItem"] = None):
        super().__init__()
        self.data = data
        self.parent = parent
        self.children: List[CategoryItem] = []
        self._value_models = [
            ui.SimpleStringModel(self.data.get("CategoryName", "Unnamed"))
        ]

    def __repr__(self):
        return f"CategoryItem({self.data.get('CategoryName')})"

    @property
    def category_id(self) -> Optional[str]:
        return self.data.get("CategoryId")

    @property
    def name(self) -> str:
        return self.data.get("CategoryName", "Unnamed")


class CategoryModel(ui.AbstractItemModel):
    """
    Model for the category tree view, managing the hierarchical structure.
    """

    def __init__(self, category_list: list):
        super().__init__()
        self._root = CategoryItem(
            {"CategoryName": "root", "CategoryId": "root"}, parent=None
        )
        self._build_tree(self._root, category_list)

    def _build_tree(self, parent_item: CategoryItem, items: list):
        """Recursively builds the tree from flat API data."""
        for item_data in items:
            child_item = CategoryItem(item_data, parent=parent_item)
            parent_item.children.append(child_item)
            sub_items = item_data.get("CategoryLists", [])
            if sub_items:
                self._build_tree(child_item, sub_items)

    def get_item_children(
        self, item: Optional[CategoryItem] = None
    ) -> List[CategoryItem]:
        """Gets children of an item (or root if None)."""
        if item is None:
            return self._root.children
        return item.children

    def get_item_value_model_count(self, item: CategoryItem) -> int:
        """Returns the number of value models for an item."""
        # This check `if self:` seems incorrect but was in original code.
        # It likely always evaluates to True. Keeping it for compatibility.
        if self:
            return 1
        return 0

    def get_item_value_model(self, item: CategoryItem, column_id: int):
        """Gets the value model for an item's column."""
        if column_id == 0:
            return item._value_models[0]
        return None


class CategoryDelegate(ui.AbstractItemDelegate):
    """
    Delegate for rendering category items in the tree view.
    Defines how branches and labels are drawn.
    """

    def __init__(self):
        super().__init__()

    def build_branch(
        self,
        model: CategoryModel,
        item: CategoryItem,
        column_id: int,
        level: int,
        expanded: bool,
    ):
        """Builds the expand/collapse icons for tree branches."""
        _line_color = cl("#5b5b5b")
        _node_height = 32
        _node_icon_width = 16
        _node_root_size = 6
        _node_root_icon_offset_y = (_node_height - _node_root_size) * 0.5
        _node_root_icon_offset_x = (_node_icon_width - _node_root_size) * 0.5

        if column_id == 0:
            with ui.HStack(height=_node_height):
                ui.Spacer(width=_node_icon_width * 0.5)
                _has_children = bool(model.get_item_children(item))
                if level == 0:
                    if _has_children:
                        icon = "minus.png" if expanded else "plus.png"
                        ui.Image(
                            os.path.join(EXT_PATH, "asset", icon),
                            fill_policy=ui.FillPolicy.PRESERVE_ASPECT_FIT,
                            alignment=ui.Alignment.LEFT_CENTER,
                            width=_node_icon_width,
                        )
                        ui.Spacer(width=_node_icon_width * 0.5)
                    else:
                        if not item.category_id:
                            pass
                        else:
                            if item.category_id != "All":
                                with ui.Placer(
                                    width=_node_icon_width,
                                    draggable=False,
                                    offset_x=_node_root_icon_offset_x,
                                    offset_y=_node_root_icon_offset_y,
                                ):
                                    ui.Rectangle(
                                        width=_node_root_size,
                                        height=_node_root_size,
                                        style={"background_color": cl("#ffffff")},
                                    )
                                ui.Spacer(width=_node_icon_width * 0.5)
                else:
                    for i in range(level):
                        if i == 0:
                            ui.Spacer(width=_node_icon_width * 0.5)
                        else:
                            ui.Spacer(width=_node_icon_width)
                        ui.Line(
                            height=ui.Percent(100),
                            alignment=ui.Alignment.LEFT,
                            style={"color": _line_color, "border_width": 1},
                        )

                    if _has_children:
                        ui.Spacer(width=_node_icon_width * 0.5)
                        icon = "minus.png" if expanded else "plus.png"
                        ui.Image(
                            os.path.join(EXT_PATH, "asset", icon),
                            fill_policy=ui.FillPolicy.PRESERVE_ASPECT_FIT,
                            alignment=ui.Alignment.LEFT_CENTER,
                            width=_node_icon_width,
                        )
                        ui.Spacer(width=_node_icon_width * 0.5)
                    else:
                        ui.Line(
                            width=_node_icon_width * 1.5,
                            alignment=ui.Alignment.V_CENTER,
                            style={"color": _line_color},
                        )
                        ui.Spacer(width=_node_icon_width * 0.5)

    def build_widget(
        self,
        model: CategoryModel,
        item: CategoryItem,
        column_id: int,
        level: int,
        expanded: bool,
    ):
        """Builds the text/content widget for a tree item."""
        if column_id == 0:
            hstack = ui.HStack(spacing=0)
            with hstack:
                ui.Label(
                    item.name,
                    alignment=ui.Alignment.LEFT_CENTER,
                    style_type_name_override="LabelInTreeView",
                )

    def build_header(self, column_id=0):
        super().build_header(column_id)
        return ui.Label("The Header")


# --- Main Window Class ---
class SynthesisAssetsWindow(ui.Window):
    """
    The main window for browsing Synthesis assets.
    Manages UI layout, user interactions, data loading, and state.
    """

    def __init__(self, visible=True):
        super().__init__(ASSETS_EXPLORER_NAME, visible=visible)
        self.frame.set_build_fn(self._build_ui)
        self.frame.set_style(GLOBAL_STYLE)

        self._gap = 6
        self._btn_size = 24
        self._login_widgets = {}

        # State
        self._asset_type_id_selected = ASSET_TYPES[0].get("Id")
        self._selected_visibility_tab_id = VISIBILITY_TABS[0].get("Id")
        self._is_system_admin = False
        self._asset_data_selected: Optional[Dict[str, Any]] = None

        # UI Frames and Components
        self._category_view_frame: Optional[ui.Frame] = None
        self._category_model: Optional[CategoryModel] = None
        self._category_delegate: Optional[CategoryDelegate] = None
        self._tree_widget: Optional[ui.TreeView] = None

        # Splitter components
        self._splitter_frame: Optional[ui.Frame] = None
        self._splitter_placer: Optional[ui.Placer] = None
        self._splitter_rect: Optional[ui.Rectangle] = None

        self._detail_splitter_frame: Optional[ui.Frame] = None
        self._detail_splitter_placer: Optional[ui.Placer] = (
            None  # Not used in current UI
        )
        self._detail_splitter_rect: Optional[ui.Rectangle] = (
            None  # Not used in current UI
        )

        self._tree_panel_frame: Optional[ui.ScrollingFrame] = None
        self._grid_panel_frame: Optional[ui.ScrollingFrame] = None
        self._grid_vgrid_container: Optional[ui.VGrid] = (
            None  # Container for dynamic content
        )
        self._detail_panel_frame: Optional[ui.Frame] = None
        self._tree_panel_initial_width = CATEGORY_TREE_DEFAULT_WIDTH

        # Asset Grid State - Enhanced for lazy loading
        self._asset_category_id_selected = None
        self._all_loaded_asset_items: List[Dict[str, Any]] = (
            []
        )  # Store all loaded items locally
        self._displayed_asset_items: List[Dict[str, Any]] = (
            []
        )  # Items currently displayed after filtering/search
        self._currently_selected_image_widget: Optional[ui.Image] = None

        # Lazy Loading State
        self._page_size = 60  # Number of items per page
        self._current_page_index = 1
        self._total_count_from_api = 0
        self._total_pages_from_api = 1  # Will be updated from API response
        self._is_loading_more = False  # Flag to prevent multiple simultaneous loads
        self._no_more_assets_to_load = (
            False  # Flag based on API total count or last page results
        )
        self._loading_indicator_label: Optional[ui.Label] = (
            None  # Reference to loading label in grid
        )

        # Drag states for splitters
        self._drag_start_tree_width = 0.0
        self._drag_start_x = 0.0
        self._drag_start_detail_width = 0.0  # Not used in current UI
        self._drag_start_detail_x = 0.0  # Not used in current UI

        self._grid_rendered_count = (
            0  # Track how many items are currently rendered in the grid
        )

        # Search Debounce
        self._search_timer_handle: Optional[asyncio.Handle] = None
        self._debounce_delay = 0.3  # seconds

        # Dock the window
        self.deferred_dock_in(
            "Console", active_window=ui.DockPolicy.CURRENT_WINDOW_IS_ACTIVE
        )

        # self._loading = FullScreenLoading()

    # --- UI Rebuilding Utilities ---
    def _rebuild_main_view(self):
        """Clears and rebuilds the main browsing interface."""
        self.frame.clear()
        self._build_ui()

    def _on_asset_type_click(self, asset_type: Dict[str, Any]):
        """Handles click on an asset type button."""
        self._asset_type_id_selected = asset_type.get("Id")
        self._asset_category_id_selected = None
        self._reset_pagination_state(True)
        asyncio.ensure_future(self._delayed_rebuild_main_view())

    async def _delayed_rebuild_main_view(self):
        """Delays UI rebuild to the next frame."""
        await omni.kit.app.get_app().next_update_async()
        self._rebuild_main_view()

    def _rebuild_tab_view(self):
        """Clears and rebuilds the tab view section."""
        if self._category_view_frame:
            self._category_view_frame.clear()
        self._build_category_view()

    def _on_visibility_tab_click(self, tab: Dict[str, str]):
        """Handles click on a visibility tab."""
        self._selected_visibility_tab_id = tab.get("Id")
        asyncio.ensure_future(self._delayed_rebuild_tab_view())

    async def _delayed_rebuild_tab_view(self):
        """Delays tab view rebuild to the next frame."""
        await omni.kit.app.get_app().next_update_async()
        self._rebuild_tab_view()

    def destroy(self):
        """Cleans up resources on window destruction."""
        self.clean_up()
        super().destroy()

    def clean_up(self):
        """Performs async cleanup, e.g., closing network connections."""
        # Cancel any pending search timer
        if self._search_timer_handle:
            self._search_timer_handle.cancel()
        asyncio.ensure_future(DATA_MANAGER.close())

    # --- Root UI Building ---
    def _build_ui(self):
        # """Builds the root UI: login or main view."""
        # if APP_STATE.is_logged_in:
        #     self._build_main_view()
        # else:
        #     self._build_login_view()
        self._build_main_view()

    # --- Main Browsing Interface ---
    def _build_main_view(self):
        """Builds the main asset browsing interface."""
        with self.frame:
            with ui.HStack(spacing=0):
                with ui.ScrollingFrame(
                    width=ui.Length(LEFT_SIDEBAR_WIDTH),
                    horizontal_scrollbar_policy=ui.ScrollBarPolicy.SCROLLBAR_ALWAYS_OFF,
                    vertical_scrollbar_policy=ui.ScrollBarPolicy.SCROLLBAR_AS_NEEDED,
                ):
                    with ui.VStack(spacing=self._gap):
                        for asset_type_item in ASSET_TYPES:
                            ui.Button(
                                asset_type_item.get("Name"),
                                height=self._btn_size,
                                selected=asset_type_item.get("Id")
                                == self._asset_type_id_selected,
                                checked=asset_type_item.get("Id")
                                == self._asset_type_id_selected,
                                clicked_fn=lambda a_type=asset_type_item: self._on_asset_type_click(
                                    a_type
                                ),
                            )

                ui.Line(
                    alignment=ui.Alignment.H_CENTER,
                    width=ui.Length(SEPARATOR_SIZE),
                    style={"color": SEPARATOR_COLOR, "border_width": SEPARATOR_SIZE},
                )
                ui.Spacer(width=ui.Length(18))

                self._category_view_frame = ui.Frame()
                self._build_category_view()

    # --- Login Interface ---
    def _build_login_view(self):
        """Builds the login interface."""
        _label_width = 100
        with self.frame:
            with ui.VStack(spacing=self._gap * 2):
                ui.Label(
                    "Login to Synthesis",
                    alignment=ui.Alignment.CENTER,
                    height=ui.Length(80),
                    style={"font_size": 32},
                )

                with ui.HStack(height=24):
                    ui.Label("Account", width=_label_width)
                    _account_field = ui.StringField()
                self._login_widgets["username"] = _account_field

                with ui.HStack(height=24):
                    ui.Label("Password", width=_label_width)
                    _pwd_field = ui.StringField()
                    _pwd_field.password_mode = True
                self._login_widgets["password"] = _pwd_field

                with ui.HStack(height=ui.Length(0)):
                    ui.Label("Remember Me", width=_label_width)
                    _remberme_field = ui.CheckBox(name="greenCheck")
                self._login_widgets["remember_me"] = _remberme_field

                if APP_STATE.username:
                    _account_field.model.set_value(APP_STATE.username)
                if APP_STATE.remember_me:
                    _remberme_field.model.set_value(True)
                    if APP_STATE.password:
                        _pwd_field.model.set_value(APP_STATE.password)

                with ui.HStack(height=24):
                    ui.Spacer(width=_label_width)
                    ui.Button(
                        "Login",
                        width=80,
                        clicked_fn=self._handle_login,
                        tooltip="Click to login",
                    )
                    ui.Spacer(width=self._gap)
                    self._login_widgets["status_label"] = ui.Label(
                        "", style={"color": cl.red}
                    )

    def _handle_login(self):
        """Handles the login button click event."""
        username_model = self._login_widgets["username"].model
        password_model = self._login_widgets["password"].model
        remember_me_model = self._login_widgets["remember_me"].model

        username = username_model.get_value_as_string().strip()
        password = password_model.get_value_as_string()
        remember_me = remember_me_model.get_value_as_bool()

        if not username or not password:
            self._login_widgets["status_label"].text = (
                "Account and password are required."
            )
            return

        self._login_widgets["status_label"].style = {"color": cl.green}
        self._login_widgets["status_label"].text = "Logging in..."
        asyncio.ensure_future(self._login_task(username, password, remember_me))

    async def _login_task(self, username: str, password: str, remember_me: bool):
        """Performs the asynchronous login request."""
        try:
            response = await DATA_MANAGER.login(
                LOGIN_URL, username, encrypt_aes(password)
            )

            if response:
                token = response.get("Token")
                login_user_info = response.get("LoginUserInfo", {})

                if token:
                    APP_STATE.save_credentials(username, password, remember_me)
                    APP_STATE.login(token, username, login_user_info)

                    user_type = login_user_info.get("UserType", 5)
                    self._is_system_admin = user_type <= 2

                    asyncio.ensure_future(self._delayed_login_rebuild())
                else:
                    self._login_widgets["status_label"].style = {"color": cl.red}
                    self._login_widgets["status_label"].text = (
                        "Login failed: No token in response."
                    )
            else:
                msg = response.get("MessageCode", "Unknown login error")
                self._login_widgets["status_label"].style = {"color": cl.red}
                self._login_widgets["status_label"].text = f"Login failed: {msg}"

        except ConnectionError as e:
            self._login_widgets["status_label"].style = {"color": cl.red}
            self._login_widgets["status_label"].text = f"Connection error: {str(e)}"
            carb.log_error(f"Login connection error: {e}")
        except ValueError as e:
            self._login_widgets["status_label"].style = {"color": cl.red}
            self._login_widgets["status_label"].text = f"Server error: {str(e)}"
            carb.log_error(f"Login server error: {e}")
        except Exception as e:
            self._login_widgets["status_label"].style = {"color": cl.red}
            self._login_widgets["status_label"].text = f"Error: {str(e)}"
            carb.log_error(f"Login exception: {e}")

    async def _delayed_login_rebuild(self):
        """Rebuilds UI after successful login."""
        await omni.kit.app.get_app().next_update_async()
        self._login_widgets.clear()
        self.frame.clear()
        self._build_ui()

    def _handle_logout(self):
        """Handles logout by clearing app state and rebuilding UI."""
        self._asset_category_id_selected = None
        self._asset_type_id_selected = ASSET_TYPES[0].get("Id")
        self._reset_pagination_state(True)
        APP_STATE.logout()
        asyncio.ensure_future(self._delayed_logout_rebuild())

    async def _delayed_logout_rebuild(self):
        """Rebuilds UI after logout."""
        await omni.kit.app.get_app().next_update_async()
        self.frame.clear()
        self._build_ui()

    def _build_category_view(self):
        """Builds the category view including tabs, logout, and the tree/grid area."""
        if not self._category_view_frame:
            return

        with self._category_view_frame:
            with ui.VStack(spacing=0, width=ui.Fraction(1)):
                self._build_category_header()
                ui.Line(
                    height=24,
                    alignment=ui.Alignment.V_CENTER,
                    style={"color": SEPARATOR_COLOR, "border_width": SEPARATOR_SIZE},
                )
                self._build_category_toolbar()
                ui.Line(
                    height=SEPARATOR_SIZE,
                    alignment=ui.Alignment.V_CENTER,
                    style={"color": SEPARATOR_COLOR, "border_width": SEPARATOR_SIZE},
                )
                ui.Spacer(height=self._gap)
                self._build_category_content_panels()
                asyncio.ensure_future(self._load_and_build_asset_tree())
                self._setup_splitter_drag()
                # self._setup_detail_splitter_drag() # Not used in current UI

    def _handle_open_in_browser(self):
        """Handles the 'Open In Browser' button click event."""
        import webbrowser

        selected_asset_type = next(
            (
                item
                for item in ASSET_TYPES
                if item["Id"] == self._asset_type_id_selected
            ),
            None,
        )
        if not selected_asset_type:
            carb.log_error("Invalid asset type selection.")
            return

        _final_url_to_open = f'{BASE_URL3}/#/home?id={self._asset_data_selected.get("Id","")}&t={selected_asset_type.get("TypeInBrowser","")}'
        webbrowser.open(_final_url_to_open)

    def _handle_setting(self):
        """Handles the settings button click event."""
        carb.log_info("Settings button clicked.")
        field_defs = [
            SettingModal.FieldDef("usd_server", "Server", ui.StringField, BASE_URL2),
        ]

        def _handle_form_submit(dialog: SettingModal):
            global BASE_URL2
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
                BASE_URL2 = new_usd_server
                _msg = f"Server updated to: {BASE_URL2}"
                carb.log_info(_msg)
                nm.post_notification(
                    _msg, duration=2.0, status=nm.NotificationStatus.INFO
                )
            else:
                nm.post_notification(
                    "Server unchanged",
                    duration=2.0,
                    status=nm.NotificationStatus.INFO,
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
            # if not self._is_system_admin:
            #     for tab_item in VISIBILITY_TABS:
            #         ui.Button(
            #             tab_item.get("Name"),
            #             width=ui.Length(120),
            #             height=self._btn_size,
            #             checked=tab_item.get("Id") == self._selected_visibility_tab_id,
            #             selected=tab_item.get("Id") == self._selected_visibility_tab_id,
            #             clicked_fn=lambda tab=tab_item: self._on_visibility_tab_click(
            #                 tab
            #             ),
            #         )

            ui.Spacer()
            ui.Button(
                "Setting",
                width=80,
                height=self._btn_size,
                clicked_fn=self._handle_setting,
            )
            # ui.Button(
            #     "Logout",
            #     width=80,
            #     height=self._btn_size,
            #     clicked_fn=self._handle_logout,
            # )

    def _build_category_toolbar(self):
        """Builds the toolbar with toggle buttons and search bar."""
        with ui.HStack(spacing=SEPARATOR_SIZE, height=self._btn_size):
            self._btn_toggle_tree = ui.Button(text="Toggle Tree", width=ui.Length(100))
            self._search_bar = ui.StringField(style={"background_color": cl("#333333")})
            self._btn_toggle_detail = ui.Button(
                text="Toggle Detail", width=ui.Length(100)
            )

            def _toggle_tree():
                if self._tree_panel_frame:
                    self._tree_panel_frame.visible = not self._tree_panel_frame.visible
                if self._splitter_frame:
                    self._splitter_frame.visible = not self._splitter_frame.visible

            self._btn_toggle_tree.set_mouse_pressed_fn(
                lambda a, b, c, d: _toggle_tree()
            )

            def _toggle_detail():
                if self._detail_panel_frame:
                    self._detail_panel_frame.visible = (
                        not self._detail_panel_frame.visible
                    )
                if self._detail_splitter_frame:
                    self._detail_splitter_frame.visible = (
                        not self._detail_splitter_frame.visible
                    )

            self._btn_toggle_detail.set_mouse_pressed_fn(
                lambda a, b, c, d: _toggle_detail()
            )

            self._search_bar.model.add_value_changed_fn(self._on_search_keyword_changed)

    def _on_search_keyword_changed(self, keyword_model: ui.SimpleStringModel):
        """Handles changes in the search bar with debouncing."""
        # Cancel any existing timer
        if self._search_timer_handle:
            self._search_timer_handle.cancel()

        # Schedule a new timer
        async def _debounced_search():
            keyword = keyword_model.get_value_as_string().strip()
            carb.log_info(f"Search keyword after debounce: '{keyword}'")

            # Reset pagination state for a new search
            self._reset_pagination_state(clear_all_local_data=True)

            # Trigger loading the first page with the new keyword
            # Only if a category is selected (including 'All')
            if self._asset_category_id_selected is not None:
                await self._load_assets_for_category(
                    self._asset_category_id_selected, page_index=1
                )
            else:
                carb.log_info(
                    "Search triggered, but no category is currently selected."
                )

        # Schedule the search after the debounce delay
        loop = asyncio.get_event_loop()
        self._search_timer_handle = loop.call_later(
            self._debounce_delay, lambda: asyncio.ensure_future(_debounced_search())
        )

    def _build_category_content_panels(self):
        """Builds the horizontally arranged panels for tree, splitter, grid, and detail."""
        with ui.HStack(spacing=0):
            # --- Tree Panel ---
            self._tree_panel_frame = ui.ScrollingFrame(
                width=ui.Length(self._tree_panel_initial_width),
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

            # --- Splitter between Tree and Grid ---
            self._splitter_frame = ui.Frame(
                width=ui.Length(SEPARATOR_SIZE),
                style={"background_color": SEPARATOR_COLOR},
            )
            with self._splitter_frame:
                self._splitter_placer = ui.Placer(
                    draggable=True,
                    drag_axis=ui.Axis.X,
                    width=ui.Length(SEPARATOR_SIZE),
                    offset_x=0,
                )
                with self._splitter_placer:
                    self._splitter_rect = ui.Rectangle(
                        width=ui.Length(SEPARATOR_SIZE),
                        style={"background_color": SEPARATOR_COLOR},
                    )

            # --- Grid and Detail Panel Area ---
            with ui.HStack(spacing=0):
                # --- Grid Panel ---
                self._grid_panel_frame = ui.ScrollingFrame(
                    width=ui.Fraction(1),
                    horizontal_scrollbar_policy=ui.ScrollBarPolicy.SCROLLBAR_AS_NEEDED,
                    vertical_scrollbar_policy=ui.ScrollBarPolicy.SCROLLBAR_AS_NEEDED,
                )

                # Set scroll callback for lazy loading detection
                self._set_lazy_load_callback(self._grid_panel_frame)

                # --- Vertical Splitter between Grid and Detail ---
                # Note: The detail panel is now directly added to the HStack, not in a separate frame.
                # This simplifies the layout and avoids issues with nested frames.
                self._detail_splitter_frame = ui.Frame(
                    width=ui.Length(SEPARATOR_SIZE),
                    style={"background_color": SEPARATOR_COLOR},
                )
                with self._detail_splitter_frame:
                    self._detail_splitter_rect = ui.Rectangle(
                        width=ui.Length(SEPARATOR_SIZE),
                        style={"background_color": SEPARATOR_COLOR},
                    )

                # --- Detail Panel ---
                # Adjust width to take remaining space if needed, or a fixed min width
                self._detail_panel_frame = ui.ScrollingFrame(
                    width=ui.Length(ASSET_DETAIL_MIN_WIDTH),
                    horizontal_scrollbar_policy=ui.ScrollBarPolicy.SCROLLBAR_AS_NEEDED,
                    vertical_scrollbar_policy=ui.ScrollBarPolicy.SCROLLBAR_AS_NEEDED,
                )
                self._build_detail_panel(None, None)

    def _set_lazy_load_callback(self, scrolling_frame: ui.ScrollingFrame):
        """Attaches a scroll position listener to trigger lazy loading."""

        def on_scrolling(scroll_pos_y):
            if (
                self._is_loading_more
                or self._no_more_assets_to_load
                or not self._grid_panel_frame
            ):
                return

            # Check if we are near the bottom of the scrollable content
            # Using scroll_y_max to determine the maximum scroll position
            max_scroll = scrolling_frame.scroll_y_max
            if max_scroll <= 0:  # Avoid division by zero
                return

            threshold = 0.8  # Trigger load when scrolled 80% down

            # Check if we're near the bottom
            if scroll_pos_y / max_scroll >= threshold:
                carb.log_info("Lazy Load triggered by scroll.")
                # Schedule the load task to avoid blocking the UI thread during scroll events
                asyncio.ensure_future(self._lazy_load_next_page_if_needed())

        scrolling_frame.set_scroll_y_changed_fn(on_scrolling)

    def _on_copy_name_to_clipboard(self, name: str):
        _result = on_copy_to_clipboard(to_copy=name)
        if _result == 1:
            nm.post_notification(
                "Name copied to clipboard successfully.",
                duration=2.0,
                status=nm.NotificationStatus.INFO,
            )

    def _build_detail_panel(self, asset_data: Optional[Dict[str, Any]], img_url):
        """Builds the content of the detail panel based on the provided asset data."""
        if not self._detail_panel_frame:
            return

        self._detail_panel_frame.clear()

        with self._detail_panel_frame:
            if asset_data:
                _asset_type_id = self._asset_type_id_selected
                with ui.HStack():
                    ui.Spacer(width=14)
                    with ui.VStack(
                        spacing=0,
                        style={"color": cl("#ffffffff")},
                    ):
                        ui.Spacer(height=self._gap)
                        with ui.HStack(height=0, spacing=self._gap):
                            if _asset_type_id == "Scene":
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
                                _asset_type_id == "SimReady"
                                or _asset_type_id == "Robot"
                            ):
                                with ui.HStack(height=24, spacing=0):
                                    ui.Label("Articulated:", width=0, height=24)
                                    _checkbox = ui.CheckBox(
                                        style={
                                            "color": cl.green,
                                            "margin": self._gap,
                                        },
                                        enabled=False,
                                    )
                                    _checkbox.model.set_value(
                                        asset_data.get("IsHasArticulus", False)
                                    )

                        ui.Image(
                            img_url,
                            height=300,
                            fill_policy=ui.FillPolicy.PRESERVE_ASPECT_FIT,
                            style={"border_radius": 4},
                        )
                        ui.Label(
                            asset_data.get("Name", "Unnamed"),
                            alignment=ui.Alignment.CENTER,
                            word_wrap=True,
                            height=0,
                        )
                        ui.Spacer(height=self._gap)

                        with ui.CollapsableFrame("Asset Info"):
                            with ui.VStack(spacing=self._gap * 2):
                                if _asset_type_id != "Scene":
                                    with ui.HStack():
                                        ui.Spacer(width=self._gap)
                                        ui.Label("Description:", width=0, height=0)
                                        ui.Spacer(width=self._gap)
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
        """
        Handles loading a selected scene asset.
        """
        if not self._asset_data_selected:
            nm.post_notification(
                "No scene selected to load.",
                duration=2.0,
                status=nm.NotificationStatus.WARNING,
            )
            carb.log_warn("Load Scene called, but no asset is selected.")
            return

        scene_id = self._asset_data_selected.get("Id")
        if not scene_id:
            nm.post_notification(
                "Selected scene data is invalid.",
                duration=2.0,
                status=nm.NotificationStatus.WARNING,
            )
            carb.log_error("Selected scene data missing 'Id'.")
            return

        target_usd_url = f"{BASE_URL2}/Scene/{scene_id}/main_ov.usd?t={time.time()}"
        carb.log_info(f"Target USD URL for scene load: {target_usd_url}")

        usd_context = omni.usd.get_context()
        current_stage = usd_context.get_stage()
        stage_has_content = False
        if current_stage:
            root_prim = current_stage.GetPrimAtPath(Sdf.Path.absoluteRootPath)
            if root_prim and root_prim.GetChildren():
                stage_has_content = True
                carb.log_info("Current stage appears to have content.")

        def _on_save_stage_confirm(*args):
            self._dialog_save_stage.destroy()

            def _on_save_done(a, b):
                if a:
                    asyncio.ensure_future(_async_load())

            omni.kit.window.file.save_as(False, on_save_done=_on_save_done)

        def _on_save_stage_cancel(*args):
            self._dialog_save_stage.destroy()
            asyncio.ensure_future(_async_load())

        async def _async_load():
            _scene_name = self._asset_data_selected.get("Name", "")
            nm.post_notification(
                f"Loading scene {_scene_name} ...",
                duration=1.0,
                status=nm.NotificationStatus.INFO,
                hide_after_timeout=False,
            )
            try:
                # self._loading.show()
                load_task = usd_context.open_stage_async(
                    target_usd_url, omni.usd.UsdContextInitialLoadSet.LOAD_ALL
                )
                carb.log_info(f"Initiated async loading of stage: {target_usd_url}")

                await load_task
                await omni.kit.app.get_app().next_update_async()
                nm.destroy_all_notifications()

                loaded_stage = usd_context.get_stage()
                if (
                    loaded_stage
                    and loaded_stage.GetRootLayer().identifier == target_usd_url
                ):
                    carb.log_info(f"Successfully loaded scene from {target_usd_url}")
                    nm.post_notification(
                        f"Scene {_scene_name} loaded successfully.",
                        duration=3.0,
                        status=nm.NotificationStatus.INFO,
                    )
                else:
                    raise RuntimeError(
                        "Stage loaded, but identifier mismatch or stage is None."
                    )

            except Exception as e:
                nm.destroy_all_notifications()
                error_msg = f"Failed to load scene {_scene_name}: {e}"
                carb.log_error(error_msg)
                nm.post_notification(
                    error_msg,
                    duration=5.0,
                    status=nm.NotificationStatus.WARNING,
                )
            # finally:
            #     if self._loading:
            #         self._loading.hide()

        if stage_has_content:
            dialog = MessageDialog(
                title="Save Stage",
                message="Save this stage before loading the selected scene?",
                ok_label="Ok",
                cancel_label="Discard",
                ok_handler=_on_save_stage_confirm,
                cancel_handler=_on_save_stage_cancel,
            )
            self._dialog_save_stage = dialog
            dialog.show()
        else:
            asyncio.ensure_future(_async_load())

    async def _load_and_build_asset_tree(self):
        """Loads category data from API and builds the TreeView."""
        selected_asset_type = next(
            (
                item
                for item in ASSET_TYPES
                if item["Id"] == self._asset_type_id_selected
            ),
            None,
        )
        if not selected_asset_type:
            carb.log_error("Invalid asset type selection.")
            self._update_tree_panel_with_error("Invalid asset type selection.")
            return

        try:
            _target_url = (
                selected_asset_type.get("CategoryListUrl")
                if APP_STATE.is_logged_in
                else selected_asset_type.get("CategoryListUrlFree")
            )
            category_list = await DATA_MANAGER.get_category_tree(_target_url)
            await omni.kit.app.get_app().next_update_async()

            self._tree_panel_frame.clear()
            with self._tree_panel_frame:
                with ui.VStack():
                    if len(category_list) > 0:
                        category_list.insert(
                            0,
                            {
                                "CategoryId": "All",
                                "CategoryLists": [],
                                "CategoryName": "All",
                                "Comment": "",
                                "IsSystem": False,
                                "ParentCategoryId": None,
                            },
                        )
                        self._category_model = CategoryModel(category_list)
                        self._category_delegate = CategoryDelegate()
                        self._tree_widget = ui.TreeView(
                            self._category_model,
                            delegate=self._category_delegate,
                            root_visible=False,
                            header_visible=False,
                            height=ui.Fraction(1),
                        )
                        self._tree_widget.set_selection_changed_fn(
                            self._on_selection_changed
                        )
                        # Programmatically select the first item ("All") to trigger initial load
                        _target_category = self._category_model._root.children[0]
                        self._tree_widget.call_selection_changed_fn([_target_category])
                    else:
                        ui.Label(
                            "No categories found",
                            style={"color": cl.gray},
                            alignment=ui.Alignment.CENTER,
                        )
                        # Initialize grid even if no categories
                        self._build_asset_grid([], "")

        except Exception as e:
            carb.log_error(f"Failed to build asset tree view: {e}")
            self._update_tree_panel_with_error(f"Failed to load assets: {str(e)}")

    def _on_selection_changed(self, items: List[CategoryItem]):
        """Handles selection change in the tree view."""
        if self._tree_widget:
            self._tree_widget.selection = items

        selected_item = items[0] if len(items) > 0 else None

        if selected_item:
            category_id = selected_item.category_id
            # Prevent redundant loading if the same category is selected again
            if self._asset_category_id_selected == category_id:
                carb.log_info(
                    f"Category {category_id} is already loaded or loading (via selection)."
                )
                return

            # Reset state for new category selection
            self._asset_category_id_selected = category_id
            self._reset_pagination_state(True)

            # Clear grid and show initial loading indicator
            if self._grid_panel_frame:
                self._grid_panel_frame.clear()
                with self._grid_panel_frame:
                    ui.Label(
                        "Loading assets...",
                        style={"color": cl.green},
                        alignment=ui.Alignment.CENTER,
                    )

            # Start loading first page for the selected category
            # Reset search bar to trigger a fresh load without a keyword
            if self._search_bar:
                self._search_bar.model.set_value("")
            asyncio.ensure_future(
                self._load_assets_for_category(category_id, page_index=1)
            )
        else:
            # No selection, clear everything
            self._reset_pagination_state(True)
            self._build_asset_grid([], "")  # Clear grid
            self._build_detail_panel(None, None)  # Clear detail
            self._asset_data_selected = None

    def _reset_pagination_state(self, clear_all_local_data: bool = False):
        """
        Resets pagination-related variables for a fresh start/load.
        Args:
            clear_all_local_data (bool): If True, clears the local cache of loaded items.
                                         This should be True for new searches or category changes.
        """
        self._current_page_index = 1
        self._total_pages_from_api = 1
        self._grid_rendered_count = 0
        self._is_loading_more = False
        self._no_more_assets_to_load = False

        # Clear local data cache if requested (e.g., new search or new category)
        if clear_all_local_data:
            self._all_loaded_asset_items.clear()

        # Always clear the displayed items as they are based on the loaded/cache
        self._displayed_asset_items.clear()
        self._loading_indicator_label = None
        # Don't clear the container reference here; it should persist.

    def _update_tree_panel_with_error(self, error_message: str):
        """Helper to update the tree panel frame with an error message."""

        async def _async_update():
            await omni.kit.app.get_app().next_update_async()
            self._tree_panel_frame.clear()
            with self._tree_panel_frame:
                ui.Label(error_message, style={"color": cl.red})

        asyncio.ensure_future(_async_update())

    def _setup_splitter_drag(self):
        """Sets up mouse event handlers for the draggable splitter."""
        if (
            not self._splitter_rect
            or not self._splitter_placer
            or not self._tree_panel_frame
        ):
            carb.log_warn(
                "Splitter components or tree panel not found, cannot setup drag."
            )
            return

        def on_placer_pressed(x, y, button, modifier):
            if button == 0:  # Left mouse button
                self._drag_start_tree_width = self._tree_panel_frame.width.value
                self._drag_start_x = x
                self._splitter_rect.set_style({"background_color": cl("#3b70b0")})

        def on_placer_hovered(is_hovered):
            if is_hovered:
                self._splitter_rect.set_style({"background_color": cl("#3b70b0")})
            else:
                self._splitter_rect.set_style({"background_color": SEPARATOR_COLOR})

        def on_placer_moved(x, y, dx, dy):  # dx, dy are relative movements
            if self._splitter_placer.dragging:
                delta_x = x - self._drag_start_x
                new_width = self._drag_start_tree_width + delta_x
                new_width = max(
                    CATEGORY_TREE_MIN_WIDTH, min(new_width, CATEGORY_TREE_MAX_WIDTH)
                )
                self._tree_panel_frame.width = ui.Length(new_width)
                # Reset offset to keep the placer aligned
                self._splitter_placer.offset_x = 0

        self._splitter_placer.set_mouse_hovered_fn(on_placer_hovered)
        self._splitter_placer.set_mouse_pressed_fn(on_placer_pressed)
        self._splitter_placer.set_mouse_moved_fn(on_placer_moved)

    def _setup_detail_splitter_drag(self):
        """Sets up mouse event handlers for the detail draggable splitter."""
        # This function is currently unused in the UI layout.
        # The detail panel is placed directly in the HStack.
        # If you want to make the detail panel resizable, you would need to
        # uncomment the relevant parts in _build_category_content_panels and
        # implement this function correctly.
        # Placeholder for future implementation if needed.
        carb.log_warn(
            "_setup_detail_splitter_drag is not implemented for current UI layout."
        )
        pass
        # if (
        #     not self._detail_splitter_rect
        #     or not self._detail_splitter_placer
        #     or not self._detail_panel_frame
        # ):
        #     carb.log_warn("Splitter components not found, cannot setup drag.")
        #     return

        # def on_placer_pressed(x, y, button, modifier):
        #     if button == 0:
        #         self._drag_start_detail_width = self._detail_panel_frame.width.value
        #         self._drag_start_detail_x = x
        #         self._detail_splitter_rect.set_style(
        #             {"background_color": cl("#3b70b0")}
        #         )

        # def on_placer_hovered(is_hovered):
        #     if is_hovered:
        #         self._detail_splitter_rect.set_style(
        #             {"background_color": cl("#3b70b0")}
        #         )
        #     else:
        #         self._detail_splitter_rect.set_style(
        #             {"background_color": SEPARATOR_COLOR}
        #         )

        # def on_placer_moved(x, y, a, b):
        #     if self._detail_splitter_placer.dragging:
        #         delta_x = x - self._drag_start_detail_x
        #         new_width = self._drag_start_detail_width + delta_x
        #         new_width = max(
        #             ASSET_DETAIL_MIN_WIDTH, min(new_width, ASSET_DETAIL_MAX_WIDTH)
        #         )
        #         self._detail_panel_frame.width = ui.Length(new_width)
        #         self._detail_splitter_placer.offset_x = 0

        # self._detail_splitter_placer.set_mouse_hovered_fn(on_placer_hovered)
        # self._detail_splitter_placer.set_mouse_pressed_fn(on_placer_pressed)
        # self._detail_splitter_placer.set_mouse_moved_fn(on_placer_moved)

    # --- Asset Loading and Grid Building with Lazy Loading ---

    async def _load_assets_for_category(self, category_id: str, page_index: int = 1):
        """Loads assets for a given category ID from the API, supporting pagination and search."""
        # Prevent overlapping requests
        if self._is_loading_more:
            carb.log_warn("_load_assets_for_category called while already loading.")
            return

        self._is_loading_more = True
        self._current_page_index = page_index  # Update internal state

        selected_asset_type = next(
            (
                item
                for item in ASSET_TYPES
                if item["Id"] == self._asset_type_id_selected
            ),
            None,
        )

        if not selected_asset_type or not selected_asset_type.get(
            "CategoryItemContentUrl"
        ):
            error_msg = f"Config error for {self._asset_type_id_selected}"
            carb.log_error(error_msg)
            self._update_grid_with_error(error_msg)
            self._is_loading_more = False
            return

        is_loading_public = (
            True
            if self._is_system_admin
            else (self._selected_visibility_tab_id == "Public")
        )
        list_api_url = (
            selected_asset_type["CategoryItemContentUrl"]
            if APP_STATE.is_logged_in
            else selected_asset_type["CategoryItemContentUrlFree"]
        )
        thumbnail_api_url = selected_asset_type["ThumbnailUrl"]
        _data_type = 1 if is_loading_public else 2

        search_keyword = ""
        if self._search_bar:
            search_keyword = self._search_bar.model.get_value_as_string().strip()

        params = {
            "CategoryId": category_id if category_id != "All" else "",
            "PageIndex": page_index,
            "PageSize": self._page_size,
            "OrderByType": -1,
            "Key": search_keyword,
            "DataType": _data_type,
        }

        carb.log_info(
            f"Loading assets for category '{category_id}', page {page_index}, with keyword '{search_keyword}'"
        )

        try:

            def deserialize_path(path_str: str, asset_name: str):
                try:
                    return json.loads(path_str)
                except json.JSONDecodeError:
                    # carb.log_error(f"{asset_name}: Error deserializing 'UsdCurrentPath'")
                    return ""

            assets_data = await DATA_MANAGER.get_asset_list(list_api_url, params)

            raw_data_list = assets_data.get("List", [])
            self._total_pages_from_api = assets_data.get("PageCount", 0)
            self._total_count_from_api = assets_data.get("Count", 0)

            processed_items = []
            if isinstance(raw_data_list, List):
                _asset_type_id = self._asset_type_id_selected
                if _asset_type_id == "Scene" or _asset_type_id == "_3dGS":
                    processed_items = raw_data_list
                else:  # Simready,Model,Robot
                    processed_items = [
                        {
                            **x,
                            "UsdCurrentPath": deserialize_path(
                                x.get("UsdCurrentPath", ""), x.get("Name", "")
                            ),
                        }
                        for x in raw_data_list
                    ]

            # Append newly loaded items to our local store
            # For search, we might want to replace instead of append if it's page 1?
            # But API should handle search + pagination correctly.
            # Let's stick to append logic, assuming API gives correct slice.
            # If user searches 'car', then goes to page 2, API gives page 2 of 'car' results.
            # Appending is fine.
            self._all_loaded_asset_items.extend(processed_items)

            # For display, we show all currently loaded items that match the *current* filter.
            # This is important if we are appending (lazy loading) and the filter hasn't changed.
            # But if we are doing a *new* search (page 1), this effectively replaces the display list.
            # Let's re-fetch filtered items. Since _all_loaded_asset_items now contains the latest
            # API results (which are already filtered by the backend), this should just be a copy.
            # However, if there was a client-side filter active somehow, this would apply it.
            # Given the change, it's safer to re-apply the filter logic.
            # But the simplest and most correct way is to assume API results are filtered,
            # and just display them. The _displayed_asset_items list is rebuilt from
            # _all_loaded_asset_items every time we load new data.
            # So, after extending _all_loaded_asset_items, we update _displayed_asset_items.
            # But actually, the grid should display the `processed_items` we just got.
            # Let's simplify: the grid displays what we just loaded from the API for this page/request.
            # The local cache (_all_loaded_asset_items) accumulates them.
            # The _displayed_asset_items should reflect what's currently shown.
            # On a new search (page 1), _displayed_asset_items should be `processed_items`.
            # On append (page > 1), it should be `_displayed_asset_items + processed_items`.
            # But the grid rebuild logic (_build_or_update_asset_grid) handles append/replace based on page.
            # Let's set _displayed_asset_items correctly here.

            # Determine items to display based on page
            if page_index == 1:
                # New search or category load, display only the items from this page/load
                self._displayed_asset_items = processed_items.copy()
            else:
                # Appending, add new items to the display list
                # Note: This might be redundant if _build_or_update_asset_grid handles append correctly
                # by looking at _all_loaded_asset_items. Let's keep it for clarity.
                self._displayed_asset_items.extend(processed_items)

            # Decide whether there's more data expected
            # Use the total count/pages from the API response for the current search/filter
            if (
                page_index >= self._total_pages_from_api
                or self._total_count_from_api <= 0
            ):
                self._no_more_assets_to_load = True

            carb.log_info(
                f"Loaded Page {page_index}/{self._total_pages_from_api} ({len(processed_items)} items) for category {category_id}. Total stored locally: {len(self._all_loaded_asset_items)}. No More? {self._no_more_assets_to_load}"
            )

            # Build/update the grid UI with ALL currently displayed items
            is_append_operation = page_index > 1
            self._build_or_update_asset_grid(
                self._displayed_asset_items,
                thumbnail_api_url,
                is_append=is_append_operation,
            )

        except Exception as e:
            error_msg = f"Failed to load assets for category {category_id}: {e}"
            carb.log_error(error_msg)
            self._update_grid_with_error(error_msg)
        finally:
            self._is_loading_more = False

    async def _lazy_load_next_page_if_needed(self):
        """Checks conditions and triggers loading of the next page if appropriate."""
        # Double-check conditions before proceeding
        if (
            not self._is_loading_more
            and not self._no_more_assets_to_load
            and self._current_page_index < self._total_pages_from_api
            and self._asset_category_id_selected is not None
        ):

            carb.log_info(
                f"Lazy loading initiated for page {self._current_page_index + 1}"
            )
            next_page = self._current_page_index + 1
            await self._load_assets_for_category(
                self._asset_category_id_selected, page_index=next_page
            )

    def _clear_and_build_asset_grid(self, asset_items: list, thumbnail_api_url: str):
        """Completely replaces the contents of the asset grid."""
        if not self._grid_panel_frame:
            carb.log_warn("Grid content frame not found.")
            return

        self._grid_panel_frame.clear()
        self._currently_selected_image_widget = None
        self._asset_data_selected = None
        self._build_detail_panel(None, None)
        self._grid_vgrid_container = None  # Reset container ref on full clear
        self._grid_rendered_count = 0  # Reset rendered count

        with self._grid_panel_frame:
            if not asset_items or len(asset_items) < 1:
                ui.Label(
                    "No assets found",
                    style={"color": cl.gray},
                    alignment=ui.Alignment.CENTER,
                )
                return

            column_width = 200
            row_height = 150

            # Create the main container for grid items dynamically added later
            self._grid_vgrid_container = ui.VGrid(
                column_width=column_width,
                row_height=row_height,
                width=ui.Fraction(1),
            )

            # Populate items into the container initially
            self._populate_grid_items_into_container(
                self._grid_vgrid_container, asset_items, thumbnail_api_url
            )

    def _build_or_update_asset_grid(
        self, asset_items: list, thumbnail_api_url: str, is_append: bool = False
    ):
        """Either creates a new grid or updates/appends to an existing one."""
        if not self._grid_panel_frame:
            carb.log_warn("Grid content frame not found.")
            return

        # Handle case where grid needs to be created anew (first load, category switch etc.)
        if not is_append or self._grid_vgrid_container is None:
            # Full replacement logic - essentially same as old _build_asset_grid but storing container ref
            self._clear_and_build_asset_grid(asset_items, thumbnail_api_url)
            return

        # Otherwise, it's an append operation onto an existing grid
        # Just add new items to the existing container
        if self._grid_vgrid_container and len(asset_items) > 0:
            num_existing_rendered_items = self._grid_rendered_count
            new_items_to_render = asset_items[num_existing_rendered_items:]

            if new_items_to_render:
                self._populate_grid_items_into_container(
                    self._grid_vgrid_container, new_items_to_render, thumbnail_api_url
                )
                # Update counter tracking how many items have been visually added to grid
                self._grid_rendered_count = num_existing_rendered_items + len(
                    new_items_to_render
                )

    def _populate_grid_items_into_container(
        self, container: ui.VGrid, asset_items: list, thumbnail_api_url: str
    ):
        def make_on_image_pressed(image_widget: ui.Image, data: Dict[str, Any]):
            def on_image_pressed(x, y, btn, mod):
                if btn == 0:  # Left click
                    if self._currently_selected_image_widget:
                        self._currently_selected_image_widget.set_style(
                            IMAGE_STYLE_UNSELECTED
                        )

                    image_widget.set_style(IMAGE_STYLE_SELECTED)
                    self._currently_selected_image_widget = image_widget

                    self._asset_data_selected = data
                    # The image URL needs to be passed to the detail panel
                    # It's either the thumbnail URL or the empty image path
                    img_url = (
                        image_widget.source_url
                        if image_widget.source_url
                        else IMAGE_EMPTY_PATH
                    )
                    self._build_detail_panel(data, img_url)

            return on_image_pressed

        """Actually adds individual asset widgets into the specified container."""
        for item_data in asset_items:
            item_name = item_data.get("Name", "Unnamed Asset")
            item_id = item_data.get("Id")
            item_thumbnail_b64 = item_data.get("MiniLogo", None)

            with container:  # Add directly into passed-in container/VGrid
                with ui.VStack(spacing=0):
                    _final_thumbnail_url = IMAGE_EMPTY_PATH
                    if item_thumbnail_b64:
                        _final_thumbnail_url = (
                            f"{thumbnail_api_url}/{item_id}.png?t={time.time()}"
                        )

                    _thumbnail = ui.Image(
                        _final_thumbnail_url,
                        fill_policy=ui.FillPolicy.PRESERVE_ASPECT_FIT,
                        style=IMAGE_STYLE_UNSELECTED,
                    )
                    _thumbnail.set_mouse_pressed_fn(
                        make_on_image_pressed(_thumbnail, item_data)
                    )

                    if self._asset_type_id_selected != "Scene":
                        _thumbnail.set_drag_fn(
                            lambda _data=item_data, _url=_final_thumbnail_url: self._get_asset_usd_path(
                                _data, _url
                            )
                        )
                        _thumbnail.set_tooltip("Drag and place")

                    ui.Label(
                        item_name,
                        word_wrap=True,
                        height=0,
                        alignment=ui.Alignment.CENTER,
                    )
                    ui.Spacer(height=self._gap)

    def _get_asset_usd_path(
        self, data: dict, thumbnail_url: str
    ):  # Renamed parameter for clarity
        """Callback for drag-and-drop, returns the USD path for an asset."""
        _asset_name = data.get("Name", "Unnamed")
        _asset_type_id = self._asset_type_id_selected
        _has_usd_file = data.get("IsHasUsdFile", False)

        if not _has_usd_file:
            nm.post_notification(
                f"Asset '{_asset_name}' has no USD file available.",
                duration=3.0,
                status=nm.NotificationStatus.WARNING,
            )
            return ""

        with ui.VStack(spacing=self._gap):
            ui.Image(
                thumbnail_url,
                width=200,
                height=150,
                fill_policy=ui.FillPolicy.PRESERVE_ASPECT_FIT,
            )
            ui.Label(_asset_name, alignment=ui.Alignment.CENTER, word_wrap=True)

        if _asset_type_id == "_3dGS":
            if data and data.get("Id"):
                asyncio.ensure_future(self._log_asset_load_record(data))
                return f"{BASE_URL1}/api/Usd/UsdzFile/{data['Id']}.usdz"
            else:
                return ""
        else:
            if data:
                _usd_path = data.get("UsdCurrentPath", None)
                if isinstance(_usd_path, list) and len(_usd_path) > 0:
                    asyncio.ensure_future(self._log_asset_load_record(data))
                    # Ensure path starts with a single slash
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
                for item in ASSET_TYPES
                if item["Id"] == self._asset_type_id_selected
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
        await DATA_MANAGER.log_asset_load_record(
            f"{BASE_URL1}/api/Global/AddLoadRecord", _data
        )

    def _update_grid_with_error(self, error_message: str):
        """Helper to update the asset grid frame with an error message."""
        if not self._grid_panel_frame:
            return
        self._grid_panel_frame.clear()
        with self._grid_panel_frame:
            ui.Label(error_message, style={"color": cl.red})
