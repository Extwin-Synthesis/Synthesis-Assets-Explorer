import asyncio
from typing import Optional, Dict, Any, List, Union
import aiohttp
from aiohttp.client import _RequestOptions
import carb
import threading  # Import threading for synchronous lock
from .app_state import APP_STATE

# --- Constants ---
HTTP_SUCCESS = 200
BUSINESS_SUCCESS = 200  # Standard success code for the main backend API
TOKEN_EXPIRED_CODE = 401  # Code for token expiration
TOKEN_EXPIRED_MESSAGE = "Token has expired"

BASE_URL1 = "https://synthesis-server.extwin.com"
BASE_URL2 = "https://multiverse-server.extwin.com"
BASE_URL3 = "https://synthesis.extwin.com"

ASSET_TYPES: list = [
    {
        "Id": "SimReady",
        "Name": "Sim Ready",
        "CategoryListUrl": f"{BASE_URL1}/api/SimReady/GetCategoryList",
        "CategoryListUrlFree": f"{BASE_URL1}/api/Global/GetCategoryList",
        "CategoryListUrlPrivate": f"{BASE_URL1}/api/EnterpriseSimReady/GetCategoryList",
        "CategoryItemContentUrl": f"{BASE_URL1}/api/SimReady/GetSimReadyList",
        "CategoryItemContentUrlFree": f"{BASE_URL1}/api/Global/GetSimReadyList",
        "CategoryItemContentUrlPrivate": f"{BASE_URL1}/api/EnterpriseSimReady/GetSimReadyList",
        "ThumbnailUrl": f"{BASE_URL1}/api/Usd/SimReady/Image",
        "TypeInBrowser": "assets-simready",
        "ModelBusinessType": 1,
    },
    {
        "Id": "Model",
        "Name": "Model",
        "CategoryListUrl": f"{BASE_URL1}/api/Model/GetCategoryList",
        "CategoryListUrlFree": f"{BASE_URL1}/api/Global/GetModelCategoryList",
        "CategoryListUrlPrivate": f"{BASE_URL1}/api/EnterpriseModel/GetCategoryList",
        "CategoryItemContentUrl": f"{BASE_URL1}/api/Model/GetModelList",
        "CategoryItemContentUrlFree": f"{BASE_URL1}/api/Global/GetModelList",
        "CategoryItemContentUrlPrivate": f"{BASE_URL1}/api/EnterpriseModel/GetModelList",
        "ThumbnailUrl": f"{BASE_URL1}/api/Usd/Model/Image",
        "TypeInBrowser": "assets-model",
        "ModelBusinessType": 2,
    },
    {
        "Id": "_3dGS",
        "Name": "3D Gauss Splatting",
        "CategoryListUrl": f"{BASE_URL1}/api/Gs/GetCategoryList",
        "CategoryListUrlFree": f"{BASE_URL1}/api/Global/GetGsCategoryList",
        "CategoryListUrlPrivate": f"{BASE_URL1}/api/EnterpriseGs/GetCategoryList",
        "CategoryItemContentUrl": f"{BASE_URL1}/api/Gs/GetGsList",
        "CategoryItemContentUrlFree": f"{BASE_URL1}/api/Global/GetGsList",
        "CategoryItemContentUrlPrivate": f"{BASE_URL1}/api/EnterpriseGs/GetGsList",
        "ThumbnailUrl": f"{BASE_URL1}/api/Usd/Gs/Image",
        "TypeInBrowser": "assets-gs",
        "ModelBusinessType": 3,
    },
    {
        "Id": "Robot",
        "Name": "Robot",
        "CategoryListUrl": f"{BASE_URL1}/api/Noumen/GetCategoryList",
        "CategoryListUrlFree": f"{BASE_URL1}/api/Global/GetRobotCategoryList",
        "CategoryListUrlPrivate": f"{BASE_URL1}/api/EnterpriseNoumen/GetCategoryList",
        "CategoryItemContentUrl": f"{BASE_URL1}/api/Robot/GetRobotList",
        "CategoryItemContentUrlFree": f"{BASE_URL1}/api/Global/GetRobotList",
        "CategoryItemContentUrlPrivate": f"{BASE_URL1}/api/EnterpriseRobot/GetRobotList",
        "ThumbnailUrl": f"{BASE_URL1}/api/Usd/Robot/Image",
        "TypeInBrowser": "assets-ontology",
        "ModelBusinessType": 5,
    },
    {
        "Id": "Scene",
        "Name": "Scene",
        "CategoryListUrl": f"{BASE_URL1}/api/Scene/GetCategoryList",
        "CategoryListUrlFree": f"{BASE_URL1}/api/Global/GetSceneCategoryList",
        "CategoryListUrlPrivate": f"{BASE_URL1}/api/EnterpriseScene/GetCategoryList",
        "CategoryItemContentUrl": f"{BASE_URL1}/api/Scene/GetSceneList",
        "CategoryItemContentUrlFree": f"{BASE_URL1}/api/Global/GetSceneList",
        "CategoryItemContentUrlPrivate": f"{BASE_URL1}/api/EnterpriseScene/GetSceneList",
        "ThumbnailUrl": f"{BASE_URL1}/api/Usd/Scene/Image",
        "TypeInBrowser": "assets-scene",
        "ModelBusinessType": 6,
    },
]

# --- Custom Exception Classes ---
class DataManagerError(Exception):
    """Base exception for DataManager errors."""

    pass


class HTTPException(DataManagerError):
    """Raised when an HTTP request fails."""

    pass


class BusinessLogicException(DataManagerError):
    """Raised when the main backend API returns a known business logic error."""

    pass


class DataParsingException(DataManagerError):
    """Raised when response data cannot be parsed."""

    pass


# --- Singleton Instance ---
DATA_MANAGER: Optional["DataManager"] = None


class DataManager:
    """
    Manages data fetching using aiohttp, implementing a singleton pattern.
    Provides a context manager for clean resource management.

    - Uses `_request` for the main backend API (adds Token, checks standard error codes).
    """

    _instance: Optional["DataManager"] = None
    # Use threading.Lock for protecting synchronous __new__ (only if needed)
    _init_lock = threading.Lock()
    _session_lock = asyncio.Lock()  # Use asyncio.Lock for async session access

    def __new__(cls, *args, **kwargs):
        """Ensures only one instance of DataManager is created (Thread-safe)."""
        # First check without acquiring lock for performance (common case after init)
        if cls._instance is not None:
            return cls._instance

        # Instance is None or might be in the process of being created.
        with cls._init_lock:  # threading.Lock supports 'with'
            # Double-check pattern
            if cls._instance is None:
                cls._instance = super(DataManager, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        """Initializes the DataManager instance."""
        if hasattr(self, "_initialized_flag"):
            return  # Already initialized

        self.session: Optional[aiohttp.ClientSession] = None
        self._initialized_flag = True
        carb.log_info("[DataManager] Instance initialized.")

    async def __aenter__(self):
        """Async context manager entry. Initializes the shared session."""
        await self._get_session()
        carb.log_info("[DataManager] Entered async context.")
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit. Closes the shared session."""
        await self.close()
        carb.log_info("[DataManager] Exited async context and closed session.")

    async def _get_session(self) -> aiohttp.ClientSession:
        """Gets or creates the shared aiohttp ClientSession, ensuring async safety."""
        async with self._session_lock:
            if self.session is None or self.session.closed:
                carb.log_info(
                    "[DataManager] Creating new shared aiohttp ClientSession."
                )
                timeout = aiohttp.ClientTimeout(total=60 * 2)
                self.session = aiohttp.ClientSession(timeout=timeout)
            return self.session

    async def close(self):
        """Explicitly closes the shared aiohttp ClientSession."""
        async with self._session_lock:
            if self.session and not self.session.closed:
                await self.session.close()
                self.session = None
                carb.log_info("[DataManager] Shared client session closed.")

    async def _request(
        self,
        method: str,
        path: str,
        check_business_status: bool = True,
        **kwargs: Union[_RequestOptions, Dict[str, Any]],
    ) -> Any:
        """Sends an HTTP request to the main backend API endpoints."""
        session = await self._get_session()
        headers = kwargs.pop("headers", {})
        headers["Token"] = APP_STATE.token or ""

        try:
            carb.log_info(f"[DataManager] Sending {method} request to main API: {path}")
            async with session.request(
                method, path, headers=headers, **kwargs
            ) as response:
                carb.log_info(
                    f"[DataManager] Received response for {method} {path}, status: {response.status}"
                )

                if response.status != HTTP_SUCCESS:
                    error_text = await response.text()
                    carb.log_error(
                        f"[DataManager] Main API HTTP Error {response.status} for {method} {path}: {error_text}"
                    )
                    raise HTTPException(f"HTTP {response.status}: {error_text}")

                try:
                    json_data = await response.json()
                    carb.log_info(
                        f"[DataManager] Parsed JSON response for {method} {path}"
                    )
                except aiohttp.ContentTypeError as e:
                    raw_text = await response.text()
                    carb.log_error(
                        f"[DataManager] Failed to parse JSON for {method} {path}. Content-Type: {response.content_type}, Body: {raw_text}"
                    )
                    raise DataParsingException(
                        f"Response is not valid JSON. Content-Type: {response.content_type}, Body: {raw_text}"
                    ) from e
                except Exception as e:
                    carb.log_error(
                        f"[DataManager] Unexpected error parsing JSON for {method} {path}: {e}"
                    )
                    raise DataParsingException(
                        f"Unexpected error parsing JSON: {e}"
                    ) from e

                if check_business_status:
                    error_code = json_data.get("ErrorCode", -1)
                    status_code = json_data.get("StatusCode", -1)
                    message = json_data.get("MessageCode", "Unknown error")
                    if error_code == TOKEN_EXPIRED_CODE:
                        APP_STATE.is_token_expired = True
                        APP_STATE.is_system_admin = False
                        carb.log_error(
                            f"[DataManager] Token expired for {method} {path}."
                        )
                        raise BusinessLogicException(TOKEN_EXPIRED_MESSAGE)

                    if (
                        error_code != BUSINESS_SUCCESS
                        or status_code != BUSINESS_SUCCESS
                    ):
                        carb.log_error(
                            f"[DataManager] Main API Business Logic Error for {method} {path}: "
                            f"ErrorCode={error_code} StatusCode={status_code} Message='{message}'"
                        )
                        raise BusinessLogicException(
                            f"Business Error ErrorCode={error_code} StatusCode={status_code}: {message}"
                        )

                result = json_data.get("Result", {})
                carb.log_info(
                    f"[DataManager] Main API request {method} {path} successful."
                )
                return result

        except (HTTPException, BusinessLogicException, DataParsingException):
            raise
        except Exception as e:
            carb.log_error(
                f"[DataManager] Unexpected error during main API {method} {path}: {str(e)}"
            )
            raise DataManagerError(
                f"Unexpected error during main API request to {method} {path}."
            ) from e

    async def get_category_tree(
        self,
        asset_type_id: str,
        _selected_visibility_tab_id: str = "Public",
    ) -> List[Dict[str, Any]]:
        """Fetches category tree data from the main backend API."""
        selected_asset_type = next(
            (item for item in ASSET_TYPES if item["Id"] == asset_type_id),
            None,
        )
        if not selected_asset_type:
            carb.log_error("Invalid asset type selection.")
            return
        _target_url = ""
        if _selected_visibility_tab_id == "Public":
            if APP_STATE.is_system_admin:
                _target_url = selected_asset_type["CategoryListUrl"]
            else:
                if (not APP_STATE.is_token_expired) and APP_STATE.is_logged_in:
                    _target_url = selected_asset_type["CategoryListUrlPrivate"]
                else:
                    _target_url = selected_asset_type["CategoryListUrlFree"]
        elif _selected_visibility_tab_id == "Private":
            _target_url = selected_asset_type["CategoryListUrlPrivate"]

        _list = await self._request("GET", _target_url)

        if not isinstance(_list, list) or len(_list) < 1:
            carb.log_error("Category list response is not a list.")
            return []
        else:
            _is_system = True if _selected_visibility_tab_id == "Public" else False
            _filtered_list = [x for x in _list if x.get("IsSystem") == _is_system]
            return _filtered_list

    async def get_asset_list(
        self,
        asset_type_id: str,
        params: Dict[str, Any],
        _selected_visibility_tab_id: str = "Public",
    ) -> Dict[str, Any]:
        """Fetches asset list from the main backend API."""
        selected_asset_type = next(
            (item for item in ASSET_TYPES if item["Id"] == asset_type_id),
            None,
        )
        if not selected_asset_type:
            carb.log_error("Invalid asset type selection.")
            return
        _target_url = ""
        if _selected_visibility_tab_id == "Public":
            params["DataType"] = 1  # Public
            if APP_STATE.is_system_admin:
                _target_url = selected_asset_type["CategoryItemContentUrl"]
            else:
                if (not APP_STATE.is_token_expired) and APP_STATE.is_logged_in:
                    _target_url = selected_asset_type["CategoryItemContentUrlPrivate"]
                else:
                    _target_url = selected_asset_type["CategoryItemContentUrlFree"]
        elif _selected_visibility_tab_id == "Private":
            _target_url = selected_asset_type["CategoryItemContentUrlPrivate"]
            params["DataType"] = 2  # Private

        return await self._request("GET", _target_url, params=params)

    async def log_asset_load_record(self, data: dict):
        return await self._request(
            "POST", f"{BASE_URL1}/api/Global/AddLoadRecord", json=data
        )


# Create the global singleton instance
DATA_MANAGER = DataManager()
