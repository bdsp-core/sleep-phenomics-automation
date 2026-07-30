# Sleep Phenomics Automation (SPA)

## Supported PSG uploads

SPA accepts EDF/BDF recordings through the existing native pipeline and XDF recordings
through an additional `pyxdf` ingestion path. XDF numeric time-series streams are
normalized to an internal EDF so visualization and phenomics behavior remains shared.
Marker streams are aligned to the selected signal clock and stored as EDF annotations.

For XDF files, SPA automatically selects the signal only when exactly one numeric stream
is available. If several numeric streams are plausible, the upload screen asks the user
to choose using stream name, type, channel/sample counts, and nominal rate. Missing rates
are inferred from timestamps; irregular streams are linearly resampled. Missing channel
labels become `Channel N`, and unknown units are treated as microvolts with a warning.
XDF metadata not representable in EDF remains visible during stream selection
but is not persisted after normalization.

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
