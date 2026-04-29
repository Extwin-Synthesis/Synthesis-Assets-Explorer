from __future__ import annotations

import time
from typing import Any, Dict, List

import omni.ui as ui

from .thumbnail_strategy import ThumbnailStrategy

MAX_PROVIDER_REFS = 600
THUMBNAIL_WIDTH = 200
THUMBNAIL_HEIGHT = 150


async def _set_thumbnail_next_frame(image_widget: ui.Image, url: str) -> None:
    import omni.kit.app

    await omni.kit.app.get_app().next_update_async()
    image_widget.source_url = url


def _build_thumbnail_widget(
    owner: Any,
    final_thumbnail_url: str,
    image_empty_path: str,
    image_style_unselected: Dict[str, Any],
    strategy: str,
    img_width: int = THUMBNAIL_WIDTH,
    img_height: int = THUMBNAIL_HEIGHT,
) -> ui.Image:
    if strategy == ThumbnailStrategy.placeholder_then_update:
        thumb = ui.Image(
            image_empty_path,
            width=img_width,
            height=img_height,
            fill_policy=ui.FillPolicy.PRESERVE_ASPECT_FIT,
            style=image_style_unselected,
        )
        if final_thumbnail_url != image_empty_path:
            owner._spawn(
                _set_thumbnail_next_frame(thumb, final_thumbnail_url),
                "thumbnail_deferred_update",
            )
        return thumb

    if strategy == ThumbnailStrategy.provider:
        provider = ui.RasterImageProvider(final_thumbnail_url)
        # Reduce provider GPU pressure for long scrolling sessions.
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
        # Keep reference set bounded to avoid unbounded Python-side retention.
        if len(owner._thumbnail_provider_refs) > MAX_PROVIDER_REFS:
            owner._thumbnail_provider_refs.pop(next(iter(owner._thumbnail_provider_refs)))
        return thumb

    return ui.Image(
        final_thumbnail_url,
        width=img_width,
        height=img_height,
        fill_policy=ui.FillPolicy.PRESERVE_ASPECT_FIT,
        style=image_style_unselected,
    )


def populate_grid_items_into_container(
    owner: Any,
    container: ui.VGrid,
    asset_items: List[Dict[str, Any]],
    thumbnail_api_url: str,
    image_style_unselected: Dict[str, Any],
    image_style_selected: Dict[str, Any],
    image_empty_path: str,
    gap: int,
    thumbnail_strategy: str = ThumbnailStrategy.placeholder_then_update,
) -> None:
    def make_on_image_pressed(
        image_widget: ui.Image, data: Dict[str, Any], thumbnail_url: str
    ):
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
                    if item_thumbnail_data:
                        base_thumbnail_url = f"{thumbnail_api_url}/{item_id}.png"
                        if thumbnail_strategy == ThumbnailStrategy.provider:
                            # RasterImageProvider in Kit may reject URLs with query params.
                            final_thumbnail_url = base_thumbnail_url
                        else:
                            cache_buster = int(time.time() * 1000)
                            final_thumbnail_url = f"{base_thumbnail_url}?t={cache_buster}"
                    
                    thumbnail = _build_thumbnail_widget(
                        owner,
                        final_thumbnail_url,
                        image_empty_path,
                        image_style_unselected,
                        thumbnail_strategy,
                        img_width=THUMBNAIL_WIDTH,
                        img_height=THUMBNAIL_HEIGHT,
                    )
                    thumbnail.set_mouse_pressed_fn(
                        make_on_image_pressed(thumbnail, item_data, final_thumbnail_url)
                    )

                    if owner.state.asset_type_id != "Scene":
                        thumbnail.set_drag_fn(
                            lambda _data=item_data, _url=final_thumbnail_url: owner._get_asset_usd_path(
                                _data, _url
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

