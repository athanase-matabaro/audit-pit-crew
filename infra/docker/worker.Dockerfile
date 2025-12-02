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

# Install the build dependencies required to read pyproject.toml
# This is needed if pyproject.toml is used for dependencies in the worker
RUN pip install setuptools wheel build

# --- SECURITY TOOLING & COMPILER PRE-INSTALL (ROBUST FIX) ---
# 1. Install Slither and its core dependencies.
RUN pip install "slither-analyzer==0.11.0" crytic-compile

# 1b. Install Mythril for multi-tool analysis.
RUN pip install "mythril==0.23.0"

# 1c. Install Aderyn for multi-tool analysis.
RUN cargo install aderyn

# 2. Install solc-select.
RUN pip install solc-select

# 3. Install a wide range of common compiler versions to handle various pragmas.
# This eliminates runtime network calls for downloading compilers.
# Installing these versions: 0.8.20 (latest needed), 0.8.0, 0.7.6, 0.6.12, and 0.5.17.
RUN solc-select install 0.8.20 0.8.0 0.7.6 0.6.12 0.5.17

# 4. Set the default to a modern version for general checks.
# Slither's compiler handler (crytic-compile) will automatically select the right
# pre-installed version based on the contract's pragma.
RUN solc-select use 0.8.20
# --- END TOOLING ---

# Install PyYAML for config file parsing (temporary)
RUN pip install pyyaml

# Copy the entire application source code
COPY . .

# Install the project and dependencies in the container's environment
# The dot '.' refers to the current working directory (/usr/src/app)
# This command should install everything listed in your pyproject.toml dependencies section.
# Assuming pyproject.toml is copied and used for dependency management for the worker
COPY pyproject.toml .
RUN pip install .

# Copy and prepare entrypoint and healthcheck scripts
COPY scripts/analyzers_healthcheck.sh /usr/local/bin/analyzers_healthcheck.sh
COPY scripts/entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/analyzers_healthcheck.sh /usr/local/bin/entrypoint.sh

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]

# CMD is typically defined in docker-compose for the worker,
# but a default can be provided. For a worker, it might be running
# celery, for example. I'll leave this part generic as it will be
# overridden by docker-compose for the worker service.
# CMD ["celery", "-A", "src.worker.celery_app", "worker", "--loglevel=info"]
# I'll use the API CMD for now since the original root Dockerfile had it
# and I don't have explicit worker CMD info. This should be overridden by docker-compose.
CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
