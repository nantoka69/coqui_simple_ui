import os
import json
from . import MODEL_CACHE_PATH

class ModelMetaDataCacheManager:

    def __init__(self):
        self.cache = self.__load_cache()

    def get_model_info(self, model_name):
        info = self.cache["models"].get(model_name, {})
        return {
            "status": info.get("status", "unknown"),
            "speaker_type": info.get("speaker_type", "single"),
            "is_multilingual": info.get("is_multilingual", False),
            "speakers": info.get("speakers", []),
            "languages": info.get("languages", [])
        }

    def update_model_metadata(self, model_name, speaker_type, is_multilingual, speakers, languages):
        self.cache["models"][model_name] = {
            "status": "known",
            "speaker_type": speaker_type,
            "is_multilingual": is_multilingual,
            "speakers": speakers,
            "languages": languages
        }
        self.__save_cache()

    def sync_models(self, tts_model_names):
        changed = False
        for m in tts_model_names:
            if m not in self.cache["models"]:
                self.cache["models"][m] = {
                    "status": "unknown", 
                    "speaker_type": "single",
                    "is_multilingual": False,
                    "speakers": [],
                    "languages": []
                }
                changed = True
        if changed:
            self.__save_cache()

    def __load_cache(self):
        if os.path.exists(MODEL_CACHE_PATH):
            try:
                with open(MODEL_CACHE_PATH, "r", encoding="utf-8") as f:
                    return json.load(f)
            except:
                pass
        return {"models": {}}

    def __save_cache(self):
        with open(MODEL_CACHE_PATH, "w", encoding="utf-8") as f:
            json.dump(self.cache, f, indent=4)
