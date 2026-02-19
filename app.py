import sys
import os
import re
import collections
from PyQt6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout, 
                             QTextEdit, QPushButton, QLabel, QMessageBox, 
                             QSplashScreen, QComboBox, QFileDialog, QLineEdit, QFormLayout)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QPixmap, QColor, QLinearGradient, QPainter, QFont

class ModelFetcher(QThread):
    finished = pyqtSignal(list, list)
    error = pyqtSignal(str)

    def run(self):
        try:
            from TTS.api import TTS
            # Get the ModelManager
            manager = TTS().list_models()
            # Get the actual list of model names
            models = manager.list_models()
            
            # Group into tts and vocoders
            t_models = [m for m in models if m.startswith("tts_models/")]
            v_models = [m for m in models if m.startswith("vocoder_models/")]
            
            self.finished.emit(t_models, v_models)
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
        
        # Handle carriage return: if it contains \r, only take the text after the last \r
        # We emit a special flag for \r to allow the UI to overwrite the last line
        replace = '\r' in clean_text
        if replace:
            clean_text = clean_text.split('\r')[-1]
            
        if clean_text.strip():
            self.signal.emit(clean_text.strip(), replace)

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
            
            # Only use speaker_wav if the model is multi-speaker
            use_speaker = self.speaker_wav if self.speaker_wav and tts.is_multi_speaker else None
            
            for i, sentence in enumerate(sentences):
                # Emit with 'replace=True' to keep the console clean
                self.log_signal.emit(f"<b>[PROG]</b> Processing segment {i+1}/{total}...", True)
                # tts.tts returns a list of floats (the waveform)
                wav = tts.tts(text=sentence, speaker_wav=use_speaker)
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
        self.combo_model.addItems(self.t_models)
        # Default to a common model
        default_idx = self.combo_model.findText("tts_models/en/ljspeech/vits")
        if default_idx >= 0:
            self.combo_model.setCurrentIndex(default_idx)
        form_layout.addRow("Model:", self.combo_model)

        # Vocoder Selection
        self.combo_vocoder = QComboBox()
        self.combo_vocoder.setEditable(False)
        self.combo_vocoder.addItem("") # Optional
        self.combo_vocoder.addItems(self.v_models)
        form_layout.addRow("Vocoder (Optional):", self.combo_vocoder)

        # Speaker Wave (for cloning)
        speaker_layout = QHBoxLayout()
        self.edit_speaker = QLineEdit()
        self.btn_browse_speaker = QPushButton("Browse...")
        self.btn_browse_speaker.clicked.connect(self.browse_speaker)
        speaker_layout.addWidget(self.edit_speaker)
        speaker_layout.addWidget(self.btn_browse_speaker)
        form_layout.addRow("Speaker Reference (Optional WAV):", speaker_layout)


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
        self.log("Ready")

    def log(self, message, color="#00ff00", replace=False):
        """Append a message to the console window. If replace=True, replaces the last line if it's a progress line."""
        cursor = self.console_output.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        
        if replace:
            # Check if the last line contains [PROG] or was marked for replacement
            # This prevents overwriting [LIB] logs that might have appeared since the last [PROG]
            cursor.movePosition(cursor.MoveOperation.StartOfLine, cursor.MoveMode.KeepAnchor)
            last_line = cursor.selectedText()
            if "[PROG]" in last_line or "Processing" in last_line:
                cursor.removeSelectedText()
                cursor.deletePreviousChar() # remove the newline
                self.console_output.setTextCursor(cursor)
            else:
                # If the last line wasn't a progress line, don't replace, just append normally
                pass

        self.console_output.append(f'<span style="color: {color};">{message}</span>')
        # Auto-scroll to bottom
        self.console_output.moveCursor(self.console_output.textCursor().MoveOperation.End)

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

        model = self.combo_model.currentText().strip()
        vocoder = self.combo_vocoder.currentText().strip()
        speaker = self.edit_speaker.text().strip()
        output = self.edit_output.text().strip()

        if not model:
            QMessageBox.warning(self, "Warning", "Please select or enter a model.")
            return

        self.btn_generate.setEnabled(False)
        self.log_input(model, vocoder, speaker, output, text)
        self.log("<b>[STATUS]</b> Initializing TTS Engine...", "#facc15")

        self.worker = TTSWorker(text, model, vocoder, speaker, output)
        self.worker.finished.connect(self.on_tts_finished)
        self.worker.error.connect(self.on_tts_error)
        self.worker.log_signal.connect(lambda msg, rep: self.log(msg if "</b>" in msg else f"<b>[LIB]</b> {msg}", "#9ca3af" if "</b>" not in msg else "#00ff00", rep))
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




