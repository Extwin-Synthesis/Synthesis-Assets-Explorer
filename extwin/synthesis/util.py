import carb
import uuid
from typing import Dict, List, Optional, Union

from omni import ui


def generate_category_tree(
    root_name: str = "Others",  # 根节点名称
    depth: int = 2,  # 树的总深度（根节点为第1层，depth=2表示根+1层子节点）
    children_count: int = 5,  # 每个非叶子节点默认的子节点数量
    is_system: bool = True,  # 所有节点的IsSystem默认值
) -> Dict:
    """
    生成指定深度的分类树形结构，格式与示例一致

    Args:
        root_name: 根节点的CategoryName
        depth: 树的总深度（至少为1，1表示仅根节点）
        children_count: 每个非叶子节点的子节点数量（叶子节点无children）
        is_system: 所有节点的IsSystem字段值

    Returns:
        完整的树形结构字典
    """

    # 工具函数：生成唯一的CategoryId（UUID4格式，与示例一致）
    def _generate_uuid() -> str:
        return str(uuid.uuid4())

    # 递归函数：生成单个节点及下属子树
    def _build_node(
        parent_id: Optional[str],  # 父节点ID（根节点为None）
        current_level: int,  # 当前节点的层级（根节点为1）
    ) -> Dict:
        # 1. 生成当前节点的基础信息
        node_id = _generate_uuid()
        node: Dict = {
            "CategoryId": node_id,
            "ParentCategoryId": (
                parent_id if parent_id is not None else ""
            ),  # 根节点Parent为空字符串
            "CategoryName": _get_node_name(
                current_level, node_id
            ),  # 生成有辨识度的节点名称
            "Comment": "",  # 固定为空字符串，与示例一致
            "CategoryLists": [],  # 子节点列表（后续递归填充）
            "IsSystem": is_system,
        }

        # 2. 若未达到目标深度，递归生成子节点
        if current_level < depth:
            node["CategoryLists"] = [
                _build_node(parent_id=node_id, current_level=current_level + 1)
                for _ in range(children_count)
            ]

        return node

    # 工具函数：生成节点名称（包含层级和ID后4位，便于区分）
    def _get_node_name(level: int, node_id: str) -> str:
        if level == 1:
            return root_name  # 根节点用自定义名称
        # 非根节点：格式如"Level2-xxxx"（xxxx为ID后4位）
        id_suffix = node_id[-4:]  # 取UUID后4位作为唯一标识
        base_names = [
            "Car",
            "Machinery",
            "Subway facilities",
            "Door",
            "Hardware tools",
            "Gearwhee",
            "Electrical equipment",
            "Dryingracks",
        ]
        # 循环使用示例中的基础名称，避免重复
        base_name = base_names[level % len(base_names)]
        return f"{base_name}-L{level}-{id_suffix}"

    # 3. 从根节点开始构建整棵树（根节点层级为1）
    if depth < 1:
        raise ValueError("Depth must be at least 1 (root node only)")
    return _build_node(parent_id=None, current_level=1)


# # ------------------------------
# # 使用示例
# # ------------------------------
# if __name__ == "__main__":
#     # 1. 生成深度为3的树（根节点+2层子节点，每层5个节点）
#     tree_depth_3 = generate_category_tree(root_name="Others", depth=3, children_count=5)

#     # 2. 打印树结构（可用于调试或验证）
#     import json

#     print("生成的树形结构：")
#     print(json.dumps(tree_depth_3, indent=2))


def get_field_value(field: ui.AbstractField) -> Union[str, int, float, bool]:
    """
    Returns value of the given field.

    Args:
        field (:obj:'ui.AbstractField'): Name of the field.

    Returns:
        Union[str, int, float, bool]
    """
    
    if not field:
        return None
    if isinstance(field, ui.StringField):
        return field.model.get_value_as_string()
    elif type(field) in [ui.IntField, ui.IntDrag, ui.IntSlider]:
        return field.model.get_value_as_int()
    elif type(field) in [ui.FloatField, ui.FloatDrag, ui.FloatSlider]:
        return field.model.get_value_as_float()
    elif isinstance(field, ui.CheckBox):
        return field.model.get_value_as_bool()
    else:
        # TODO: Retrieve values for MultiField
        return None
    
def on_copy_to_clipboard(to_copy: str) -> int | None:
    """
    Copy text to system clipboard
    """
    try:
        import pyperclip
    except ImportError:
        carb.log_warn("Could not import pyperclip.")
        return
    try:
        pyperclip.copy(to_copy)
        return 1
    except pyperclip.PyperclipException:
        carb.log_warn(pyperclip.EXCEPT_MSG)
        return
