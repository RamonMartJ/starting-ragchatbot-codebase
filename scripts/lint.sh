#!/bin/bash
# Run linting checks on the backend code using ruff
# This script checks for code quality issues, import sorting, and PEP 8 compliance

set -e

echo "🔍 Running linting checks with ruff..."
cd backend && uv run ruff check .

echo "✅ Linting checks passed!"
