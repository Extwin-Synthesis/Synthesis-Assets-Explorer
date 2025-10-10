# from omni.kit.window.extensions.common import get_icons_path
from omni import ui
from omni.ui import color as cl


def get_style():

    # icons_path = get_icons_path()

    KIT_GREEN_CHECKBOX = cl("#9a9a9aFF")
    BORDER_RADIUS = 2
    FONT_SIZE = 14.0
    TOOLTIP_STYLE = {
        "background_color": cl("#FFf7d1ff"),
        "color": cl("#333333ff"),
        "margin_width": 0,
        "margin_height": 0,
        "padding": 0,
        "border_width": 0,
        "border_radius": BORDER_RADIUS,
        "border_color": cl("#000000FF"),
    }

    LABEL_COLOR = cl("#868e8fff")
    FIELD_BACKGROUND = cl("#1f2123ff")
    WINDOW_BACKGROUND_COLOR = cl("#444444ff")
    BUTTON_BACKGROUND_COLOR = cl("#1f2124")
    BUTTON_BACKGROUND_HOVERED_COLOR = cl("#9e9e9eff")
    BUTTON_BACKGROUND_PRESSED_COLOR = cl("#78872ac2")
    BUTTON_LABEL_DISABLED_COLOR = cl("#606060ff")
    style = {
        "Window": {"background_color": WINDOW_BACKGROUND_COLOR},
        "Button": {
            "background_color": BUTTON_BACKGROUND_COLOR,
            "margin": 0,
            "padding": 3,
            "border_radius": BORDER_RADIUS,
        },
        "Button:hovered": {"background_color": BUTTON_BACKGROUND_HOVERED_COLOR},
        "Button:pressed": {"background_color": BUTTON_BACKGROUND_PRESSED_COLOR},
        "Button.Label:disabled": {"color": BUTTON_LABEL_DISABLED_COLOR},
        "Label": {"font_size": FONT_SIZE, "color": LABEL_COLOR},
        "LabelInTreeView": {"color": cl("#ffffffff")},
        "CheckBox::greenCheck": {
            "font_size": 12,
            "background_color": KIT_GREEN_CHECKBOX,
            "color": FIELD_BACKGROUND,
            "border_radius": BORDER_RADIUS,
        },
        "TreeView": {
            "background_color": cl("#1f2123ff"),
            "background_selected_color": cl("#434d4f66"),
            "secondary_color": cl("#3b3b40ff"),
            # "secondary_selected_color": cl("#00ff00ff"),
            # "border_color": cl.red,
            # "border_width": 10
        },
        "TreeView:selected": {
            "background_color": cl("#434d4fff"),
        },
        "TreeView.Header": {
            "background_color": cl.blue,
        },
        "Tooltip": TOOLTIP_STYLE,
        "Field.Label": {
            "color": cl("#ffffffff"),
        },
    }

    return style
