#!/bin/sh
set -e

echo "--- Analyzer Healthcheck ---"

echo "Checking slither..."
slither --version

echo "Checking mythril..."
myth version

echo "Checking aderyn..."
aderyn --version

echo "--------------------------"
echo "All analyzers found."
