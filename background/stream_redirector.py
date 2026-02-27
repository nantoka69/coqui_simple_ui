import re

class StreamRedirector:
    def __init__(self, signal):
        self.signal = signal
        # More robust regex for stripping ANSI escape sequences
        self.ansi_escape = re.compile(r'(?:\x1B[@-_]|[\x80-\x9F])[0-?]*[ -/]*[@-~]')
        self.encoding = "utf-8"
        self.errors = "strict"
        self.softspace = 0
        self.mode = "w"

        self.buffer = ""

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
                replace = True
            else:
                display_line = line
                replace = False
            
            # Emit if there's content or it's a newline (not the last empty segment)
            if display_line or (not is_last):
                self.signal.emit(display_line, replace)

    def isatty(self):
        """Trick libraries like tqdm into thinking we are a real terminal."""
        return True

    def flush(self):
        """No-op for compatibility."""
        pass
