from omni.kit.async_engine import run_coroutine
import omni.ui as ui

from typing import List, Union, Callable
from collections import namedtuple
from .style import get_style
from omni.kit.window.popup_dialog import PopupDialog, FormWidget
from .util import get_field_value


class SettingModal(PopupDialog):
    FieldDef = namedtuple(
        "FormDialogFieldDef", "name label type default focused", defaults=[False]
    )

    def __init__(
        self,
        width: int = 400,
        message: str = None,
        title: str = None,
        ok_handler: Callable[[PopupDialog], None] = None,
        cancel_handler: Callable[[PopupDialog], None] = None,
        ok_label: str = "Ok",
        cancel_label: str = "Cancel",
        field_defs: List[FieldDef] = None,
    ):
        super().__init__(
            width=width,
            title=title,
            ok_handler=ok_handler,
            cancel_handler=cancel_handler,
            ok_label=ok_label,
            cancel_label=cancel_label,
            modal=True,
        )
        with self._window.frame:
            with ui.VStack(style=get_style()):
                ui.Spacer(height=6)
                self._widget = FormWidget(message, field_defs)
                ui.Spacer(height=6)
                self._build_ok_cancel_buttons()
                ui.Spacer(height=6)
        self.hide()

    def show(self, offset_x: int = 0, offset_y: int = 0, parent: ui.Widget = None):
        """
        Shows this dialog, optionally offset from the parent widget, if any.

        Keyword Args:
            offset_x (int): X offset. Default 0.
            offset_y (int): Y offset. Default 0.
            parent (ui.Widget): Offset from this parent widget. Default None.

        """
        # focus on show
        self._widget.focus()
        super().show(offset_x=offset_x, offset_y=offset_y, parent=parent)

    def get_field(self, name: str) -> ui.AbstractField:
        """
        Returns widget corresponding to named field.

        Args:
            name (str): Name of the field.

        Returns:
            omni.ui.AbstractField

        """
        if self._widget:
            return self._widget.get_field(name)
        return None

    def get_value(self, name: str) -> Union[str, int, float, bool]:
        """
        Returns value of the named field.

        Args:
            name (str): Name of the field.

        Returns:
            Union[str, int, float, bool]

        Note:
            Doesn't currently return MultiFields correctly.

        """
        if self._widget:
            return self._widget.get_value(name)
        return None

    def get_values(self) -> dict:
        """
        Returns all values in a dict.

        Args:

            name (str): Name of the field.

        Returns:
            dict

        Note:
            Doesn't currently return MultiFields correctly.

        """
        if self._widget:
            return self._widget.get_values()
        return {}

    def reset_values(self):
        """Resets all values to their defaults."""
        if self._widget:
            return self._widget.reset_values()

    def destroy(self):
        """Destructor."""
        if self._widget:
            self._widget.destroy()
        self._widget = None
        super().destroy()


class FormWidget:
    """
    A simple form widget with a set of input fields. As opposed to the dialog class, the widget can be combined
    with other widget types in the same window.

    Keyword Args:
        message (str): Message string.
        field_defs ([FormDialog.FieldDef]): List of FieldDefs. Default [].

    Note:
        FormDialog.FieldDef:
            A namedtuple of (name, label, type, default value) for describing the input field,
            e.g. FormDialog.FieldDef("name", "Name:  ", omni.ui.StringField, "Bob").

    """

    def __init__(
        self, message: str = None, field_defs: List[SettingModal.FieldDef] = []
    ):
        self._field_defs = field_defs
        self._fields = {}
        self._build_ui(message, field_defs)

    def _build_ui(self, message: str, field_defs: List[SettingModal.FieldDef]):

        with ui.ZStack(style=get_style()):
            with ui.VStack(spacing=6):
                if message:
                    ui.Label(
                        message,
                        height=20,
                        word_wrap=True,
                    )
                for field_def in field_defs:
                    with ui.HStack(height=0):
                        ui.Spacer(width=6)
                        ui.Label(
                            field_def.label,
                            style_type_name_override="Field.Label",
                            name="prefix",
                            alignment=ui.Alignment.CENTER,
                            width=60,
                        )
                        ui.Spacer(width=6)
                        field = field_def.type(
                            height=20,
                        )
                        ui.Spacer(width=6)

                        if "set_value" in dir(field.model):
                            field.model.set_value(field_def.default)
                        self._fields[field_def.name] = field

    def focus(self) -> None:
        """Focus fields for the current widget."""

        # had to delay focus keyboard for one frame
        async def delay_focus(field):
            import omni.kit.app

            await omni.kit.app.get_app().next_update_async()
            field.focus_keyboard()

        # OM-80009: Add ability to focus an input field for form dialog;
        #  When multiple fields are set to focused, then the last field will be the
        #  actual focused field.
        for field_def in self._field_defs:
            if field_def.focused:
                field = self._fields[field_def.name]
                run_coroutine(delay_focus(field))

    def get_field(self, name: str) -> ui.AbstractField:
        """
        Returns widget corresponding to named field.

        Args:
            name (str): Name of the field.

        Returns:
            omni.ui.AbstractField

        """
        if name and name in self._fields:
            return self._fields[name]
        return None

    def get_value(self, name: str) -> Union[str, int, float, bool]:
        """
        Returns value of the named field.

        Args:
            name (str): Name of the field.

        Returns:
            Union[str, int, float, bool]

        Note:
            Doesn't currently return MultiFields correctly.

        """
        if name and name in self._fields:
            field = self._fields[name]
            return get_field_value(field)
        return None

    def get_values(self) -> dict:
        """
        Returns all values in a dict.

        Args:
            name (str): Name of the field.

        Returns:
            dict

        Note:
            Doesn't currently return MultiFields correctly.

        """
        return {name: get_field_value(field) for name, field in self._fields.items()}

    def reset_values(self):
        """Resets all values to their defaults."""
        for field_def in self._field_defs:
            if field_def.name in self._fields:
                field = self._fields[field_def.name]
                if "set_value" in dir(field.model):
                    field.model.set_value(field_def.default)

    def destroy(self):
        """Destructor."""
        self._field_defs = None
        self._fields.clear()
