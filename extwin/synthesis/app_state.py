class AppState:
    """A simple singleton class to store application state."""

    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(AppState, cls).__new__(cls, *args, **kwargs)
        return cls._instance

    def __init__(self):
        if not hasattr(self, "_initialized"):
            self._initialized = True
            self.token = None
            self.user_info = None
            self.is_token_expired = True
            self.is_system_admin = False

    @property
    def is_logged_in(self) -> bool:
        """Determines if the user is logged in based on the token and user info."""
        return bool(self.token) and bool(self.user_info)

    def apply_login(self, token, user_info) -> bool:
        if not token or not user_info:
            return False
        self.token = token
        self.user_info = user_info
        self.is_token_expired = False
        user_type = user_info.get("UserType", 5)
        self.is_system_admin = user_type <= 2
        return True

# Create a single, shared instance of the application state
APP_STATE = AppState()
