
# Install the package
setup:
    #!/usr/bin/env bash
    ./setup-scripts/install-deps.sh
    uv venv --python-preference only-system --system-site-packages
    uv sync

# Run the original bash script
run-orig:
    uv run src/systemd-mount-manager/original.py

# Run the CLI, passing through any flags
run flags='':
	uv run systemd-mount-manager {{flags}}

# Run in dev mode
run-dev:
	uv run textual run --dev src/systemd_mount_manager/main.py

# Run the console
console:
	uv run textual console -x EVENT -x SYSTEM

# Runs ruff, exits with 0 if no issues are found
lint:
  @uv run ruff check src

# Runs mypy, exits with 0 if no issues are found
typecheck:
  @uv run mypy src
  @uv run basedpyright src

# Runs black
format:
  @uv run black src

test:
  @uv run pytest tests -v

# Run the Nox testing suite for comprehensive testing.
# This will run pytest against all versions of Textual and Python
# specified in the noxfile.py
nox:
  nox
  
# Remove all caches and temporary files
clean:
  find . -name "*.pyc" -delete
  find . -name "*-report.*" -delete
  find . -name "error.*" -delete
  rm -rf .mypy_cache
  rm -rf .ruff_cache
  rm -rf .nox

# Remove the virtual environment and lock file
del-env:
  rm -rf .venv
  rm -rf uv.lock

nuke: clean del-env
  @echo "All build artifacts and caches have been removed."

# Removes all environment and build stuff
reset: nuke install
  @echo "Environment reset."

release:
  bash .github/scripts/validate_main.sh && \
  uv run .github/scripts/tag_release.py && \
  git push --tags

sync-tags:
  git fetch --prune origin "+refs/tags/*:refs/tags/*"