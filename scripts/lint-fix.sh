#!/bin/bash
# Run linting checks and automatically fix issues where possible
# Uses ruff to fix import sorting, remove unused imports, and other auto-fixable issues

set -e

echo "🔧 Running linting with auto-fix..."
cd backend && uv run ruff check --fix .

echo "✅ Auto-fixable issues resolved!"
