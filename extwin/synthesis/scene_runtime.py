from __future__ import annotations

import time
from typing import Any

import carb
import omni.kit.app
import omni.kit.notification_manager as nm
import omni.kit.window.file
import omni.usd
from omni.kit.window.popup_dialog import MessageDialog
from pxr import Sdf

from .data_manager import BASE_URL2


def load_scene(owner: Any) -> None:
    if not owner.state.selected_asset:
        nm.post_notification(
            "No scene selected to load.",
            duration=2.0,
            status=nm.NotificationStatus.WARNING,
        )
        carb.log_warn("Load Scene called, but no asset is selected.")
        return

    scene_id = owner.state.selected_asset.get("Id")
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
        stage_has_content = bool(root_prim and root_prim.GetChildren())

    async def _async_load():
        scene_name = owner.state.selected_asset.get("Name", "")
        nm.post_notification(
            f"Loading scene {scene_name} ...",
            duration=1.0,
            status=nm.NotificationStatus.INFO,
            hide_after_timeout=False,
        )
        try:
            load_task = usd_context.open_stage_async(
                target_usd_url, omni.usd.UsdContextInitialLoadSet.LOAD_ALL
            )
            await load_task
            await omni.kit.app.get_app().next_update_async()
            nm.destroy_all_notifications()
            loaded_stage = usd_context.get_stage()
            if loaded_stage and loaded_stage.GetRootLayer().identifier == target_usd_url:
                nm.post_notification(
                    f"Scene {scene_name} loaded successfully.",
                    duration=3.0,
                    status=nm.NotificationStatus.INFO,
                )
            else:
                raise RuntimeError("Stage loaded, but identifier mismatch or stage is None.")
        except Exception as e:
            nm.destroy_all_notifications()
            nm.post_notification(
                f"Failed to load scene {scene_name}: {e}",
                duration=5.0,
                status=nm.NotificationStatus.WARNING,
            )

    def _on_save_stage_confirm(*args):
        owner._dialog_save_stage.destroy()

        def _on_save_done(a, b):
            if a:
                owner._spawn(_async_load(), "scene_load_after_save")

        omni.kit.window.file.save_as(False, on_save_done=_on_save_done)

    def _on_save_stage_cancel(*args):
        owner._dialog_save_stage.destroy()
        owner._spawn(_async_load(), "scene_load_discard")

    if stage_has_content:
        dialog = MessageDialog(
            title="Save Stage",
            message="Save this stage before loading the selected scene?",
            ok_label="Ok",
            cancel_label="Discard",
            ok_handler=_on_save_stage_confirm,
            cancel_handler=_on_save_stage_cancel,
        )
        owner._dialog_save_stage = dialog
        dialog.show()
    else:
        owner._spawn(_async_load(), "scene_load")

