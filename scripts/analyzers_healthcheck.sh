#!/bin/sh
# Don't use set -e - we want to check all tools even if some fail

echo "--- Analyzer Healthcheck ---"

# Track core tools status
SLITHER_OK=0
MYTHRIL_OK=0

echo "Checking slither..."
if command -v slither > /dev/null 2>&1; then
    slither --version && SLITHER_OK=1
else
    echo "Slither not found (CRITICAL)"
fi

echo "Checking mythril..."
if command -v myth > /dev/null 2>&1; then
    myth version && MYTHRIL_OK=1
else
    echo "Mythril not found (CRITICAL)"
fi

# Aderyn is optional (may have installation issues)
echo "Checking aderyn (optional)..."
if command -v aderyn > /dev/null 2>&1; then
    aderyn --version 2>/dev/null || echo "Aderyn installed but version check failed"
else
    echo "Aderyn not installed (optional - may have cargo install issues)"
fi

# Oyente is optional (unmaintained package, may fail to install)
echo "Checking oyente (optional)..."
if command -v oyente > /dev/null 2>&1; then
    oyente --version 2>/dev/null || echo "Oyente installed but version check failed"
else
    echo "Oyente not installed (optional - unmaintained package)"
fi

echo "--------------------------"

# Only require slither and mythril
if [ "$SLITHER_OK" -eq 1 ] && [ "$MYTHRIL_OK" -eq 1 ]; then
    echo "✅ Core analyzers found (Slither, Mythril)"
    exit 0
else
    echo "❌ Missing core analyzers!"
    exit 1
fi
