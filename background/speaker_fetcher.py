from PyQt6.QtCore import QThread, pyqtSignal

class SpeakerFetcher(QThread):
    finished = pyqtSignal(str, str, list) # model_name, status, speakers
    error = pyqtSignal(str)

    def __init__(self, model_name):
        super().__init__()
        self.model_name = model_name

    def run(self):
        try:
            from TTS.api import TTS
            # Initialize TTS just to peek at speakers (gpu=False for speed/silence)
            tts = TTS(model_name=self.model_name, progress_bar=False, gpu=False)
            
            if tts.is_multi_speaker:
                speakers = []
                # 1. Standard TTS models
                if hasattr(tts, "speakers") and tts.speakers:
                    speakers = tts.speakers
                # 2. Some models put it in speaker_manager directly
                elif hasattr(tts, "speaker_manager") and tts.speaker_manager:
                     if hasattr(tts.speaker_manager, "speaker_names"):
                        speakers = list(tts.speaker_manager.speaker_names)
                     elif hasattr(tts.speaker_manager, "name_to_id"):
                        # Handle both dict (keys) and dict_keys object
                        val = tts.speaker_manager.name_to_id
                        speakers = list(val.keys()) if isinstance(val, dict) else list(val)
                # 3. XTTS specific location (synthesizer -> tts_model -> speaker_manager)
                elif hasattr(tts, "synthesizer") and hasattr(tts.synthesizer, "tts_model"):
                     if hasattr(tts.synthesizer.tts_model, "speaker_manager"):
                          sm = tts.synthesizer.tts_model.speaker_manager
                          if hasattr(sm, "speaker_names"):
                               speakers = list(sm.speaker_names)
                          elif hasattr(sm, "name_to_id"):
                               val = sm.name_to_id
                               speakers = list(val.keys()) if isinstance(val, dict) else list(val)
                
                self.finished.emit(self.model_name, "multi", speakers)

                self.finished.emit(self.model_name, "multi", speakers)
            else:
                self.finished.emit(self.model_name, "single", [])
        except Exception as e:
            self.error.emit(str(e))
