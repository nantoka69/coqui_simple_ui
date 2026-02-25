import os
from PyQt6.QtCore import QThread, pyqtSignal

class ModelFetcher(QThread):
    finished = pyqtSignal(list, list)
    error = pyqtSignal(str)

    def run(self):
        try:
            from TTS.utils.manage import ModelManager
            manager = ModelManager()
            models = manager.list_models()
            
            tts_model_names = [m for m in models if m.startswith("tts_models/")]
            vocoder_model_names = [m for m in models if m.startswith("vocoder_models/")]
            
            processed_tts_model_names = []
            for model_name in tts_model_names:
                if self.__is_loaded(manager, model_name):
                    processed_tts_model_names.append(f"{model_name} [Downloaded]")
                else:
                    processed_tts_model_names.append(model_name)

            self.finished.emit(processed_tts_model_names, vocoder_model_names)
        except Exception as e:
            self.error.emit(str(e))

    def __is_loaded(self, manager, model_name):
        folder_name = model_name.replace("/", "--")
        local_path = os.path.join(manager.output_prefix, folder_name)
        return os.path.exists(os.path.join(local_path, "config.json"))
