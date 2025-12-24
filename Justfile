setup-traditional:
    #!/usr/bin/env bash
    python3 -m venv --system-site-packages venv
    ./venv/bin/pip install -e .
    echo "✓ Setup complete! Run 'just run' to start"
    
setup-uv:
    #!/usr/bin/env bash
    uv venv --python-preference only-system --system-site-packages
    uv sync

install-deps:
    ./setup-scripts/install-deps.sh

run-orig:
    uv run src/systemd-mount-manager/original.py


run-trad:
    .venv/bin/python3 src/systemd-mount-manager/gitest.py

nuke:
    rm -rf venv
