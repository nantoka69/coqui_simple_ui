import os
import json

class ModelMetaDataCacheManager:
    APP_FOLDER_NAME = "CoquiSimpleUI"
    MODEL_META_DATA_CACHE_FILE_NAME = "mode_meta_data_cache.json"

    def __init__(self):
        self.app_data_dir = os.path.join(os.environ.get('APPDATA', os.getcwd()), self.APP_FOLDER_NAME)
        os.makedirs(self.app_data_dir, exist_ok=True)

        self.cache_path = os.path.join(self.app_data_dir, self.MODEL_META_DATA_CACHE_FILE_NAME)
        self.cache = self.__load_cache()

    def get_model_info(self, model_name):
        return self.cache["models"].get(model_name, {"status": "unknown", "speakers": []})

    def update_model(self, model_name, status, speakers=None):
        if model_name not in self.cache["models"]:
            self.cache["models"][model_name] = {}
        self.cache["models"][model_name]["status"] = status
        if speakers is not None:
            self.cache["models"][model_name]["speakers"] = speakers
        self.__save_cache()

    def sync_models(self, tts_model_names):
        changed = False
        for m in tts_model_names:
            if m not in self.cache["models"]:
                self.cache["models"][m] = {"status": "unknown", "speakers": []}
                changed = True
        if changed:
            self.__save_cache()

    def __load_cache(self):
        if os.path.exists(self.cache_path):
            try:
                with open(self.cache_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except:
                pass
        return {"models": {}}

    def __save_cache(self):
        with open(self.cache_path, "w", encoding="utf-8") as f:
            json.dump(self.cache, f, indent=4)