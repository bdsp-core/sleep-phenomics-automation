# SPA processing-data lifecycle

SPA treats uploaded recordings, annotations, intermediate signal files, generated
databases, plots, CSV files, and detection files as sensitive clinical data.

## Storage locations

- Initial uploads and annotation mapping files are staged under `DATA_PATH`
  (`app/data/` by default). This directory is not beneath `app/static/` and is not
  served by a Flask static route.
- When analysis starts, the recording and any annotation files are moved into a
  unique private directory under `SPA_JOB_CACHE_ROOT`
  (`instance/spa_jobs/job-<UUID>/` by default).
- CAISR input/output trees, Luna EDF/annotation/database files, phenotype CSV and
  pickle files, and email PNG files are all created inside that job directory.
- Result CSV and detection data retained for the download/view APIs are held only
  in process memory after on-disk cleanup. The complete in-memory job entry and its
  results expire after `SPA_RESULT_RETENTION_SECONDS` (one hour by default).

Viewer MNE objects are explicitly evicted and closed when analysis takes ownership
of a recording or when a recording is manually deleted.

## Guaranteed cleanup

The background worker owns one job workspace. Its `finally` block recursively
deletes that workspace after successful processing and after parser, signal-processing,
subprocess, email, or partial-output failures. The corresponding database record is
also removed. Cleanup is idempotent, rejects targets outside the configured root,
does not traverse symlinks, and runs before the frontend receives the completion or
error event. Cleanup failures do not replace the original processing outcome.

Cleanup logging includes only opaque job IDs, counts, booleans, and exception class
names. Uploaded filenames, filesystem paths, raw samples, annotations, and generated
clinical results are not logged by the cleanup layer.

## Abrupt termination and retention

An operating-system kill, out-of-memory termination, machine restart, or power loss
cannot execute Python `finally` blocks. At every application startup SPA therefore
purges abandoned `job-*` directories older than `SPA_JOB_RETENTION_SECONDS`. The
default is **3600 seconds (one hour)**. Recent/active directories and unrelated
directories are preserved. Each live job holds an operating-system file lock; an old
directory is purged only when that lock is no longer owned by a running worker.
Deployments may set both `SPA_JOB_CACHE_ROOT` and
`SPA_JOB_RETENTION_SECONDS` through environment variables.

Startup also purges files older than the same limit from `DATA_PATH`. This covers
uploads abandoned before processing began and legacy uploads created before the
job-workspace lifecycle was introduced.

Jobs also have a cooperative processing deadline configured by
`SPA_JOB_TIMEOUT_SECONDS` (default: **7200 seconds / two hours**). Cancellation and
timeout checks run before and after signal loading, preprocessing, and each phenotype;
queued cancellations purge immediately. A running native-library or subprocess call
cannot be interrupted safely in-process, so cancellation is completed at the next
check; its workspace remains private until the guaranteed cleanup then runs.

Infrastructure should additionally encrypt the backing volume, restrict filesystem
permissions to the SPA service account, and run startup promptly after host recovery.
No application can delete local files while its host and storage are unavailable.

Custom phenotype code executes with the SPA worker's Python permissions. SPA passes its
private job directory as the intended working location, but cannot prevent deliberately
or accidentally supplied Python code from writing elsewhere. Deployments that enable
custom code for untrusted users should execute it in a separately sandboxed container
with only the job directory mounted.
