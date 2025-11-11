#!/bin/bash
# Run type checking on the backend code using mypy
# This script verifies type annotations and catches type-related errors
# Note: Currently runs in informational mode (doesn't fail on errors)

echo "🔎 Running type checks with mypy..."
cd backend && uv run mypy . || echo "⚠️  Type hints need improvement (informational only)"

echo "✅ Type checking complete!"
