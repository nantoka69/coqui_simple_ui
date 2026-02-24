import os

APP_FOLDER_NAME = "CoquiSimpleUI"
SETTINGS_FILE_NAME = "settings.json"
MODEL_META_DATA_CACHE_FILE_NAME = "mode_meta_data_cache.json"

def __get_app_data_dir():
    base_dir = os.environ.get('APPDATA')
    if not base_dir:
        base_dir = os.getcwd()
    path = os.path.join(base_dir, APP_FOLDER_NAME)
    os.makedirs(path, exist_ok=True)
    return path

APP_DATA_DIR = __get_app_data_dir()
SETTINGS_PATH = os.path.join(APP_DATA_DIR, SETTINGS_FILE_NAME)
MODEL_CACHE_PATH = os.path.join(APP_DATA_DIR, MODEL_META_DATA_CACHE_FILE_NAME)
