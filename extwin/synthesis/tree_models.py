import omni.ui as ui
from typing import List, Optional, Dict, Any
from omni.ui import color as cl
import os

EXT_PATH = os.path.dirname(__file__)

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
