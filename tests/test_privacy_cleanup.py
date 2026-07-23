import os
import io
import subprocess
import time

import pytest

from conftest import load_source_module


privacy = load_source_module("spa_privacy_cleanup", "app/viewer/privacy_cleanup.py")
JobWorkspace = privacy.JobWorkspace
UnsafeCleanupPath = privacy.UnsafeCleanupPath
purge_stale_workspaces = privacy.purge_stale_workspaces
purge_stale_uploads = privacy.purge_stale_uploads
safe_remove = privacy.safe_remove


def test_files_are_deleted_after_successful_processing(tmp_path):
    workspace = JobWorkspace(tmp_path, "success").create()
    artifact = workspace.child("results", "result.csv")
    artifact.parent.mkdir()
    artifact.write_text("clinical result")
    try:
        assert artifact.exists()
    finally:
        workspace.cleanup()
    assert not workspace.path.exists()


@pytest.mark.parametrize("failure", ["parser", "signal"])
def test_files_are_deleted_when_processing_fails(tmp_path, failure):
    workspace = JobWorkspace(tmp_path, failure)
    with pytest.raises(RuntimeError):
        with workspace:
            workspace.child("input.edf").write_bytes(b"partial clinical data")
            if failure == "signal":
                workspace.child("partial-output.png").write_bytes(b"partial image")
            raise RuntimeError(f"mock {failure} failure")
    assert not workspace.path.exists()


def test_cleanup_occurs_after_nonzero_subprocess(tmp_path):
    workspace = JobWorkspace(tmp_path, "subprocess")
    with pytest.raises(subprocess.CalledProcessError):
        with workspace:
            workspace.child("partial.db").write_bytes(b"partial")
            subprocess.run(["/usr/bin/false"], check=True)
    assert not workspace.path.exists()


def test_cleanup_is_idempotent_when_files_are_already_removed(tmp_path):
    workspace = JobWorkspace(tmp_path, "idempotent").create()
    workspace.cleanup()
    assert workspace.cleanup() is False


def test_concurrent_jobs_are_isolated_and_cannot_delete_each_other(tmp_path):
    first = JobWorkspace(tmp_path, "one").create()
    second = JobWorkspace(tmp_path, "two").create()
    first.child("input.edf").write_bytes(b"one")
    second_file = second.child("input.edf")
    second_file.write_bytes(b"two")

    first.cleanup()
    assert not first.path.exists()
    assert second_file.read_bytes() == b"two"
    second.cleanup()


def test_path_traversal_cannot_delete_outside_cache_root(tmp_path):
    root = tmp_path / "jobs"
    root.mkdir()
    outside = tmp_path / "outside.edf"
    outside.write_bytes(b"must survive")
    with pytest.raises(UnsafeCleanupPath):
        safe_remove(root / ".." / "outside.edf", root)
    assert outside.exists()


def test_symlink_is_unlinked_without_deleting_its_target(tmp_path):
    root = tmp_path / "jobs"
    root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    protected = outside / "protected.edf"
    protected.write_bytes(b"must survive")
    link = root / "job-link"
    link.symlink_to(outside, target_is_directory=True)
    assert safe_remove(link, root)
    assert protected.exists()


def test_stale_jobs_removed_but_recent_active_jobs_preserved(tmp_path):
    stale = JobWorkspace(tmp_path, "stale").create()
    recent = JobWorkspace(tmp_path, "recent").create()
    stale.child("input.edf").write_bytes(b"old")
    recent.child("input.edf").write_bytes(b"active")
    now = time.time()
    old = now - 7200
    os.utime(stale.path, (old, old))
    # Simulate abrupt process death: OS locks are released, but the directory and
    # active marker remain for startup recovery.
    stale._release_lock()

    assert purge_stale_workspaces(tmp_path, retention_seconds=3600, now=now) == 1
    assert not stale.path.exists()
    assert recent.path.exists()
    recent.cleanup()


def test_old_but_actively_locked_job_is_not_purged(tmp_path):
    active = JobWorkspace(tmp_path, "long-running").create()
    active.child("input.edf").write_bytes(b"active")
    now = time.time()
    old = now - 7200
    os.utime(active.path, (old, old))
    assert purge_stale_workspaces(tmp_path, retention_seconds=3600, now=now) == 0
    assert active.path.exists()
    active.cleanup()


def test_non_job_directories_are_never_removed_by_stale_purge(tmp_path):
    unrelated = tmp_path / "uploads"
    unrelated.mkdir()
    protected = unrelated / "recording.edf"
    protected.write_bytes(b"protected")
    old = time.time() - 7200
    os.utime(unrelated, (old, old))
    assert purge_stale_workspaces(tmp_path, retention_seconds=1) == 0
    assert protected.exists()


def test_stale_uploads_are_removed_while_recent_uploads_are_preserved(tmp_path):
    root = tmp_path / "uploads"
    user_dir = root / "42"
    user_dir.mkdir(parents=True)
    stale = user_dir / "stale.edf"
    recent = user_dir / "recent.edf"
    stale.write_bytes(b"old")
    recent.write_bytes(b"new")
    now = time.time()
    old = now - 7200
    os.utime(stale, (old, old))
    assert purge_stale_uploads(root, retention_seconds=3600, now=now) == 1
    assert not stale.exists()
    assert recent.exists()


def test_corrupted_edf_upload_is_deleted(tmp_path):
    from werkzeug.datastructures import FileStorage
    from app import create_app, db
    from app.models.user import User
    from app.viewer.data_processing import PSGDataManager

    app = create_app({
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": "sqlite://",
        "DATA_PATH": str(tmp_path / "uploads"),
        "SPA_JOB_CACHE_ROOT": str(tmp_path / "jobs"),
        "SPA_JOB_RETENTION_SECONDS": 3600,
        "SPA_JOB_TIMEOUT_SECONDS": 7200,
        "SPA_RESULT_RETENTION_SECONDS": 3600,
        "SESSION_TYPE": "filesystem",
    })
    with app.app_context():
        user = User(email="privacy-test@example.invalid")
        user.set_password("test-password")
        db.session.add(user)
        db.session.commit()
        upload = FileStorage(stream=io.BytesIO(b"not an EDF"), filename="corrupt.edf")
        with pytest.raises(Exception):
            PSGDataManager.save_uploaded_file(upload, user)
        assert not list((tmp_path / "uploads").rglob("*.edf"))
