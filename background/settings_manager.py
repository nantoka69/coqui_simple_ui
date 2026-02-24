import os
import json
from . import SETTINGS_PATH

class SettingsManager:

    def __init__(self):
        self.settings = self.__load_settings()

    def get_setting(self, key, default=None):
        return self.settings.get(key, default)

    def set_setting(self, key, value):
        self.settings[key] = value
        self.__save_settings()

    def __load_settings(self):
        if os.path.exists(SETTINGS_PATH):
            try:
                with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
                    return json.load(f)
            except:
                pass
        return {}

    def __save_settings(self):
        try:
            with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
                json.dump(self.settings, f, indent=4)
        except:
            pass
