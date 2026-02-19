import sys
import os
import time
from PyQt6.QtWidgets import QApplication, QWidget, QVBoxLayout, QTextEdit, QPushButton, QLabel, QMessageBox, QSplashScreen
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QPixmap, QColor, QLinearGradient, QPainter, QFont

class TTSWorker(QThread):
    finished = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, text, model_name="tts_models/en/ljspeech/vits"):
        super().__init__()
        self.text = text
        self.model_name = model_name

    def run(self):
        try:
            # Heavy import moved here for lazy loading
            from TTS.api import TTS
            tts = TTS(self.model_name)
            output_path = "output.wav"
            tts.tts_to_file(text=self.text, file_path=output_path)
            self.finished.emit(output_path)
        except Exception as e:
            self.error.emit(str(e))

class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle("Coqui TTS Simple UI")
        self.setGeometry(100, 100, 400, 300)

        layout = QVBoxLayout()

        self.label = QLabel("Enter text to speak:")
        layout.addWidget(self.label)

        self.text_edit = QTextEdit()
        layout.addWidget(self.text_edit)

        self.btn_generate = QPushButton("Generate Speech")
        self.btn_generate.clicked.connect(self.on_generate_clicked)
        layout.addWidget(self.btn_generate)

        self.status_label = QLabel("")
        layout.addWidget(self.status_label)

        self.setLayout(layout)

    def on_generate_clicked(self):
        text = self.text_edit.toPlainText().strip()
        if not text:
            QMessageBox.warning(self, "Warning", "Please enter some text.")
            return

        self.btn_generate.setEnabled(False)
        self.status_label.setText("Generating...")

        self.worker = TTSWorker(text)
        self.worker.finished.connect(self.on_tts_finished)
        self.worker.error.connect(self.on_tts_error)
        self.worker.start()

    def on_tts_finished(self, output_path):
        self.btn_generate.setEnabled(True)
        self.status_label.setText(f"Generated: {output_path}")
        QMessageBox.information(self, "Success", f"Speech generated successfully: {output_path}")

    def on_tts_error(self, error_msg):
        self.btn_generate.setEnabled(True)
        self.status_label.setText("Error occurred.")
        QMessageBox.critical(self, "Error", f"An error occurred: {error_msg}")

def create_splash_pixmap():
    pixmap = QPixmap(400, 300)
    pixmap.fill(Qt.GlobalColor.transparent)
    
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    
    # Create gradient background
    gradient = QLinearGradient(0, 0, 0, 300)
    gradient.setColorAt(0.0, QColor("#1e3a8a"))
    gradient.setColorAt(1.0, QColor("#1e1b4b"))
    
    painter.setBrush(gradient)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawRoundedRect(0, 0, 400, 300, 15, 15)
    
    # Draw simple text
    painter.setPen(Qt.GlobalColor.white)
    painter.setFont(QFont("Arial", 20, QFont.Weight.Bold))
    painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, "Coqui TTS\nLoading Application...")
    
    painter.end()
    return pixmap

if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    # Show Splash Screen
    splash = QSplashScreen(create_splash_pixmap())
    splash.show()
    app.processEvents()
    
    # Simulate a small delay for feeling "premium" or handle actual init
    # Since we moved the heavy import to lazy load, the main window will appear fast.
    
    window = MainWindow()
    
    # We wait a tiny bit to make sure the splash is visible
    QTimer.singleShot(1500, lambda: (window.show(), splash.finish(window)))
    
    sys.exit(app.exec())

