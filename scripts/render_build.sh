#!/usr/bin/env bash
# Render build: install, fetch the new orders' bureau, train the model (artifacts/ is git-ignored).
set -e
pip install -r requirements.txt
# the bureau API fails some clients per run; retry, then train with whatever was cached
for attempt in 1 2 3; do python -m src.bureau && break || true; done
python -m src.risk_model
