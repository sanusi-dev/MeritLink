"""OS-level lock so only one LLM-calling script runs at a time.
fcntl.flock is atomic and auto-releases on process exit (including crashes)."""
import fcntl
import os
from pathlib import Path


def acquire_lock(lock_path: Path):
    """Non-blocking exclusive lock. Returns the open file handle on success
    (keep it referenced for the process's lifetime), or None if held elsewhere."""
    try:
        lock_file = lock_path.open("w")
    except OSError:
        return None
    try:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except (BlockingIOError, OSError):
        lock_file.close()
        return None
    lock_file.write(str(os.getpid()))
    lock_file.flush()
    return lock_file


def release_lock(lock_file) -> None:
    """Release the lock and close the file handle."""
    try:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
    except Exception:
        pass
    lock_file.close()


def is_locked(lock_path: Path) -> bool:
    """Non-destructive probe -- tries to acquire and immediately release.
    Returns True if already held by another process."""
    lock_file = acquire_lock(lock_path)
    if lock_file is None:
        return True
    release_lock(lock_file)
    return False
