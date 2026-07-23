"""Fail-safe lifecycle management for files that may contain clinical data.

Only opaque job identifiers are logged. Paths and uploaded filenames are deliberately
excluded because they may contain patient identifiers.
"""
from __future__ import annotations

import logging
import os
import shutil
import time
import uuid
from pathlib import Path

try:
    import fcntl
except ImportError:  # pragma: no cover - SPA production targets are Linux/macOS
    fcntl = None


class UnsafeCleanupPath(ValueError):
    """Raised when a cleanup target is not strictly inside its configured root."""


def _absolute(path):
    return Path(os.path.abspath(os.path.expanduser(os.fspath(path))))


def _inside(path, root):
    try:
        path.relative_to(root)
        return path != root
    except ValueError:
        return False


def safe_remove(path, allowed_root):
    """Idempotently remove one file/tree without escaping or following symlinks."""
    target = _absolute(path)
    root = _absolute(allowed_root)
    if root.is_symlink():
        raise UnsafeCleanupPath("configured cleanup root must not be a symlink")
    if not _inside(target, root):
        raise UnsafeCleanupPath("cleanup target is outside the configured root")
    cursor = root
    for part in target.relative_to(root).parts[:-1]:
        cursor = cursor / part
        if cursor.is_symlink():
            raise UnsafeCleanupPath("cleanup target traverses a symlink")
    if not os.path.lexists(target):
        return False

    # A symlink is removed as a link; its target is never traversed.
    if target.is_symlink() or target.is_file():
        target.unlink(missing_ok=True)
    elif target.is_dir():
        resolved_root = root.resolve(strict=True)
        resolved_target = target.resolve(strict=True)
        if not _inside(resolved_target, resolved_root):
            raise UnsafeCleanupPath("resolved cleanup target is outside the configured root")
        shutil.rmtree(target)
    else:
        target.unlink(missing_ok=True)
    return True


class JobWorkspace:
    """Unique, private directory containing every on-disk artifact for one run."""

    def __init__(self, root, job_id=None, logger=None):
        self.root = _absolute(root)
        self.job_id = job_id or str(uuid.uuid4())
        self.path = self.root / f"job-{self.job_id}"
        self.logger = logger or logging.getLogger(__name__)
        self._created = False
        self._active_handle = None

    def create(self):
        self.root.mkdir(mode=0o700, parents=True, exist_ok=True)
        os.chmod(self.root, 0o700)
        self.path.mkdir(mode=0o700, exist_ok=False)
        marker = self.path / ".active"
        self._active_handle = marker.open("x")
        self._active_handle.write(str(os.getpid()))
        self._active_handle.flush()
        if fcntl is not None:
            fcntl.flock(self._active_handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        self._created = True
        self.logger.info("[privacy-cleanup] workspace created job_id=%s", self.job_id)
        return self

    def child(self, *parts):
        candidate = self.path.joinpath(*parts)
        if not _inside(_absolute(candidate), _absolute(self.path)):
            raise UnsafeCleanupPath("job artifact path escapes its workspace")
        return candidate

    def move_into(self, source, name):
        destination = self.child(name)
        destination.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        shutil.move(str(source), str(destination))
        return destination

    def cleanup(self):
        self._release_lock()
        removed = safe_remove(self.path, self.root)
        self._created = False
        self.logger.info(
            "[privacy-cleanup] workspace cleanup job_id=%s removed=%s",
            self.job_id, removed,
        )
        return removed

    def _release_lock(self):
        if self._active_handle is not None:
            try:
                if fcntl is not None:
                    fcntl.flock(self._active_handle.fileno(), fcntl.LOCK_UN)
            finally:
                self._active_handle.close()
                self._active_handle = None

    def __enter__(self):
        return self.create()

    def __exit__(self, exc_type, exc, tb):
        self.cleanup()
        return False


def purge_stale_workspaces(root, retention_seconds, now=None, logger=None):
    """Remove abandoned job directories, including old crash-left `.active` jobs."""
    logger = logger or logging.getLogger(__name__)
    root = _absolute(root)
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(root, 0o700)
    now = time.time() if now is None else now
    removed = 0
    for entry in root.iterdir():
        if not entry.name.startswith("job-") or entry.is_symlink() or not entry.is_dir():
            continue
        try:
            age = now - entry.lstat().st_mtime
            if age <= retention_seconds:
                continue
            marker = entry / ".active"
            if fcntl is not None and marker.is_file() and not marker.is_symlink():
                with marker.open("r+") as handle:
                    try:
                        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                    except BlockingIOError:
                        # Another live SPA process still owns this workspace.
                        continue
                    finally:
                        try:
                            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
                        except OSError:
                            pass
            safe_remove(entry, root)
            removed += 1
        except (FileNotFoundError, UnsafeCleanupPath):
            continue
        except OSError as exc:
            logger.warning(
                "[privacy-cleanup] stale workspace cleanup failed error_type=%s",
                type(exc).__name__,
            )
    logger.info("[privacy-cleanup] stale purge completed removed=%d", removed)
    return removed


def purge_stale_uploads(root, retention_seconds, now=None, logger=None):
    """Purge abandoned pre-job uploads, including files from older SPA versions."""
    logger = logger or logging.getLogger(__name__)
    root = _absolute(root)
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    now = time.time() if now is None else now
    removed = 0
    for directory, names, filenames in os.walk(root, topdown=True, followlinks=False):
        directory_path = Path(directory)
        names[:] = [name for name in names if not (directory_path / name).is_symlink()]
        for filename in filenames:
            target = directory_path / filename
            try:
                if now - target.lstat().st_mtime <= retention_seconds:
                    continue
                safe_remove(target, root)
                removed += 1
            except (FileNotFoundError, UnsafeCleanupPath):
                continue
            except OSError as exc:
                logger.warning(
                    "[privacy-cleanup] stale upload cleanup failed error_type=%s",
                    type(exc).__name__,
                )
    for directory, _, _ in os.walk(root, topdown=False, followlinks=False):
        directory_path = Path(directory)
        if directory_path != root:
            try:
                directory_path.rmdir()
            except OSError:
                pass
    logger.info("[privacy-cleanup] stale upload purge completed removed=%d", removed)
    return removed
