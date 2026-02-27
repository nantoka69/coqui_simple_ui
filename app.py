import os
os.environ["TQDM_ASCII"] = "-123456789#"
import sys
from PyQt6.QtWidgets import QApplication, QMessageBox, QSplashScreen
from PyQt6.QtCore import Qt, QObject, pyqtSlot
from PyQt6.QtGui import QPixmap, QColor, QLinearGradient, QPainter, QFont

from background.model_fetcher import ModelFetcher
from ui.main_window import MainWindow

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
    
    class StartupBridge(QObject):
        @pyqtSlot(list, list)
        def on_models_fetched(self, tts_model_names, vocoder_model_names):
            try:
                global main_window
                main_window = MainWindow(tts_model_names, vocoder_model_names)
                main_window.show()
                splash.finish(main_window)
            except Exception as e:
                splash.close()
                QMessageBox.critical(None, "Runtime Error", f"An error occurred during UI initialization:\n{e}")
                sys.exit(1)

        @pyqtSlot(str)
        def on_fetch_error(self, err):
            splash.close()
            QMessageBox.critical(None, "Startup Error", f"Failed to fetch models:\n{err}\n\nFalling back to manual entries.")
            self.on_models_fetched([], [])

    bridge = StartupBridge()
    app.fetcher = ModelFetcher()
    app.fetcher.finished.connect(bridge.on_models_fetched)
    app.fetcher.error.connect(bridge.on_fetch_error)
    app.fetcher.start()

    sys.exit(app.exec())
