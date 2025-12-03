# Use a lean official Python image
FROM python:3.10-slim

# Set environment variables for non-interactive commands
ENV PYTHONUNBUFFERED 1
ENV APP_HOME /usr/src/app

# Create and set the working directory
WORKDIR $APP_HOME

# Install system dependencies needed for git (for cloning) and build tools
RUN apt-get update \
    && apt-get install -y git build-essential curl python3-dev libssl-dev libffi-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Rust and Cargo
RUN curl https://sh.rustup.rs -sSf | sh -s -- -y
ENV PATH="/root/.cargo/bin:${PATH}"

# Copy all configuration files needed for installation
COPY pyproject.toml .

# Install the build dependencies required to read pyproject.toml
RUN pip install setuptools wheel build

# --- SECURITY TOOLING & COMPILER PRE-INSTALL (ROBUST FIX) ---
# 1. Install Slither and its core dependencies.
RUN pip install "slither-analyzer==0.11.0" crytic-compile

# 1b. Install Mythril for multi-tool analysis.
# Also install py-solc-x explicitly to ensure solc versions are cached
RUN pip install "mythril==0.23.0" py-solc-x

# 1b-patch. CRITICAL: Patch Mythril's util.py to handle network failures gracefully
# Mythril calls solcx.get_installable_solc_versions() at import time (line 138 of util.py)
# This causes crashes when network is unavailable. We use a Python script to patch it.
COPY scripts/patch_mythril.py /tmp/patch_mythril.py
RUN python3 /tmp/patch_mythril.py || echo "Warning: Mythril patch script failed"

# 1c. Install Aderyn for multi-tool analysis.
# NOTE: Aderyn v0.1.9 from crates.io has a bug that causes panics on certain version strings.
# We try to install from GitHub with a newer version. If that fails, we skip Aderyn entirely
# rather than installing the buggy v0.1.9.
# The correct cargo install syntax for a workspace package from a specific tag:
RUN (cargo install --git https://github.com/Cyfrin/aderyn --tag aderyn-v0.6.5 --package aderyn && \
     echo "✅ Aderyn v0.6.5 installed successfully from GitHub") || \
    (echo "⚠️ WARNING: Aderyn GitHub install failed. Aderyn will NOT be available." && \
     echo "aderyn_install_failed" > /tmp/aderyn_failed)

# Verify Aderyn installation - if it failed, show warning
RUN if [ -f /tmp/aderyn_failed ]; then \
      echo "⚠️ Aderyn not installed - will be skipped during scans"; \
    else \
      aderyn --version || echo "Warning: Aderyn binary not runnable"; \
    fi

# 1d. Install Oyente (Legacy)
# Use explicit python3 pip, avoid wheel cache, and verify installation and PATH.
# Oyente is unmaintained and may fail to install on some platforms; we keep a non-failing
# build but emit clear diagnostics and a marker file the runtime can inspect.
RUN python3 -m pip install --no-cache-dir oyente || (echo "Warning: Oyente pip install failed" > /tmp/oyente_install_failed) \
    && python3 -m pip show oyente || echo "Oyente not found in pip show" \
    && (command -v oyente || echo "Warning: oyente not found in PATH after install" > /tmp/oyente_missing_in_path)

# 2. Install solc-select.
RUN pip install solc-select

# 3. Install a wide range of common compiler versions to handle various pragmas.
# This eliminates runtime network calls for downloading compilers.
# Installing these versions: 0.8.20 (latest needed), 0.8.0, 0.7.6, 0.6.12, and 0.5.17.
RUN solc-select install 0.8.20 0.8.0 0.7.6 0.6.12 0.5.17

# 3b. Pre-install solc versions via py-solc-x for Mythril
# This prevents Mythril from making network calls during analysis
RUN python3 -c "import solcx; solcx.install_solc('0.8.20'); solcx.install_solc('0.8.0'); solcx.install_solc('0.7.6')" || echo "Warning: py-solc-x install failed"

# 4. Set the default to a modern version for general checks.
# Slither's compiler handler (crytic-compile) will automatically select the right
# pre-installed version based on the contract's pragma.
RUN solc-select use 0.8.20

# Set environment variable to help Mythril avoid network calls during import
ENV MYTHRIL_SOLC_BINARY=/root/.solcx/solc-v0.8.20
# --- END TOOLING ---

# Install PyYAML for config file parsing (temporary)
RUN pip install pyyaml

# Copy the entire application source code
COPY . .

# Install the project and dependencies in the container's environment
# The dot '.' refers to the current working directory (/usr/src/app)
# This command should install everything listed in your pyproject.toml dependencies section.
RUN pip install .

# Copy and prepare entrypoint and healthcheck scripts
COPY scripts/analyzers_healthcheck.sh /usr/local/bin/analyzers_healthcheck.sh
COPY scripts/entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/analyzers_healthcheck.sh /usr/local/bin/entrypoint.sh

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]

# Set up the default command (needed for the API service, overridden by docker-compose for the worker)
CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
