from enum import Enum, auto
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QTextEdit
from PyQt6.QtGui import QTextCursor

class LogType(Enum):
    NONE = auto()
    LIB = auto()
    STATUS = auto()
    INPUT = auto()
    OUTPUT = auto()
    ERROR = auto()
    PROG = auto()

LOG_TYPE_COLORS = {
    LogType.NONE: "#00ff00", # Default Green
    LogType.LIB: "#9ca3af",   # Gray
    LogType.STATUS: "#facc15", # Yellow
    LogType.INPUT: "#60a5fa",  # Blue
    LogType.OUTPUT: "#4ade80", # Bright Green
    LogType.ERROR: "#f87171",  # Red
    LogType.PROG: "#f97316",   # Vibrant Orange
}

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

    def log(self, message, color=None, replace=False, log_type=LogType.NONE):
        """Append a message to the console window. If replace=True, replaces the last block."""
        
        # Determine Color
        if color is None:
            color = LOG_TYPE_COLORS.get(log_type, LOG_TYPE_COLORS[LogType.NONE])

        # 1. Handle Prefixes and Escaping
        if log_type == LogType.LIB:
            # Escape HTML special characters for library output
            clean_msg = message.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            formatted_msg = f'<b>[LIB]</b> {clean_msg}'
        elif log_type != LogType.NONE:
            # Prepend bold prefix for internal types
            prefix = log_type.name
            formatted_msg = f'<b>[{prefix}]</b> {message}'
        else:
            # No prefix, use raw message
            formatted_msg = message

        cursor = self.console_output.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        
        if replace:
            # Shift selection to the start of the current last block (logical paragraph)
            # This handles wrapped lines correctly, unlike StartOfLine
            cursor.movePosition(QTextCursor.MoveOperation.StartOfBlock, QTextCursor.MoveMode.KeepAnchor)
            
            if cursor.hasSelection():
                # OVERWRITE the selected block using insertHtml
                cursor.insertHtml(f'<span style="color: {color};">{formatted_msg}</span>')
                return

        # Use append() for normal logs to ensure they start on a new line
        self.console_output.append(f'<span style="color: {color};">{formatted_msg}</span>')
        
        # Auto-scroll to bottom
        self.console_output.moveCursor(QTextCursor.MoveOperation.End)
