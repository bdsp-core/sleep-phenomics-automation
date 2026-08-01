# Sleep Phenomics Automation (SPA)

## Supported PSG uploads

SPA accepts PSG signal recordings in EDF format through the existing native processing
pipeline. XDF physiological time-series streams are not accepted as PSG signal uploads.

Annotation uploads accept TXT, CSV, TSV, XLS, XLSX, and XDF files. SPA supports both
Lab Streaming Layer XDF marker streams (through `pyxdf`) and Polysmith/OpenXDF XML
annotation exports. Both variants are converted to the existing `Onset`, `Duration`, and
`Description` table used by the annotation-mapping workflow. OpenXDF uses the document's
default scorer when one is identified and otherwise selects the scorer with the most
complete stage/event set. Numeric OpenXDF stages are normalized to W, N1, N2, N3, and R.
For LSL XDF, a signal stream may establish the recording time origin, but its samples are
not imported. An annotation-only LSL XDF uses its first marker as time zero. Missing LSL
marker durations are inferred from the next marker, with a 30-second final-marker fallback.

## Security and privacy

Uploaded recordings and all job-generated files are deleted after successful and
failed analysis attempts through a guaranteed worker `finally` cleanup. A configurable
startup purge removes abandoned job directories left by abrupt process or machine
termination. Cleanup logs omit filenames, paths, and signal contents. See
[`SECURITY_PRIVACY.md`](SECURITY_PRIVACY.md) for storage locations, the one-hour
default retention policy, configuration, and infrastructure limitations.

On Mac
```
# install colima
# colima delete     # if previous instance exists
colima start --memory 12 --cpu 4 --vm-type vz --vz-rosetta

# setup venv and docker
python -m venv venv
source venv/bin/activate
cd app/ml_models/CAISR-App
DOCKER_HOST=unix://$HOME/.colima/docker.sock python create_caisr_dockers.py
cd ../../..

# run
DOCKER_HOST=unix://$HOME/.colima/docker.sock python -Wignore app.py
```

On Linux
```
# setup venv and docker
python -m venv venv
source venv/bin/activate
python create_caisr_dockers.py

# run
python -Wignore app.py
```
