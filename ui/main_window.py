import os
import re
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, 
                             QTextEdit, QPushButton, QLabel, QMessageBox, 
                             QComboBox, QFileDialog, QLineEdit, QFormLayout,
                             QStackedWidget, QGridLayout, QCheckBox)
from . import settings, model_meta_data_cache
from .console_widget import ConsoleWidget, LogType
from background.metadata_fetcher import MetadataFetcher
from background.tts_worker import TTSWorker

class MainWindow(QWidget):
    def __init__(self, tts_model_names, vocoder_model_names):
        super().__init__()
        self.tts_model_names = tts_model_names
        self.vocoder_model_names = vocoder_model_names
        self.clean_tts_model_names = [m.replace(" [Downloaded]", "") for m in tts_model_names]
        
        # Sync current model list with cache
        model_meta_data_cache.sync_models(self.clean_tts_model_names)
        
        self.__init_ui()

    def __init_ui(self):
        self.setWindowTitle("Coqui TTS Simple UI")
        self.setMinimumWidth(600)

        layout = QVBoxLayout()

        self.__add_text_input_field(layout)
        self.__add_split_lines_checkbox(layout)

        # Settings Grid
        grid_layout = QGridLayout()
        grid_layout.setColumnStretch(1, 1) # Make the middle column (fields) stretch

        self.__add_model_selection_combo_box(grid_layout, 0)
        self.__add_vocoder_selection_combo_box(grid_layout, 1)
        self.__add_metadata_loader_button(grid_layout, 2) # Row 2 & 3, Col 2
        self.__add_language_selection_area(grid_layout, 2)
        self.__add_internal_speaker_selection_area(grid_layout, 3)
        self.__add_external_speaker_reference_field(grid_layout, 4)
        self.__add_output_file_section(grid_layout, 5)

        layout.addLayout(grid_layout)

        self.__add_generate_button(layout)
        
        self.console = ConsoleWidget()
        layout.addWidget(self.console)

        self.setLayout(layout)

        # Trigger initial speaker UI state
        self.__on_model_changed()
        self.console.log("Ready", is_rich_text=True)

    def __handle_log_signal(self, msg, replace):
        """Parse incoming logs from background workers and route to console correctly."""
        if msg.startswith("[STATUS] "):
            self.console.log(msg[9:], replace=replace, log_type=LogType.STATUS, is_rich_text=True)
        elif msg.startswith("[PROG] "):
            self.console.log(msg[7:], replace=replace, log_type=LogType.PROG)
        elif msg.startswith("[INPUT] "):
            self.console.log(msg[8:], replace=replace, log_type=LogType.INPUT)
        elif msg.startswith("[OUTPUT] "):
            self.console.log(msg[9:], replace=replace, log_type=LogType.OUTPUT)
        elif msg.startswith("[ERROR] "):
            self.console.log(msg[8:], replace=replace, log_type=LogType.ERROR)
        elif msg.startswith("[WARNING] "):
            self.console.log(msg, replace=replace) # Keep prefix for warnings
        elif msg.startswith("[LIB] "):
            self.console.log(msg[6:], replace=replace, log_type=LogType.LIB)
        else:
            # Typical tqdm bars have '|' followed by a bar character (-123456789#) and contain '%'
            is_probably_progress = ("%" in msg) and bool(re.search(r'\|[-1-9#]', msg)) 
            
            if is_probably_progress:
                # FORCE replace=True for progress bars to handle libraries that send newlines
                self.console.log(msg, replace=True, log_type=LogType.PROG)
            else:
                self.console.log(msg, replace=replace, log_type=LogType.LIB)

    def __on_generate_clicked(self):
        text = self.text_edit.toPlainText().strip()
        if not text:
            QMessageBox.warning(self, "Warning", "Please enter some text.")
            return

        model = self.combo_model.currentData()
        vocoder = self.combo_vocoder.currentText().strip()
        speaker_wav = self.edit_speaker.text().strip()
        speaker_id = self.combo_internal_speaker.currentData() if self.speaker_stack.currentIndex() == 1 else None
        language = self.combo_language.currentData() if self.lang_stack.currentIndex() == 1 else "en"
        if not model:
            QMessageBox.warning(self, "Warning", "Please select a model.")
            return

        info = model_meta_data_cache.get_model_info(model)
        is_multilingual = info["is_multilingual"]
        split_lines = self.check_split_lines.isChecked()
        output = self.edit_output.text().strip()

        # Explicit validation for missing multi-speaker selection
        if info["status"] == "unknown":
             QMessageBox.critical(self, "Metadata Required", "Please click 'Download Model' to probe this model's capabilities before generating.")
             return
        elif info["speaker_type"] == "multi" and not speaker_id and not speaker_wav:
             QMessageBox.critical(self, "Speaker Required", "Please select a speaker from the dropdown or provide a reference WAV.")
             return

        self.btn_generate.setEnabled(False)
        
        # Determine logical speaker name for logging
        log_speaker = "Default"
        if speaker_wav:
            log_speaker = f"WAV: {os.path.basename(speaker_wav)}"
        elif speaker_id:
            log_speaker = f"ID: {speaker_id}"

        self.__log_input(model, vocoder, log_speaker, output, text)
        self.console.log("Initializing TTS Engine...", log_type=LogType.STATUS, is_rich_text=True)
        self.console.log("Note: External WAV takes precedence over internal ID.", color="#9ca3af")

        self.worker = TTSWorker(text, model, vocoder, speaker_wav, speaker_id, language, is_multilingual, split_lines, output)
        self.worker.finished.connect(self.__on_tts_finished)
        self.worker.error.connect(self.__on_tts_error)
        self.worker.log_signal.connect(self.__handle_log_signal)
        self.worker.start()


    def __log_input(self, model, vocoder, speaker, output, text):
        """Log the command configuration."""
        self.console.log("--- Starting TTS Task ---", log_type=LogType.INPUT)
        self.console.log(f"Model: {model}", log_type=LogType.INPUT)
        if vocoder:
            self.console.log(f"Vocoder: {vocoder}", log_type=LogType.INPUT)
        if speaker:
            self.console.log(f"Speaker Ref: {speaker}", log_type=LogType.INPUT)
        self.console.log(f"Output Path: {output}", log_type=LogType.INPUT)
        self.console.log(f"Text Length: {len(text)} characters", log_type=LogType.INPUT)


    def __on_model_changed(self):
        model_name = self.combo_model.currentData()
        if not model_name:
            return
            
        # Save selection
        settings.set_setting("last_model", model_name)
            
        # Trigger fetchers if unknown
        # We now manage status labels and button visibility
        show_load_btn = False
        
        meta_data = model_meta_data_cache.get_model_info(model_name)
        status = meta_data["status"]
        
        if status == "unknown":
            self.lbl_speaker_info.setText("No Information (Download required)")
            self.lbl_lang_info.setText("No Information (Download required)")
            self.speaker_stack.setCurrentIndex(0) # Show Label
            self.lang_stack.setCurrentIndex(0)    # Show Label
            show_load_btn = True
        else:
            # Handle Speaker UI
            if meta_data["speaker_type"] == "multi":
                self.speaker_stack.setCurrentIndex(1) # Show Combo
                self.combo_internal_speaker.blockSignals(True)
                self.combo_internal_speaker.clear()
                for i, spk in enumerate(meta_data["speakers"]):
                    self.combo_internal_speaker.addItem(f"[{i}] {spk}", spk)
                
                # Restore speaker
                last_speaker = settings.get_setting(f"last_speaker_{model_name}")
                if last_speaker:
                    idx = self.combo_internal_speaker.findData(last_speaker)
                    if idx != -1:
                        self.combo_internal_speaker.setCurrentIndex(idx)
                self.combo_internal_speaker.blockSignals(False)
            else:
                self.lbl_speaker_info.setText("Single speaker model")
                self.speaker_stack.setCurrentIndex(0) # Show Label
            
            # Handle Multilingual UI
            if meta_data["is_multilingual"]:
                self.lang_stack.setCurrentIndex(1) # Show Combo
                self.combo_language.blockSignals(True)
                self.combo_language.clear()
                for lang in meta_data["languages"]:
                    self.combo_language.addItem(lang, lang)
                
                # Restore language
                last_lang = settings.get_setting(f"last_language_{model_name}")
                if last_lang:
                    idx = self.combo_language.findData(last_lang)
                    if idx != -1:
                        self.combo_language.setCurrentIndex(idx)
                else:
                    # Default to English if available
                    idx = self.combo_language.findData("en")
                    if idx != -1:
                        self.combo_language.setCurrentIndex(idx)
                self.combo_language.blockSignals(False)
            else:
                self.lbl_lang_info.setText("Single language model")
                self.lang_stack.setCurrentIndex(0) # Show Label
            
        self.btn_load_metadata.setVisible(show_load_btn)
        self.btn_load_metadata.setEnabled(show_load_btn)

    def __on_load_metadata_clicked(self):
        model_name = self.combo_model.currentData()
        if not model_name:
            return
            
        self.console.log(f"Downloading and probing {model_name}...", log_type=LogType.STATUS)
        self.btn_load_metadata.setText("Downloading ...")
        self.btn_load_metadata.setEnabled(False)
        
        # Combined Fetcher
        self.fetcher = MetadataFetcher(model_name)
        self.fetcher.finished.connect(self.__on_metadata_fetched)
        self.fetcher.error.connect(self.__on_metadata_error)
        self.fetcher.log_signal.connect(self.__handle_log_signal)
        self.fetcher.start()

    def __on_metadata_fetched(self, model_name, speaker_type, is_multilingual, speakers, languages):
        model_meta_data_cache.update_model_metadata(model_name, speaker_type, is_multilingual, speakers, languages)
        
        self.console.log(f"Download and analysis complete for {model_name}:", log_type=LogType.STATUS, is_rich_text=True)
        self.console.log(f" &nbsp;&bull; Speaker Type: {speaker_type}", log_type=LogType.STATUS, is_rich_text=True)
        self.console.log(f" &nbsp;&bull; Multilingual: {is_multilingual}", log_type=LogType.STATUS, is_rich_text=True)
        self.console.log(f" &nbsp;&bull; Speakers: {len(speakers)} found", log_type=LogType.STATUS, is_rich_text=True)
        self.console.log(f" &nbsp;&bull; Languages: {len(languages)} found", log_type=LogType.STATUS, is_rich_text=True)
        
        # Update the item text in the combo box to show it's downloaded
        idx = self.combo_model.findData(model_name)
        if idx != -1:
            self.combo_model.setItemText(idx, f"{model_name} [Downloaded]")

        # If the currently selected model is still this one, update UI
        if self.combo_model.currentData() == model_name:
            self.__on_model_changed()

    def __on_metadata_error(self, err):
        self.console.log(f"Metadata probe failed: {err}", log_type=LogType.ERROR)
        QMessageBox.warning(self, "Load Error", f"Could not load model metadata:\n{err}")
        self.__on_model_changed()

    def __on_language_changed(self):
        model_name = self.combo_model.currentData()
        lang = self.combo_language.currentData()
        if model_name and lang:
            settings.set_setting(f"last_language_{model_name}", lang)

    def __on_vocoder_changed(self):
        vocoder_name = self.combo_vocoder.currentText().strip()
        settings.set_setting("last_vocoder", vocoder_name)

    def __on_speaker_changed(self):
        model_name = self.combo_model.currentData()
        speaker_id = self.combo_internal_speaker.currentData()
        if model_name and speaker_id:
            settings.set_setting(f"last_speaker_{model_name}", speaker_id)

    def __browse_speaker(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Select Speaker Reference", "", "Audio Files (*.wav)")
        if file_path:
            self.edit_speaker.setText(file_path)

    def __browse_output(self):
        file_path, _ = QFileDialog.getSaveFileName(self, "Select Output File", self.edit_output.text(), "Audio Files (*.wav)")
        if file_path:
            self.edit_output.setText(file_path)

    def __play_audio(self):
        file_path = self.edit_output.text().strip()
        if not file_path or not os.path.exists(file_path):
            QMessageBox.warning(self, "Warning", "Output file does not exist. Generate it first!")
            return
        
        try:
            os.startfile(file_path)
            self.console.log(f"Playing file: {os.path.basename(file_path)}", color="#a78bfa")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not play audio:\n{str(e)}")

    def __on_tts_finished(self, output_path):
        self.btn_generate.setEnabled(True)
        self.console.log(f"Success! Generated: {os.path.basename(output_path)}", log_type=LogType.OUTPUT)
        QMessageBox.information(self, "Success", f"Speech generated successfully:\n{output_path}")

    def __on_tts_error(self, error_msg):
        self.btn_generate.setEnabled(True)
        self.console.log(error_msg, log_type=LogType.ERROR)
        QMessageBox.critical(self, "Error", f"An error occurred:\n{error_msg}")

    def __add_text_input_field(self, layout):
        layout.addWidget(QLabel("Enter text to speak:"))
        self.text_edit = QTextEdit()
        self.text_edit.setPlaceholderText("Type something here...")
        layout.addWidget(self.text_edit)

    def __add_model_selection_combo_box(self, grid_layout, row):
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
        self.combo_model.currentIndexChanged.connect(self.__on_model_changed)
        
        grid_layout.addWidget(QLabel("Model:"), row, 0)
        grid_layout.addWidget(self.combo_model, row, 1, 1, 2) # Span 2 columns if no button

    def __add_vocoder_selection_combo_box(self, grid_layout, row):
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
        self.combo_vocoder.currentIndexChanged.connect(self.__on_vocoder_changed)
        
        grid_layout.addWidget(QLabel("Vocoder (Optional):"), row, 0)
        grid_layout.addWidget(self.combo_vocoder, row, 1, 1, 2)

    def __add_language_selection_area(self, grid_layout, row):
        self.lang_stack = QStackedWidget()
        
        # Page 0: Status Label
        self.lbl_lang_info = QLabel("Single language model")
        self.lbl_lang_info.setStyleSheet("color: #9ca3af; font-style: italic;")
        self.lang_stack.addWidget(self.lbl_lang_info)
        
        # Page 1: Language Combo
        self.combo_language = QComboBox()
        self.combo_language.currentIndexChanged.connect(self.__on_language_changed)
        self.lang_stack.addWidget(self.combo_language)
        
        grid_layout.addWidget(QLabel("Language:"), row, 0)
        grid_layout.addWidget(self.lang_stack, row, 1)

    def __add_internal_speaker_selection_area(self, grid_layout, row):
        self.speaker_stack = QStackedWidget()
        
        # Page 0: Status Label
        self.lbl_speaker_info = QLabel("Single speaker model")
        self.lbl_speaker_info.setStyleSheet("color: #9ca3af; font-style: italic;")
        self.speaker_stack.addWidget(self.lbl_speaker_info)
        
        # Page 1: Speaker Combo
        self.combo_internal_speaker = QComboBox()
        self.combo_internal_speaker.currentIndexChanged.connect(self.__on_speaker_changed)
        self.speaker_stack.addWidget(self.combo_internal_speaker)
        
        grid_layout.addWidget(QLabel("Speaker (Internal):"), row, 0)
        grid_layout.addWidget(self.speaker_stack, row, 1)

    def __add_metadata_loader_button(self, grid_layout, row):
        self.btn_load_metadata = QPushButton("Download Model")
        self.btn_load_metadata.setStyleSheet("padding: 5px; min-height: 2.5em;")
        self.btn_load_metadata.clicked.connect(self.__on_load_metadata_clicked)
        
        # Add to the right column, spanning 2 rows (Language and Speaker)
        grid_layout.addWidget(self.btn_load_metadata, row, 2, 2, 1)

    def __add_external_speaker_reference_field(self, grid_layout, row):
        speaker_layout = QHBoxLayout()
        
        saved_speaker = settings.get_setting("last_external_speaker_path", "")
        self.edit_speaker = QLineEdit(saved_speaker)
        self.edit_speaker.textChanged.connect(self.__on_external_speaker_changed)
        
        self.edit_speaker.setPlaceholderText("Optional WAV for voice cloning")
        self.btn_browse_speaker = QPushButton("Browse...")
        self.btn_browse_speaker.clicked.connect(self.__browse_speaker)
        speaker_layout.addWidget(self.edit_speaker)
        speaker_layout.addWidget(self.btn_browse_speaker)
        
        grid_layout.addWidget(QLabel("Speaker Reference (External WAV):"), row, 0)
        grid_layout.addLayout(speaker_layout, row, 1, 1, 2)

    def __on_external_speaker_changed(self):
        settings.set_setting("last_external_speaker_path", self.edit_speaker.text().strip())

    def __add_split_lines_checkbox(self, layout):
        self.check_split_lines = QCheckBox("Split lines")
        
        # Default to True, but restore from settings if available
        saved_split = settings.get_setting("split_lines", True)
        self.check_split_lines.setChecked(saved_split)
        self.check_split_lines.toggled.connect(self.__on_split_lines_toggled)
        
        # Add to main layout (QVBoxLayout automatically aligns left by default if specified or no stretch)
        # We can also wrap it in a QHBoxLayout if we want to be explicit about left alignment
        cb_layout = QHBoxLayout()
        cb_layout.addWidget(self.check_split_lines)
        cb_layout.addStretch()
        layout.addLayout(cb_layout)

    def __on_split_lines_toggled(self, checked):
        settings.set_setting("split_lines", checked)

    def __add_output_file_section(self, grid_layout, row):
        output_layout = QHBoxLayout()
        
        saved_output = settings.get_setting("last_output_path", os.path.join(os.getcwd(), "output.wav"))
        self.edit_output = QLineEdit(saved_output)
        self.edit_output.textChanged.connect(self.__on_output_path_changed)
        
        self.btn_browse_output = QPushButton("Browse...")
        self.btn_browse_output.clicked.connect(self.__browse_output)
        self.btn_play = QPushButton("▶ Play")
        self.btn_play.setToolTip("Play the selected output file")
        self.btn_play.clicked.connect(self.__play_audio)
        
        output_layout.addWidget(self.edit_output)
        output_layout.addWidget(self.btn_browse_output)
        output_layout.addWidget(self.btn_play)
        
        grid_layout.addWidget(QLabel("Output File:"), row, 0)
        grid_layout.addLayout(output_layout, row, 1, 1, 2)

    def __on_output_path_changed(self):
        settings.set_setting("last_output_path", self.edit_output.text().strip())

    def __add_generate_button(self, layout):
        # Generate Button
        self.btn_generate = QPushButton("Generate Speech")
        self.btn_generate.setStyleSheet("padding: 15px; font-size: 14pt; font-weight: bold; background-color: #1e40af; color: white; border-radius: 5px;")
        self.btn_generate.clicked.connect(self.__on_generate_clicked)
        layout.addWidget(self.btn_generate)

