from __future__ import annotations

from typing import Any

import omni.ui as ui

THUMBNAIL_WIDTH = 200
THUMBNAIL_HEIGHT = 150


def release_thumbnail_providers(refs: dict[int, Any]) -> None:
    """Drop Python references so Kit can free the previous category's textures."""
    refs.clear()


def _make_raster_thumbnail(
    owner: Any,
    url: str,
    image_style_unselected: dict[str, Any],
    img_width: int,
    img_height: int,
) -> ui.ImageWithProvider:
    provider = ui.RasterImageProvider(url)
    try:
        provider.max_mip_levels = 1
    except Exception:
        pass
    thumb = ui.ImageWithProvider(
        provider,
        width=ui.Length(img_width),
        height=ui.Length(img_height),
        style=image_style_unselected,
    )
    try:
        thumb.fill_policy = ui.FillPolicy.PRESERVE_ASPECT_FIT
    except Exception:
        pass
    try:
        thumb.prepare_draw(float(img_width), float(img_height))
    except Exception:
        pass
    owner._thumbnail_provider_refs[id(thumb)] = provider
    return thumb


def populate_grid_items_into_container(
    owner: Any,
    container: ui.VGrid,
    asset_items: list[dict[str, Any]],
    thumbnail_api_url: str,
    image_style_unselected: dict[str, Any],
    image_style_selected: dict[str, Any],
    image_empty_path: str,
    gap: int,
) -> None:
    def make_on_image_pressed(image_widget, data: dict[str, Any], thumbnail_url: str):
        def on_image_pressed(x, y, btn, mod):
            if btn != 0:
                return
            if owner._current_selected_thumb:
                owner._current_selected_thumb.set_style(image_style_unselected)
            image_widget.set_style(image_style_selected)
            owner._current_selected_thumb = image_widget
            owner.state.selected_asset = data
            img_url = thumbnail_url if thumbnail_url else image_empty_path
            owner._build_detail_panel(data, img_url)

        return on_image_pressed

    for item_data in asset_items:
        item_name = item_data.get("Name", "Unnamed Asset")
        item_id = item_data.get("Id")
        item_thumbnail_data = item_data.get("MiniLogo", None)

        with container:
            with ui.Frame():
                with ui.VStack(spacing=0):
                    final_thumbnail_url = image_empty_path
                    if item_thumbnail_data and item_id:
                        final_thumbnail_url = f"{thumbnail_api_url}/{item_id}.png"
                        thumbnail = _make_raster_thumbnail(
                            owner,
                            final_thumbnail_url,
                            image_style_unselected,
                            THUMBNAIL_WIDTH,
                            THUMBNAIL_HEIGHT,
                        )
                    else:
                        thumbnail = ui.Image(
                            image_empty_path,
                            width=THUMBNAIL_WIDTH,
                            height=THUMBNAIL_HEIGHT,
                            fill_policy=ui.FillPolicy.PRESERVE_ASPECT_FIT,
                            style=image_style_unselected,
                        )

                    thumbnail.set_mouse_pressed_fn(
                        make_on_image_pressed(thumbnail, item_data, final_thumbnail_url)
                    )

                    if owner.state.asset_type_id != "Scene":
                        preview_provider = owner._thumbnail_provider_refs.get(id(thumbnail))
                        thumbnail.set_drag_fn(
                            lambda _data=item_data, _provider=preview_provider: owner._get_asset_usd_path(
                                _data, _provider
                            )
                        )
                        thumbnail.set_tooltip("Drag and place")

                    ui.Spacer(height=gap)
                    ui.Label(
                        item_name,
                        word_wrap=True,
                        height=0,
                        alignment=ui.Alignment.CENTER,
                        elided_text=True,
                        tooltip=item_name,
                    )
                    ui.Spacer(height=gap)
