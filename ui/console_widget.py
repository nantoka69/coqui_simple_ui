from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QTextEdit
from PyQt6.QtGui import QTextCursor

class ConsoleWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.__init_ui()

    def __init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Console Output Window
        layout.addWidget(QLabel("Console Output:"))
        self.console_output = QTextEdit()
        self.console_output.setReadOnly(True)
        self.console_output.setMinimumHeight(150)
        self.console_output.setStyleSheet("""
            QTextEdit {
                background-color: #000000;
                color: #00ff00;
                font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
                font-size: 10pt;
                border: 1px solid #333333;
                border-radius: 4px;
            }
        """)
        layout.addWidget(self.console_output)

    def log(self, message, color="#00ff00", replace=False, is_lib=False):
        """Append a message to the console window. If replace=True, replaces the last block."""
        
        if is_lib:
            # 1. Escape HTML special characters in the raw library message content
            # This prevents characters like < and > in progress bars from being eaten by Qt's HTML renderer
            clean_msg = message.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            formatted_msg = f'<b>[LIB]</b> {clean_msg}'
        else:
            # For non-lib messages (status logs), we assume they may contain intentional HTML tags
            # like <b>[STATUS]</b> or <i>Note:</i>
            formatted_msg = message

        cursor = self.console_output.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        
        if replace:
            # Shift selection to the start of the current last block (logical paragraph)
            # This handles wrapped lines correctly, unlike StartOfLine
            cursor.movePosition(QTextCursor.MoveOperation.StartOfBlock, QTextCursor.MoveMode.KeepAnchor)
            
            if cursor.hasSelection():
                # OVERWRITE the selected block using insertHtml
                # Only set the color; the font-family is inherited from the widget stylesheet
                cursor.insertHtml(f'<span style="color: {color};">{formatted_msg}</span>')
                return

        # Use append() for normal logs. Removing the redundant font-family
        # allows the widget stylesheet to handle it, making bold/italic inheritance more reliable.
        self.console_output.append(f'<span style="color: {color};">{formatted_msg}</span>')
        
        # Auto-scroll to bottom
        self.console_output.moveCursor(QTextCursor.MoveOperation.End)
