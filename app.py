import sys
import os
import re
import collections
import json
from PyQt6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout, 
                             QTextEdit, QPushButton, QLabel, QMessageBox, 
                             QSplashScreen, QComboBox, QFileDialog, QLineEdit, QFormLayout,
                             QStackedWidget)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QPixmap, QColor, QLinearGradient, QPainter, QFont

# --- Config Management ---
class ConfigManager:
    def __init__(self):
        self.app_data_dir = os.path.join(os.environ.get('APPDATA', os.getcwd()), "CoquiSimpleUI")
        os.makedirs(self.app_data_dir, exist_ok=True)
        self.cache_path = os.path.join(self.app_data_dir, "models_cache.json")
        self.cache = self.load_cache()

    def load_cache(self):
        if os.path.exists(self.cache_path):
            try:
                with open(self.cache_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except:
                pass
        return {"models": {}}

    def save_cache(self):
        with open(self.cache_path, "w", encoding="utf-8") as f:
            json.dump(self.cache, f, indent=4)

    def get_model_info(self, model_name):
        return self.cache["models"].get(model_name, {"status": "unknown", "speakers": []})

    def update_model(self, model_name, status, speakers=None):
        if model_name not in self.cache["models"]:
            self.cache["models"][model_name] = {}
        self.cache["models"][model_name]["status"] = status
        if speakers is not None:
            self.cache["models"][model_name]["speakers"] = speakers
        self.save_cache()

    def sync_models(self, t_models):
        changed = False
        for m in t_models:
            if m not in self.cache["models"]:
                self.cache["models"][m] = {"status": "unknown", "speakers": []}
                changed = True
        if changed:
            self.save_cache()

class ModelFetcher(QThread):
    finished = pyqtSignal(list, list)
    error = pyqtSignal(str)

    def run(self):
        try:
            from TTS.utils.manage import ModelManager
            manager = ModelManager()
            models = manager.list_models()
            
            t_models = [m for m in models if m.startswith("tts_models/")]
            v_models = [m for m in models if m.startswith("vocoder_models/")]
            
            # Identify which models are already local
            def is_local(m_name):
                folder_name = m_name.replace("/", "--")
                local_path = os.path.join(manager.output_prefix, folder_name)
                return os.path.exists(os.path.join(local_path, "config.json"))

            processed_t = []
            for m in t_models:
                if is_local(m):
                    processed_t.append(f"{m} [Loaded]")
                else:
                    processed_t.append(m)

            self.finished.emit(processed_t, v_models)
        except Exception as e:
            self.error.emit(str(e))

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



class StreamRedirector:
    def __init__(self, signal):
        self.signal = signal
        # More robust regex for stripping ANSI escape sequences
        self.ansi_escape = re.compile(r'(?:\x1B[@-_]|[\x80-\x9F])[0-?]*[ -/]*[@-~]')

    def write(self, text):
        # Strip ANSI codes
        clean_text = self.ansi_escape.sub('', text)
        if not clean_text:
            return

        # Split by newline first
        lines = clean_text.split('\n')
        
        for i, line in enumerate(lines):
            is_last = (i == len(lines) - 1)
            
            # Handle carriage returns within the segment
            if '\r' in line:
                parts = line.split('\r')
                # Take the last non-empty part to show current progress
                display_line = next((p for p in reversed(parts) if p), "")
                # If we have a trailing \r or the specific content contains a \r, mark for replacement
                replace = True
            else:
                display_line = line
                replace = False
            
            # Emit if there's content or it's a newline (not the last empty segment)
            if display_line or (not is_last):
                self.signal.emit(display_line, replace)

    def flush(self):
        pass

class TTSWorker(QThread):
    finished = pyqtSignal(str)
    error = pyqtSignal(str)
    log_signal = pyqtSignal(str, bool) # Added bool for 'replace last line'

    def __init__(self, text, model_name, vocoder_name, speaker_wav, output_path):
        super().__init__()
        self.text = text
        self.model_name = model_name
        self.vocoder_name = vocoder_name
        self.speaker_wav = speaker_wav
        self.speaker_id = None # Set externally
        self.output_path = output_path

    def run(self):
        try:
            from TTS.api import TTS
            import torch
            
            # Definitive fix for PyTorch 2.6+ weights_only issue:
            # Monkeypatch torch.load to default weights_only to False if not specified.
            # This is necessary because Coqui TTS (and many other libraries)
            # were written before this security feature and don't yet pass weights_only=False.
            original_load = torch.load
            def patched_load(*args, **kwargs):
                if 'weights_only' not in kwargs:
                    kwargs['weights_only'] = False
                return original_load(*args, **kwargs)
            torch.load = patched_load
            
            # Redirect stdout/stderr for this thread
            sys.stdout = StreamRedirector(self.log_signal)
            sys.stderr = sys.stdout
            
            tts = TTS(model_name=self.model_name, vocoder_path=self.vocoder_name if self.vocoder_name else None)
            
            # Use a more aggressive regex to split into sentences/segments
            # Splits on one or more newlines, or on .!? followed by whitespace
            sentences = re.split(r'[\n\r]+|(?<=[.!?])\s+', self.text)
            sentences = [s.strip() for s in sentences if s.strip()]
            
            total = len(sentences)
            self.log_signal.emit(f"<b>[STATUS]</b> Identified {total} segments for processing.", False)
            
            all_wavs = []
            import numpy as np
            
            # Smart speaker selection for multi-speaker models
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

            for i, sentence in enumerate(sentences):
                # Emit with 'replace=True' to keep the console clean
                self.log_signal.emit(f"<b>[PROG]</b> Processing segment {i+1}/{total}...", True)
                # tts.tts handles both speaker (ID) and speaker_wav (file)
                # We dynamically pass the language for XTTS if it's multilingual
                language = "en" # Default to English, could be made a setting later
                if "multilingual" in self.model_name.lower() or "xtts" in self.model_name.lower():
                    wav = tts.tts(text=sentence, speaker=use_speaker_id, speaker_wav=use_speaker_wav, language=language)
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

class MainWindow(QWidget):
    def __init__(self, t_models, v_models):
        super().__init__()
        self.t_models = t_models
        self.v_models = v_models
        self.config = ConfigManager()
        # Sync current model list with cache
        clean_models = [m.replace(" [Loaded]", "") for m in t_models]
        self.config.sync_models(clean_models)
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle("Coqui TTS Simple UI")
        self.setMinimumWidth(600)

        layout = QVBoxLayout()

        # Text input
        layout.addWidget(QLabel("Enter text to speak:"))
        self.text_edit = QTextEdit()
        self.text_edit.setPlaceholderText("Type something here...")
        layout.addWidget(self.text_edit)

        # Settings Form
        form_layout = QFormLayout()

        # Model Selection
        self.combo_model = QComboBox()
        self.combo_model.setEditable(False)
        for m in self.t_models:
             # Store real name in userData
             real_name = m.replace(" [Loaded]", "")
             self.combo_model.addItem(m, real_name)
        
        # Default to a common model
        default_idx = self.combo_model.findText("tts_models/en/ljspeech/vits [Loaded]")
        if default_idx == -1:
            default_idx = self.combo_model.findText("tts_models/en/ljspeech/vits")
        if default_idx >= 0:
            self.combo_model.setCurrentIndex(default_idx)
        self.combo_model.currentIndexChanged.connect(self.on_model_changed)
        form_layout.addRow("Model:", self.combo_model)

        # Vocoder Selection
        self.combo_vocoder = QComboBox()
        self.combo_vocoder.setEditable(False)
        self.combo_vocoder.addItem("") # Optional
        self.combo_vocoder.addItems(self.v_models)
        form_layout.addRow("Vocoder (Optional):", self.combo_vocoder)

        # Dynamic Speaker Selection Area
        self.speaker_stack = QStackedWidget()
        
        # Page 0: Load Button
        self.btn_load_speakers = QPushButton("Load speaker IDs if available")
        self.btn_load_speakers.clicked.connect(self.on_load_speakers_clicked)
        self.speaker_stack.addWidget(self.btn_load_speakers)
        
        # Page 1: Speaker Combo
        self.combo_internal_speaker = QComboBox()
        self.speaker_stack.addWidget(self.combo_internal_speaker)
        
        # Page 2: Single Speaker Label
        self.lbl_single_speaker = QLabel("Single speaker model")
        self.lbl_single_speaker.setStyleSheet("color: #9ca3af; font-style: italic;")
        self.speaker_stack.addWidget(self.lbl_single_speaker)
        
        form_layout.addRow("Speaker (Internal):", self.speaker_stack)

        # Speaker Wave (for cloning)
        speaker_layout = QHBoxLayout()
        self.edit_speaker = QLineEdit()
        self.edit_speaker.setPlaceholderText("Optional WAV for voice cloning")
        self.btn_browse_speaker = QPushButton("Browse...")
        self.btn_browse_speaker.clicked.connect(self.browse_speaker)
        speaker_layout.addWidget(self.edit_speaker)
        speaker_layout.addWidget(self.btn_browse_speaker)
        form_layout.addRow("Speaker Reference (External WAV):", speaker_layout)


        # Output File
        output_layout = QHBoxLayout()
        self.edit_output = QLineEdit(os.path.join(os.getcwd(), "output.wav"))
        self.btn_browse_output = QPushButton("Browse...")
        self.btn_browse_output.clicked.connect(self.browse_output)
        self.btn_play = QPushButton("▶ Play")
        self.btn_play.setToolTip("Play the selected output file")
        self.btn_play.clicked.connect(self.play_audio)
        
        output_layout.addWidget(self.edit_output)
        output_layout.addWidget(self.btn_browse_output)
        output_layout.addWidget(self.btn_play)
        form_layout.addRow("Output File:", output_layout)

        layout.addLayout(form_layout)

        # Generate Button
        self.btn_generate = QPushButton("Generate Speech")
        self.btn_generate.setStyleSheet("padding: 15px; font-size: 14pt; font-weight: bold; background-color: #1e40af; color: white; border-radius: 5px;")
        self.btn_generate.clicked.connect(self.on_generate_clicked)
        layout.addWidget(self.btn_generate)

        # Console Output Window
        layout.addWidget(QLabel("Console Output:"))
        self.console_output = QTextEdit()
        self.console_output.setReadOnly(True)
        self.console_output.setMinimumHeight(150)
        self.console_output.setStyleSheet("""
            background-color: #000000;
            color: #00ff00;
            font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
            font-size: 10pt;
            border: 1px solid #333333;
            border-radius: 4px;
        """)
        layout.addWidget(self.console_output)

        self.setLayout(layout)
        # Trigger initial speaker UI state
        self.on_model_changed()
        self.log("Ready")

    def log(self, message, color="#00ff00", replace=False, is_lib=False):
        """Append a message to the console window. If replace=True, replaces the last block."""
        
        # 1. Escape HTML special characters in the raw message content
        # This prevents characters like < and > in progress bars from being eaten by Qt's HTML renderer
        clean_msg = message.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        
        # 2. Add formatting (bold tags, prefixes) AFTER escaping the content
        if is_lib:
            formatted_msg = f'<b>[LIB]</b> {clean_msg}'
        else:
            formatted_msg = clean_msg # Already contains tags if it was one of our <b>[STATUS]</b> logs

        cursor = self.console_output.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        
        if replace:
            # Shift selection to the start of the current last block (logical paragraph)
            # This handles wrapped lines correctly, unlike StartOfLine
            cursor.movePosition(cursor.MoveOperation.StartOfBlock, cursor.MoveMode.KeepAnchor)
            
            if cursor.hasSelection():
                # OVERWRITE the selected block using insertHtml instead of remove + append
                # This prevents the accumulation of empty paragraph blocks
                cursor.insertHtml(f'<span style="color: {color}; font-family: \'Consolas\', \'Monaco\', \'Courier New\', monospace;">{formatted_msg}</span>')
                return

        self.console_output.append(f'<span style="color: {color};">{formatted_msg}</span>')
        # Auto-scroll to bottom
        self.console_output.moveCursor(self.console_output.textCursor().MoveOperation.End)

    def on_model_changed(self):
        model_name = self.combo_model.currentData()
        if not model_name:
            return
            
        info = self.config.get_model_info(model_name)
        status = info["status"]
        
        if status == "unknown":
            self.speaker_stack.setCurrentIndex(0) # Show Load Button
            self.btn_load_speakers.setText("Load speaker IDs if available")
            self.btn_load_speakers.setEnabled(True)
        elif status == "single":
            self.speaker_stack.setCurrentIndex(2) # Show Label
        elif status == "multi":
            self.speaker_stack.setCurrentIndex(1) # Show Combo
            self.combo_internal_speaker.clear()
            for i, spk in enumerate(info["speakers"]):
                self.combo_internal_speaker.addItem(f"[{i}] {spk}", spk)

    def on_load_speakers_clicked(self):
        model_name = self.combo_model.currentData()
        if not model_name:
            return
            
        self.btn_load_speakers.setText("Loading... (Windows may flash)")
        self.btn_load_speakers.setEnabled(False)
        
        self.fetcher = SpeakerFetcher(model_name)
        self.fetcher.finished.connect(self.on_speakers_fetched)
        self.fetcher.error.connect(self.on_speaker_error)
        self.fetcher.start()

    def on_speakers_fetched(self, model_name, status, speakers):
        self.config.update_model(model_name, status, speakers)
        # If the currently selected model is still this one, update UI
        if self.combo_model.currentData() == model_name:
            self.on_model_changed()

    def on_speaker_error(self, err):
        QMessageBox.warning(self, "Load Error", f"Could not load speaker list:\n{err}")
        self.on_model_changed()

    def log_input(self, model, vocoder, speaker, output, text):
        """Log the command configuration."""
        self.log("\n--- Starting TTS Task ---", "#60a5fa")
        self.log(f"<b>[INPUT]</b> Model: {model}", "#60a5fa")
        if vocoder:
            self.log(f"<b>[INPUT]</b> Vocoder: {vocoder}", "#60a5fa")
        if speaker:
            self.log(f"<b>[INPUT]</b> Speaker Ref: {speaker}", "#60a5fa")
        self.log(f"<b>[INPUT]</b> Output Path: {output}", "#60a5fa")
        self.log(f"<b>[INPUT]</b> Text Length: {len(text)} characters", "#60a5fa")

    def browse_speaker(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Select Speaker Reference", "", "Audio Files (*.wav)")
        if file_path:
            self.edit_speaker.setText(file_path)

    def browse_output(self):
        file_path, _ = QFileDialog.getSaveFileName(self, "Select Output File", self.edit_output.text(), "Audio Files (*.wav)")
        if file_path:
            self.edit_output.setText(file_path)

    def play_audio(self):
        file_path = self.edit_output.text().strip()
        if not file_path or not os.path.exists(file_path):
            QMessageBox.warning(self, "Warning", "Output file does not exist. Generate it first!")
            return
        
        try:
            os.startfile(file_path)
            self.log(f"Playing file: {os.path.basename(file_path)}", "#a78bfa")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not play audio:\n{str(e)}")

    def on_generate_clicked(self):
        text = self.text_edit.toPlainText().strip()
        if not text:
            QMessageBox.warning(self, "Warning", "Please enter some text.")
            return

        model = self.combo_model.currentData()
        vocoder = self.combo_vocoder.currentText().strip()
        speaker_wav = self.edit_speaker.text().strip()
        speaker_id = self.combo_internal_speaker.currentData() if self.speaker_stack.currentIndex() == 1 else None
        output = self.edit_output.text().strip()

        if not model:
            QMessageBox.warning(self, "Warning", "Please select a model.")
            return

        # Explicit validation for missing multi-speaker selection
        info = self.config.get_model_info(model)
        if info["status"] == "unknown":
             # We don't know yet, but if it's XTTS we suspect multi
             if "xtts" in model or "multilingual" in model:
                  QMessageBox.critical(self, "Speaker Required", "Download speaker list and select a speaker index.")
                  return
        elif info["status"] == "multi" and not speaker_id and not speaker_wav:
             QMessageBox.critical(self, "Speaker Required", "Please select a speaker from the dropdown or provide a reference WAV.")
             return

        self.btn_generate.setEnabled(False)
        
        # Determine logical speaker name for logging
        log_speaker = "Default"
        if speaker_wav:
            log_speaker = f"WAV: {os.path.basename(speaker_wav)}"
        elif speaker_id:
            log_speaker = f"ID: {speaker_id}"

        self.log_input(model, vocoder, log_speaker, output, text)
        self.log("<b>[STATUS]</b> Initializing TTS Engine...", "#facc15")
        self.log("<i>Note: External WAV takes precedence over internal ID.</i>", "#9ca3af")

        self.worker = TTSWorker(text, model, vocoder, speaker_wav, output)
        # Update worker to handle the internal speaker ID (need to modify TTSWorker)
        self.worker.speaker_id = speaker_id 
        self.worker.finished.connect(self.on_tts_finished)
        self.worker.error.connect(self.on_tts_error)
        self.worker.log_signal.connect(lambda msg, rep: self.log(msg, "#9ca3af" if "</b>" not in msg else "#00ff00", rep, is_lib=("</b>" not in msg)))
        self.worker.start()

    def on_tts_finished(self, output_path):
        self.btn_generate.setEnabled(True)
        self.log(f"<b>[OUTPUT]</b> Success! Generated: {os.path.basename(output_path)}", "#4ade80")
        QMessageBox.information(self, "Success", f"Speech generated successfully:\n{output_path}")

    def on_tts_error(self, error_msg):
        self.btn_generate.setEnabled(True)
        self.log(f"<b>[ERROR]</b> {error_msg}", "#f87171")
        QMessageBox.critical(self, "Error", f"An error occurred:\n{error_msg}")


def create_splash_pixmap():
    pixmap = QPixmap(400, 300)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    gradient = QLinearGradient(0, 0, 0, 300)
    gradient.setColorAt(0.0, QColor("#1e3a8a"))
    gradient.setColorAt(1.0, QColor("#1e1b4b"))
    painter.setBrush(gradient)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawRoundedRect(0, 0, 400, 300, 20, 20)
    painter.setPen(Qt.GlobalColor.white)
    painter.setFont(QFont("Segoe UI", 24, QFont.Weight.Bold))
    painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, "Coqui TTS\nSimple UI")
    painter.setFont(QFont("Segoe UI", 10))
    painter.drawText(pixmap.rect().adjusted(0, 220, 0, 0), Qt.AlignmentFlag.AlignHCenter, "Fetching available models...")
    painter.end()
    return pixmap

if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    splash = QSplashScreen(create_splash_pixmap())
    splash.show()
    app.processEvents()

    main_window = None

    def on_models_fetched(t_models, v_models):
        global main_window
        main_window = MainWindow(t_models, v_models)
        main_window.show()
        splash.finish(main_window)

    def on_fetch_error(err):
        splash.close()
        QMessageBox.critical(None, "Startup Error", f"Failed to fetch models:\n{err}\n\nFalling back to manual entries.")
        on_models_fetched([], [])

    app.fetcher = ModelFetcher() # Store reference on app object to prevent GC
    app.fetcher.finished.connect(on_models_fetched)
    app.fetcher.error.connect(on_fetch_error)
    app.fetcher.start()

    sys.exit(app.exec())




