from __future__ import annotations

from typing import Callable

import carb
import omni.kit.notification_manager as nm
from aiohttp import web

LOGIN_RESULT_LISTEN_PORT = 8090
ALLOWED_ORIGINS = {
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "https://synthesis.extwin.com",
}


class LoginListener:
    def __init__(self, on_login: Callable[[str, dict], None]):
        self._on_login = on_login
        self._runner: web.AppRunner | None = None

    async def start(self) -> None:
        await self.stop()
        app = web.Application()
        app.router.add_options("/", self._handle_cors_preflight)
        app.router.add_post("/", self._handle_receive_login_result)
        self._runner = web.AppRunner(app)
        await self._runner.setup()
        site = web.TCPSite(self._runner, "127.0.0.1", LOGIN_RESULT_LISTEN_PORT)
        try:
            await site.start()
            carb.log_info(f"Login listener on 127.0.0.1:{LOGIN_RESULT_LISTEN_PORT}")
        except OSError as e:
            carb.log_warn(f"Login listener start failed: {e}")

    async def stop(self) -> None:
        runner = self._runner
        self._runner = None
        if runner is None:
            return
        try:
            await runner.cleanup()
        except Exception as e:
            carb.log_warn(f"Ignore web runner cleanup error: {e}")

    async def _handle_cors_preflight(self, request: web.Request) -> web.Response:
        origin = request.headers.get("Origin")
        if origin not in ALLOWED_ORIGINS:
            return web.Response(status=403)
        return web.Response(
            status=204,
            headers={
                "Access-Control-Allow-Origin": origin,
                "Access-Control-Allow-Methods": "POST, OPTIONS",
                "Access-Control-Allow-Headers": "Content-Type",
            },
        )

    async def _handle_receive_login_result(self, request: web.Request) -> web.Response:
        origin = str(request.headers.get("Origin")).lower()
        if origin not in ALLOWED_ORIGINS:
            return web.json_response(
                {"error": "Origin not allowed"},
                status=403,
                headers={"Access-Control-Allow-Origin": origin},
            )
        try:
            data = await request.json()
        except Exception as e:
            carb.log_error(f"Failed to parse login result JSON: {e}")
            return web.json_response(
                {"error": "Invalid JSON"},
                status=400,
                headers={"Access-Control-Allow-Origin": origin},
            )

        token = data.get("Token")
        login_user_info = data.get("LoginUserInfo")
        if token and login_user_info:
            self._on_login(token, login_user_info)
            return web.json_response(
                {"status": "success"},
                headers={"Access-Control-Allow-Origin": origin},
            )

        carb.log_warn("Login result missing Token or LoginUserInfo")
        nm.post_notification(
            "Invalid auth info format.",
            duration=2.0,
            status=nm.NotificationStatus.WARNING,
        )
        return web.json_response(
            {"error": "Missing Token or UserInfo"},
            status=400,
            headers={"Access-Control-Allow-Origin": origin},
        )
