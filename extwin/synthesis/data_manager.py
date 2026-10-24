from __future__ import annotations

import asyncio
import threading
from typing import Any, Optional

import aiohttp
import carb

from .app_state import APP_STATE

HTTP_SUCCESS = 200
BUSINESS_SUCCESS = 200
TOKEN_EXPIRED_CODE = 401
TOKEN_EXPIRED_MESSAGE = "Token has expired"


class DataManagerError(Exception):
    pass


class HTTPException(DataManagerError):
    pass


class BusinessLogicException(DataManagerError):
    pass


class DataParsingException(DataManagerError):
    pass


class DataManager:
    """Shared aiohttp session for the synthesis API. URL choice lives in catalog."""

    _instance: Optional["DataManager"] = None
    _init_lock = threading.Lock()
    _session_lock = asyncio.Lock()

    def __new__(cls, *args, **kwargs):
        if cls._instance is not None:
            return cls._instance
        with cls._init_lock:
            if cls._instance is None:
                cls._instance = super(DataManager, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, "_initialized_flag"):
            return
        self.session: Optional[aiohttp.ClientSession] = None
        self._initialized_flag = True

    async def __aenter__(self):
        await self._get_session()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    async def _get_session(self) -> aiohttp.ClientSession:
        async with self._session_lock:
            if self.session is None or self.session.closed:
                timeout = aiohttp.ClientTimeout(total=60 * 2)
                self.session = aiohttp.ClientSession(timeout=timeout)
            return self.session

    async def close(self):
        async with self._session_lock:
            if self.session and not self.session.closed:
                await self.session.close()
                self.session = None

    async def _request(
        self,
        method: str,
        path: str,
        check_business_status: bool = True,
        **kwargs: Any,
    ) -> Any:
        session = await self._get_session()
        headers = kwargs.pop("headers", {})
        headers["Token"] = APP_STATE.token or ""

        try:
            async with session.request(method, path, headers=headers, **kwargs) as response:
                if response.status != HTTP_SUCCESS:
                    error_text = await response.text()
                    carb.log_error(
                        f"[DataManager] HTTP {response.status} for {method} {path}: {error_text}"
                    )
                    raise HTTPException(f"HTTP {response.status}: {error_text}")

                try:
                    json_data = await response.json()
                except aiohttp.ContentTypeError as e:
                    raw_text = await response.text()
                    carb.log_error(
                        f"[DataManager] JSON parse failed for {method} {path}: {raw_text}"
                    )
                    raise DataParsingException(
                        f"Response is not valid JSON. Content-Type: {response.content_type}, Body: {raw_text}"
                    ) from e
                except Exception as e:
                    carb.log_error(f"[DataManager] JSON parse failed for {method} {path}: {e}")
                    raise DataParsingException(f"Unexpected error parsing JSON: {e}") from e

                if check_business_status:
                    error_code = json_data.get("ErrorCode", -1)
                    status_code = json_data.get("StatusCode", -1)
                    message = json_data.get("MessageCode", "Unknown error")
                    if error_code == TOKEN_EXPIRED_CODE:
                        APP_STATE.is_token_expired = True
                        APP_STATE.is_system_admin = False
                        carb.log_error(f"[DataManager] Token expired for {method} {path}.")
                        raise BusinessLogicException(TOKEN_EXPIRED_MESSAGE)

                    if error_code != BUSINESS_SUCCESS or status_code != BUSINESS_SUCCESS:
                        carb.log_error(
                            f"[DataManager] Business error for {method} {path}: "
                            f"ErrorCode={error_code} StatusCode={status_code} Message='{message}'"
                        )
                        raise BusinessLogicException(
                            f"Business Error ErrorCode={error_code} StatusCode={status_code}: {message}"
                        )

                return json_data.get("Result", {})

        except (HTTPException, BusinessLogicException, DataParsingException):
            raise
        except Exception as e:
            carb.log_error(f"[DataManager] Request failed for {method} {path}: {e}")
            raise DataManagerError(
                f"Unexpected error during main API request to {method} {path}."
            ) from e

    async def get_json(self, url: str, params: dict[str, Any] | None = None) -> Any:
        return await self._request("GET", url, params=params)

    async def post_json(self, url: str, payload: dict[str, Any]) -> Any:
        return await self._request("POST", url, json=payload)


DATA_MANAGER = DataManager()
