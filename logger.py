"""
Path: logger.py
Purpose: Centralized logging module for debug output
Rationale: Provides dual output (console + file) for debugging purposes
Key Dependencies: None
Last Modified: 2025-12-03
"""

import sys
import os
from datetime import datetime
from typing import Optional

class DualLogger:
    """Logger that writes to both console and file simultaneously."""
    
    def __init__(self, log_file_path: str = None, mode: str = 'a'):
        """
        Initialize the dual logger.
        
        Args:
            log_file_path: Path to the log file. Defaults to 'result.txt' in current directory.
            mode: File open mode ('a' for append, 'w' for overwrite).
        """
        if log_file_path is None:
            log_file_path = os.path.join(os.getcwd(), 'result.txt')
        
        self.log_file_path = log_file_path
        self.log_file = None
        self.mode = mode
        
        try:
            self.log_file = open(self.log_file_path, self.mode, encoding='utf-8')
            self._write_header()
        except Exception as e:
            print(f"Warning: Could not open log file '{self.log_file_path}': {e}", file=sys.stderr)
    
    def _write_header(self):
        """Write a header to the log file with timestamp."""
        if self.log_file and self.mode == 'w':
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            header = f"{'=' * 80}\n"
            header += f"Wasabi Downloader Execution Log\n"
            header += f"Started at: {timestamp}\n"
            header += f"{'=' * 80}\n\n"
            self.log_file.write(header)
            self.log_file.flush()
    
    def log(self, message: str, file=None, end: str = '\n'):
        """
        Write a message to both console and log file.
        
        Args:
            message: The message to log.
            file: Output stream for console (default: sys.stdout).
            end: Line ending character (default: newline).
        """
        if file is None:
            file = sys.stdout
        
        # Write to console
        print(message, file=file, end=end)
        
        # Write to log file
        if self.log_file:
            try:
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
                log_entry = f"[{timestamp}] {message}{end}"
                self.log_file.write(log_entry)
                self.log_file.flush()
            except Exception as e:
                print(f"Warning: Could not write to log file: {e}", file=sys.stderr)
    
    def log_error(self, message: str):
        """
        Write an error message to both console (stderr) and log file.
        
        Args:
            message: The error message to log.
        """
        self.log(f"ERROR: {message}", file=sys.stderr)
    
    def log_warning(self, message: str):
        """
        Write a warning message to both console and log file.
        
        Args:
            message: The warning message to log.
        """
        self.log(f"WARNING: {message}")
    
    def log_info(self, message: str):
        """
        Write an info message to both console and log file.
        
        Args:
            message: The info message to log.
        """
        self.log(f"INFO: {message}")
    
    def log_debug(self, message: str):
        """
        Write a debug message to both console and log file.
        
        Args:
            message: The debug message to log.
        """
        self.log(f"DEBUG: {message}")
    
    def close(self):
        """Close the log file."""
        if self.log_file:
            try:
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                footer = f"\n{'=' * 80}\n"
                footer += f"Execution ended at: {timestamp}\n"
                footer += f"{'=' * 80}\n"
                self.log_file.write(footer)
                self.log_file.close()
            except Exception:
                pass
    
    def __enter__(self):
        """Support for context manager."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Support for context manager."""
        self.close()

# Global logger instance
_global_logger: Optional[DualLogger] = None

def init_logger(log_file_path: str = None, mode: str = 'w') -> DualLogger:
    """
    Initialize the global logger.
    
    Args:
        log_file_path: Path to the log file.
        mode: File open mode ('a' for append, 'w' for overwrite).
    
    Returns:
        The initialized DualLogger instance.
    """
    global _global_logger
    if _global_logger:
        _global_logger.close()
    _global_logger = DualLogger(log_file_path, mode)
    return _global_logger

def get_logger() -> Optional[DualLogger]:
    """
    Get the global logger instance.
    
    Returns:
        The global DualLogger instance, or None if not initialized.
    """
    return _global_logger

def log(message: str, file=None, end: str = '\n'):
    """Convenience function to log using the global logger."""
    if _global_logger:
        _global_logger.log(message, file, end)
    else:
        print(message, file=file if file else sys.stdout, end=end)

def log_error(message: str):
    """Convenience function to log errors using the global logger."""
    if _global_logger:
        _global_logger.log_error(message)
    else:
        print(f"ERROR: {message}", file=sys.stderr)

def log_warning(message: str):
    """Convenience function to log warnings using the global logger."""
    if _global_logger:
        _global_logger.log_warning(message)
    else:
        print(f"WARNING: {message}")

def log_info(message: str):
    """Convenience function to log info messages using the global logger."""
    if _global_logger:
        _global_logger.log_info(message)
    else:
        print(f"INFO: {message}")

def log_debug(message: str):
    """Convenience function to log debug messages using the global logger."""
    if _global_logger:
        _global_logger.log_debug(message)
    else:
        print(f"DEBUG: {message}")

def close_logger():
    """Close the global logger."""
    global _global_logger
    if _global_logger:
        _global_logger.close()
        _global_logger = None
