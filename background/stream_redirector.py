import re

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
