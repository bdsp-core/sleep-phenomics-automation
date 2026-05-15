# Sleep Phenomics Automation (SPA)

On Mac
```
# install colima
# colima delete     # if previous instance exists
colima start --memory 12 --cpu 4

# setup venv and docker
python -m venv venv
source venv/bin/activate
DOCKER_HOST=unix:///$HOME/.colima/docker.sock python create_caisr_dockers.py

# run
DOCKER_HOST=unix:///$HOME/.colima/docker.sock python -Wignore app.py
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
