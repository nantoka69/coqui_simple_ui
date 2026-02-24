import os
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, 
                             QTextEdit, QPushButton, QLabel, QMessageBox, 
                             QComboBox, QFileDialog, QLineEdit, QFormLayout,
                             QStackedWidget)
from background.model_meta_data_cache_manager import ModelMetaDataCacheManager
from . import settings
from background.speaker_fetcher import SpeakerFetcher
from background.tts_worker import TTSWorker

class MainWindow(QWidget):
    def __init__(self, tts_model_names, vocoder_model_names):
        super().__init__()
        self.tts_model_names = tts_model_names
        self.vocoder_model_names = vocoder_model_names
        self.clean_tts_model_names = [m.replace(" [Loaded]", "") for m in tts_model_names]
        
        # Sync current model list with cache
        self.config = ModelMetaDataCacheManager()
        self.config.sync_models(self.clean_tts_model_names)
        
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
        for display_name, real_name in zip(self.tts_model_names, self.clean_tts_model_names):
             self.combo_model.addItem(display_name, real_name)
        
        # Default to a saved model or first entry
        last_model = settings.get_setting("last_model")
        default_idx = self.combo_model.findData(last_model) if last_model else -1
        if default_idx == -1:
            default_idx = 0
            
        self.combo_model.setCurrentIndex(default_idx)
        self.combo_model.currentIndexChanged.connect(self.on_model_changed)
        form_layout.addRow("Model:", self.combo_model)

        # Vocoder Selection
        self.combo_vocoder = QComboBox()
        self.combo_vocoder.setEditable(False)
        self.combo_vocoder.addItem("") # Optional
        self.combo_vocoder.addItems(self.vocoder_model_names)
        
        # Default to a saved vocoder or first entry (empty)
        last_vocoder = settings.get_setting("last_vocoder")
        vocoder_idx = self.combo_vocoder.findText(last_vocoder) if last_vocoder else -1
        if vocoder_idx == -1:
            vocoder_idx = 0
            
        self.combo_vocoder.setCurrentIndex(vocoder_idx)
        self.combo_vocoder.currentIndexChanged.connect(self.on_vocoder_changed)
        
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
            
        # Save selection
        settings.set_setting("last_model", model_name)
            
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

    def on_vocoder_changed(self):
        vocoder_name = self.combo_vocoder.currentText().strip()
        settings.set_setting("last_vocoder", vocoder_name)

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
