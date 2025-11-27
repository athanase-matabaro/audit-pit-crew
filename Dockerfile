# Use a lean official Python image
FROM python:3.12-slim

# Set environment variables for non-interactive commands
ENV PYTHONUNBUFFERED 1
ENV APP_HOME /usr/src/app

# Create and set the working directory
WORKDIR $APP_HOME

# Install system dependencies needed for git (for cloning) and build tools
RUN apt-get update \
    && apt-get install -y git build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy all configuration files needed for installation
COPY pyproject.toml .

# Install the build dependencies required to read pyproject.toml
RUN pip install setuptools wheel build

# --- SECURITY TOOLING & COMPILER PRE-INSTALL (ROBUST FIX) ---
# 1. Install Slither and its core dependencies.
RUN pip install slither-analyzer crytic-compile

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

# Copy the entire application source code
COPY . .

# Install the project and dependencies in the container's environment
# The dot '.' refers to the current working directory (/usr/src/app)
# This command should install everything listed in your pyproject.toml dependencies section.
RUN pip install .

# Set up the default command (needed for the API service, overridden by docker-compose for the worker)
CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000"]