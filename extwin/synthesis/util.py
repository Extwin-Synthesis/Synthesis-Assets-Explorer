import carb
from typing import Union

from omni import ui


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
