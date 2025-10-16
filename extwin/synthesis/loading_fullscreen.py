import omni.ui as ui
from omni.ui import color as cl


class FullScreenLoading:
    def __init__(self):
        self._window = None
        self.build_ui()

    def build_ui(self):
        self._window = ui.Window(
            "FullScreenLoading",
            width=0,
            height=0,
            visible=False,
            docked=True,
            flags=ui.WINDOW_FLAGS_NO_TITLE_BAR
            | ui.WINDOW_FLAGS_NO_RESIZE
            | ui.WINDOW_FLAGS_NO_SCROLLBAR
            | ui.WINDOW_FLAGS_MODAL,
        )

        with self._window.frame:
            with ui.ZStack():
                ui.Rectangle(
                    style={"background_color": cl(0, 0, 0, 100)}
                )
                ui.Label(
                    "Loading...",
                    style={
                        "color": cl.white,
                        "font_size": 24,
                    },
                    alignment=ui.Alignment.CENTER,
                )

    def show(self):
        if self._window:
            width = ui.Workspace.get_main_window_width()
            height = ui.Workspace.get_main_window_height()
            self._window.width = width
            self._window.height = height
            self._window.visible = True

    def hide(self):
        if self._window:
            self._window.visible = False

    def destroy(self):
        if self._window:
            self._window.destroy()
        self._window = None
