#!/bin/sh
set -e

# Run the healthcheck
/usr/local/bin/analyzers_healthcheck.sh

# Execute the command passed to the entrypoint
exec "$@"
