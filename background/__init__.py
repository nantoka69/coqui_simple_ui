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

def import_and_monkey_patch_torch():
    """Import torch and monkeypatch torch.load to default weights_only to False if not specified.
    This is necessary for PyTorch 2.6+ compatibility with Coqui TTS.
    """
    try:
        import torch
        original_load = torch.load
        def patched_load(*args, **kwargs):
            if 'weights_only' not in kwargs:
                kwargs['weights_only'] = False
            return original_load(*args, **kwargs)
        torch.load = patched_load
    except ImportError:
        pass
