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
        # 1. Strip ANSI codes from the incoming chunk
        clean_text = self.ansi_escape.sub('', text)
        if not clean_text:
            return

        # 2. Append to buffer
        self.buffer += clean_text

        # 3. Process the buffer
        # Split by newline, but keep the last part if it's incomplete
        if '\n' in self.buffer:
            parts = self.buffer.split('\n')
            # All parts except the last one were followed by a newline
            lines_to_process = parts[:-1]
            # Store the remaining text back in buffer
            self.buffer = parts[-1]
            
            for line in lines_to_process:
                self._process_line(line, is_partial=False)
        
        # 4. Handle carriage returns even in the current buffer segment
        # If the buffer contains \r, we might want to "flash" the progress
        if '\r' in self.buffer:
            # We only emit if there's significant content before the \r or if it's the end
            parts = self.buffer.split('\r')
            # The last part is the "current" line being built
            # If there was a \r, the part BEFORE it is a complete line to show (and replace later)
            for part in parts[:-1]:
                if part:
                    self.signal.emit(part, True)
            self.buffer = parts[-1]

    def _process_line(self, line, is_partial):
        """Internal helper to emit a line, handling internal carriage returns."""
        if '\r' in line:
            parts = line.split('\r')
            # Find the last non-empty part to display
            display_line = next((p for p in reversed(parts) if p), "")
            if display_line:
                self.signal.emit(display_line, True)
        else:
            # Normal line
            self.signal.emit(line, False)

    def isatty(self):
        """Trick libraries like tqdm into thinking we are a real terminal."""
        return True

    def flush(self):
        """No-op for compatibility."""
        pass
