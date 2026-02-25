from PyQt6.QtCore import QThread, pyqtSignal

class MetadataFetcher(QThread):
    # model_name, speaker_type (single/multi), is_multilingual, speakers, languages
    finished = pyqtSignal(str, str, bool, list, list)
    error = pyqtSignal(str)

    def __init__(self, model_name):
        super().__init__()
        self.model_name = model_name

    def run(self):
        try:
            from TTS.api import TTS
            # Initialize TTS once to query all metadata
            # cpu=True/gpu=False for speed since we are only peeking at metadata
            tts = TTS(model_name=self.model_name, progress_bar=False, gpu=False)
            
            speaker_type = "multi" if tts.is_multi_speaker else "single"
            speakers = self.__extract_speakers(tts)

            is_multilingual = getattr(tts, "is_multi_lingual", False)
            languages = self.__extract_languages(tts)
                
            self.finished.emit(self.model_name, speaker_type, is_multilingual, speakers, languages)
        except Exception as e:
            self.error.emit(str(e))

    def __extract_languages(self, tts):
        languages = getattr(tts, "languages", [])
        if languages:
            languages = sorted(list(set(languages)))
        else:
            languages = []
        return languages

    def __extract_speakers(self, tts):
        speakers = []
        if tts.is_multi_speaker:
            # Standard TTS models
            if hasattr(tts, "speakers") and tts.speakers:
                speakers = tts.speakers
            # Some models put it in speaker_manager directly
            elif hasattr(tts, "speaker_manager") and tts.speaker_manager:
                 if hasattr(tts.speaker_manager, "speaker_names"):
                    speakers = list(tts.speaker_manager.speaker_names)
                 elif hasattr(tts.speaker_manager, "name_to_id"):
                    val = tts.speaker_manager.name_to_id
                    speakers = list(val.keys()) if isinstance(val, dict) else list(val)
            # XTTS specific location
            elif hasattr(tts, "synthesizer") and hasattr(tts.synthesizer, "tts_model"):
                 if hasattr(tts.synthesizer.tts_model, "speaker_manager"):
                      sm = tts.synthesizer.tts_model.speaker_manager
                      if hasattr(sm, "speaker_names"):
                           speakers = list(sm.speaker_names)
                      elif hasattr(sm, "name_to_id"):
                           val = sm.name_to_id
                           speakers = list(val.keys()) if isinstance(val, dict) else list(val)
        return speakers
