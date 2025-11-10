import carb

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

    @property
    def is_logged_in(self) -> bool:
        """Determines if the user is logged in based on the token."""
        return bool(self.token)

# Create a single, shared instance of the application state
APP_STATE = AppState()
