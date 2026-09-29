import sys

# ==============================================================================
# Global UTF-8 Stream Sanitizer for Windows
# Prevents UnicodeEncodeError ('charmap' codec can't encode character...)
# across all Python scripts and processes in this project.
# ==============================================================================

if sys.platform == "win32":
    try:
        if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
            sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

    try:
        if sys.stderr and hasattr(sys.stderr, 'reconfigure'):
            sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

    try:
        if sys.stdin and hasattr(sys.stdin, 'reconfigure'):
            sys.stdin.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass
