import sys
import os
import re
from PyQt6.QtCore import QThread, pyqtSignal
from background.stream_redirector import StreamRedirector

class TTSWorker(QThread):
    finished = pyqtSignal(str)
    error = pyqtSignal(str)
    log_signal = pyqtSignal(str, bool) # Added bool for 'replace last line'

    def __init__(self, text, model_name, vocoder_name, speaker_wav, speaker_id, language, is_multilingual, output_path):
        super().__init__()
        self.text = text
        self.model_name = model_name
        self.vocoder_name = vocoder_name
        self.speaker_wav = speaker_wav
        self.speaker_id = speaker_id
        self.language = language
        self.is_multilingual = is_multilingual
        self.output_path = output_path

    def run(self):
        try:
            from TTS.api import TTS
            import numpy as np
            import torch
            self.__monkey_patch_torch_load(torch)
            
            # Redirect stdout/stderr for this thread
            sys.stdout = StreamRedirector(self.log_signal)
            sys.stderr = sys.stdout
            
            tts = TTS(model_name=self.model_name, vocoder_path=self.vocoder_name if self.vocoder_name else None)
            
            sentences = self.__split_into_sentences(self.text)
            
            total = len(sentences)
            self.log_signal.emit(f"<b>[STATUS]</b> Identified {total} segments for processing.", False)
            
            all_wavs = []
            
            use_speaker_wav, use_speaker_id = self.__do_speaker_selection(tts)

            for i, sentence in enumerate(sentences):
                # Emit with 'replace=True' to keep the console clean
                self.log_signal.emit(f"<b>[PROG]</b> Processing segment {i+1}/{total}...", True)
                
                # tts.tts handles both speaker (ID) and speaker_wav (file)
                # We dynamically pass the language for XTTS if it's multilingual
                if self.is_multilingual:
                    wav = tts.tts(text=sentence, speaker=use_speaker_id, speaker_wav=use_speaker_wav, language=self.language)
                else:
                    wav = tts.tts(text=sentence, speaker=use_speaker_id, speaker_wav=use_speaker_wav)
                
                all_wavs.append(wav)
            
            self.log_signal.emit(f"<b>[STATUS]</b> Synthesis complete. Concatenating {len(all_wavs)} waves...", False)
            combined_wav = np.concatenate(all_wavs)
            
            # Save using the synthesizer's method (handles sample rate correctly)
            tts.synthesizer.save_wav(combined_wav, self.output_path)
            
            self.finished.emit(self.output_path)
        except Exception as e:
            self.error.emit(str(e))
        finally:
            sys.stdout = None
            sys.stderr = None

    def __split_into_sentences(self, text):
        """Split text into sentences/segments using an aggressive regex."""
        segments = re.split(r'[\n\r]+|(?<=[.!?])\s+', text)
        return [s.strip() for s in segments if s.strip()]

    def __monkey_patch_torch_load(self, torch):
        """Monkeypatch torch.load to default weights_only to False if not specified."""
        # This is strictly necessary for PyTorch 2.6+ compatibility with Coqui TTS
        original_load = torch.load
        def patched_load(*args, **kwargs):
            if 'weights_only' not in kwargs:
                kwargs['weights_only'] = False
            return original_load(*args, **kwargs)
        torch.load = patched_load

    def __do_speaker_selection(self, tts):
        """Determine the speaker reference or ID to use for synthesis."""
        use_speaker_wav = None
        use_speaker_id = None
        
        if tts.is_multi_speaker:
            if self.speaker_wav and os.path.exists(self.speaker_wav):
                use_speaker_wav = self.speaker_wav
                self.log_signal.emit(f"<b>[STATUS]</b> Using speaker reference: {os.path.basename(use_speaker_wav)}", False)
            elif self.speaker_id:
                use_speaker_id = self.speaker_id
                self.log_signal.emit(f"<b>[STATUS]</b> Using internal speaker: {use_speaker_id}", False)
            else:
                # Try to find a default speaker ID
                if hasattr(tts, "speakers") and tts.speakers:
                    use_speaker_id = tts.speakers[0]
                elif "xtts" in self.model_name.lower():
                    use_speaker_id = "Claribel Dervla"
                
                if use_speaker_id:
                    self.log_signal.emit(f"<b>[STATUS]</b> Using default speaker ID: {use_speaker_id}", False)
                else:
                    self.log_signal.emit("<b>[WARNING]</b> Multi-speaker model detected but no speaker reference or ID found. It might fail.", False)
        
        return use_speaker_wav, use_speaker_id
