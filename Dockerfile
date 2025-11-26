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
# If you are using poetry and have a lock file:
# COPY poetry.lock .

# Install the project and its dependencies (requires setuptools/flit/hatch configuration)
# The most reliable way for systems without a dedicated tool is to install the dependencies
# first, and then install the package in "editable" mode if needed.
# Since you have no requirements.txt, let's assume your packaging tool is handling installation:

# --- MODIFIED INSTALLATION STEPS ---
# Install the build dependencies required to read pyproject.toml
RUN pip install setuptools wheel build

# Copy the entire application source code
COPY . .

# Install the project and dependencies in the container's environment
# The dot '.' refers to the current working directory (/usr/src/app)
# This command should install everything listed in your pyproject.toml dependencies section.
RUN pip install .

# Copy the entire application source code
COPY . .

# Set up the default command (needed for the API service)
CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000"]