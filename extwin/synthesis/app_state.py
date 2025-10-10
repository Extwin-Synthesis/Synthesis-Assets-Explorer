import carb
from .aes import encrypt_aes, decrypt_aes
import functools


class AppState:
    """A simple singleton class to store application state."""

    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(AppState, cls).__new__(cls, *args, **kwargs)
        return cls._instance

    def __init__(self):
        if not hasattr(self, "_initialized"):
            self._settings = carb.settings.get_settings()
            self._username_key = "/persistent/exts/synthesis.extwin.com/username"
            self._password_key = "/persistent/exts/synthesis.extwin.com/password"
            self._remember_me_key = "/persistent/exts/synthesis.extwin.com/remember_me"

            self.username = self._settings.get(self._username_key)
            self.password = decrypt_aes(self._settings.get(self._password_key))
            self.remember_me = self._settings.get(self._remember_me_key)
            self._initialized = True
            self.token = None
            self.user_info = None
            carb.log_info(f"Loaded persistent settings: username={self.username}")

    @property
    def is_logged_in(self) -> bool:
        """Determines if the user is logged in based on the token."""
        return bool(self.token)

    def login(self, token: str, username: str, loginuserinfo: dict):
        """Saves login state."""
        self.token = token
        self.user_info = loginuserinfo  # self.user_info["UserType"]: 1-Super Admin, 2-System Admin, 3-Enterprise Admin, 4-Regular Member, 5-Registered User
        self.username = username
        self._settings.set(self._username_key, username)

    def save_credentials(self, username: str, password: str, remember_me: bool):
        """Saves user credentials if 'Remember Me' is checked."""
        self.username = username
        self.password = password
        self.remember_me = remember_me
        self._settings.set(self._username_key, self.username)
        # Encrypt password before saving
        self._settings.set(self._password_key, encrypt_aes(password))
        self._settings.set(self._remember_me_key, self.remember_me)

    def logout(self):
        """Clears login state."""
        self.token = None
        self.user_info = None
        # Do not clear username and password if "remember me" is active
        if not self.remember_me:
            self.username = None
            self.password = None
            self._settings.set(self._username_key, "")
            self._settings.set(self._password_key, "")
            self._settings.set(self._remember_me_key, False)


# Create a single, shared instance of the application state
APP_STATE = AppState()
