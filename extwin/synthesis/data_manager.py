import asyncio
from typing import Optional, Dict, Any, List, Union
import aiohttp
from aiohttp.client import _RequestOptions
import carb
import threading # Import threading for synchronous lock
from .app_state import APP_STATE

# --- Constants ---
HTTP_SUCCESS = 200
BUSINESS_SUCCESS = 200 # Standard success code for the main backend API


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
DATA_MANAGER: Optional['DataManager'] = None


class DataManager:
    """
    Manages data fetching using aiohttp, implementing a singleton pattern.
    Provides a context manager for clean resource management.

    - Uses `_request` for the main backend API (adds Token, checks standard error codes).
    - Uses dedicated methods (like `get_query_usd_path`) for other API endpoints
      with potentially different protocols or response formats.
    """

    _instance: Optional['DataManager'] = None
    # Use threading.Lock for protecting synchronous __new__ (only if needed)
    _init_lock = threading.Lock()
    _session_lock = asyncio.Lock() # Use asyncio.Lock for async session access

    def __new__(cls, *args, **kwargs):
        """Ensures only one instance of DataManager is created (Thread-safe)."""
        # First check without acquiring lock for performance (common case after init)
        if cls._instance is not None:
            return cls._instance

        # Instance is None or might be in the process of being created.
        with cls._init_lock: # threading.Lock supports 'with'
            # Double-check pattern
            if cls._instance is None:
                cls._instance = super(DataManager, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        """Initializes the DataManager instance."""
        if hasattr(self, '_initialized_flag'):
            return # Already initialized

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
                carb.log_info("[DataManager] Creating new shared aiohttp ClientSession.")
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
        self, method: str, path: str, check_business_status: bool = True, **kwargs: Union[_RequestOptions, Dict[str, Any]]
    ) -> Any:
        """Sends an HTTP request to the main backend API endpoints."""
        session = await self._get_session()
        headers = kwargs.pop("headers", {})
        headers["Token"] = APP_STATE.token or ""

        try:
            carb.log_info(f"[DataManager] Sending {method} request to main API: {path}") # Changed from log_debug
            async with session.request(method, path, headers=headers, **kwargs) as response:
                carb.log_info(f"[DataManager] Received response for {method} {path}, status: {response.status}") # Changed from log_debug

                if response.status != HTTP_SUCCESS:
                    error_text = await response.text()
                    carb.log_error(f"[DataManager] Main API HTTP Error {response.status} for {method} {path}: {error_text}")
                    raise HTTPException(f"HTTP {response.status}: {error_text}")

                try:
                    json_data = await response.json()
                    carb.log_info(f"[DataManager] Parsed JSON response for {method} {path}") # Changed from log_debug
                except aiohttp.ContentTypeError as e:
                    raw_text = await response.text()
                    carb.log_error(f"[DataManager] Failed to parse JSON for {method} {path}. Content-Type: {response.content_type}, Body: {raw_text}")
                    raise DataParsingException(f"Response is not valid JSON. Content-Type: {response.content_type}, Body: {raw_text}") from e
                except Exception as e:
                    carb.log_error(f"[DataManager] Unexpected error parsing JSON for {method} {path}: {e}")
                    raise DataParsingException(f"Unexpected error parsing JSON: {e}") from e

                if check_business_status:
                    error_code = json_data.get("ErrorCode", -1)
                    status_code = json_data.get("StatusCode", -1)
                    message = json_data.get("MessageCode", "Unknown error")

                    if error_code != BUSINESS_SUCCESS or status_code != BUSINESS_SUCCESS:
                        carb.log_error(
                            f"[DataManager] Main API Business Logic Error for {method} {path}: "
                            f"ErrorCode={error_code} StatusCode={status_code} Message='{message}'"
                        )
                        raise BusinessLogicException(
                            f"Business Error ErrorCode={error_code} StatusCode={status_code}: {message}"
                        )

                result = json_data.get("Result", {})
                carb.log_info(f"[DataManager] Main API request {method} {path} successful.") # Changed from log_debug
                return result

        except (HTTPException, BusinessLogicException, DataParsingException):
            raise
        except Exception as e:
            carb.log_error(f"[DataManager] Unexpected error during main API {method} {path}: {str(e)}")
            raise DataManagerError(f"Unexpected error during main API request to {method} {path}.") from e

    # --- Methods for Main Backend API Endpoints ---

    async def login(self, url: str, username: str, password: str) -> Dict[str, Any]:
        """Performs user login to the main backend API."""
        return await self._request("POST", url, json={"LoginAccount": username, "LoginPwd": password})

    async def get_category_tree(self, path: str) -> List[Dict[str, Any]]:
        """Fetches category tree data from the main backend API."""
        return await self._request("GET", path)

    async def get_asset_list(self, path: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Fetches asset list from the main backend API."""
        return await self._request("GET", path, params=params)

    # --- Methods for Other/Specific API Endpoints ---

    async def get_query_usd_path(self, other_endpoint_url: str) -> Optional[str]:
        """
        Queries a USD path from a different API endpoint.
        Does NOT automatically add the standard 'Token' header.
        Uses a temporary session.
        """
        timeout = aiohttp.ClientTimeout(total=60)
        try:
            async with aiohttp.ClientSession(timeout=timeout) as temp_session:
                carb.log_info(f"[DataManager] Querying USD path from other endpoint: {other_endpoint_url}")
                async with temp_session.get(other_endpoint_url) as response:
                    carb.log_info(f"[DataManager] Received response from other endpoint, status: {response.status}")

                    if response.status != HTTP_SUCCESS:
                        error_text = await response.text()
                        carb.log_error(f"[DataManager] Other Endpoint HTTP Error {response.status}: {error_text}")
                        return None

                    raw_text = await response.text()
                    carb.log_info(f"[DataManager] Raw response text from other endpoint: {raw_text}") # Changed from log_debug

                    try:
                        result = await response.json()
                    except aiohttp.ContentTypeError:
                        carb.log_error(
                            f"[DataManager] Other Endpoint response is not valid JSON. "
                            f"Content-Type: {response.content_type}, Body: {raw_text}"
                        )
                        return None

                    if isinstance(result, list) and len(result) > 0:
                        usd_path = result[0]
                        if isinstance(usd_path, str) and usd_path:
                            carb.log_info(f"[DataManager] USD path retrieved from other endpoint: {usd_path}")
                            return usd_path
                        else:
                            carb.log_warn(f"[DataManager] USD path query returned invalid/empty path at index 0: {usd_path}")
                            return None
                    else:
                        carb.log_warn(f"[DataManager] USD path query returned empty list or non-list: {result}")
                        return None

        except aiohttp.ClientError as e:
            carb.log_error(f"[DataManager] Network error querying other endpoint {other_endpoint_url}: {e}")
            return None
        except Exception as e:
            carb.log_error(f"[DataManager] Unexpected error querying other endpoint {other_endpoint_url}: {e}")
            return None


# Create the global singleton instance
DATA_MANAGER = DataManager()




