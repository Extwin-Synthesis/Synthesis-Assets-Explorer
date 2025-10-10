# SPDX-FileCopyrightText: Copyright (c) 2022-2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import asyncio
import gc

import carb

from omni.kit.menu.utils import MenuItemDescription, add_menu_items, remove_menu_items, refresh_menu_items
import omni.kit.actions.core

from .window import SynthesisAssetsWindow,ASSETS_EXPLORER_NAME

ACTION_ID = "toggle_assets_explorer"

MENU_NAME = "Extwin"


class Extension(omni.ext.IExt):
    def on_startup(self, ext_id: str):
        carb.log_info("Startting up")
        self.ext_id = ext_id
        # Build Window
        self._window = SynthesisAssetsWindow(False)
        self._window.set_visibility_changed_fn(self._on_visibility_changed)

        # Add Menus
        self.action_registry = omni.kit.actions.core.get_action_registry()
        self.action_registry.register_action(
            ext_id,
            ACTION_ID,
            self._toggle_assets_explorer,
            description=f"Toggle  extwin assets",
        )
        self._menu_items = [
            MenuItemDescription(
                name=ASSETS_EXPLORER_NAME,
                onclick_action=(ext_id, ACTION_ID),
                ticked_fn=self._get_window_visible,
            )
        ]

        add_menu_items(self._menu_items,MENU_NAME)

        # For Dev
        asyncio.ensure_future(self._execute_toggle_action_later())

    def on_shutdown(self):
        carb.log_info("Shutting down")
        remove_menu_items(self._menu_items, MENU_NAME)

        self.action_registry.deregister_action(self.ext_id, ACTION_ID)

        if self._window:
            self._window.clean_up()
            self._window.destroy()
            self._window = None

        gc.collect()

    async def _execute_toggle_action_later(self):
        self.action_registry.execute_action(
            extension_id=self.ext_id, action_id=ACTION_ID
        )

        await omni.kit.app.get_app().next_update_async()

        refresh_menu_items(MENU_NAME)

    def _on_visibility_changed(self, visible):
        refresh_menu_items(MENU_NAME)
        carb.log_info(f"On window visibility changed,current visible:{visible}")

    def _get_window_visible(self):
        return self._window.visible if self._window else False

    def _toggle_assets_explorer(self):
        self._window.visible = not self._window.visible
        carb.log_info(f"Toggle asset window,current visible:{self._window.visible}")
