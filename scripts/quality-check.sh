#!/bin/bash
# Run all code quality checks in sequence
# This script performs formatting, linting, and type checking to ensure code quality

set -e

echo "🚀 Running comprehensive code quality checks..."
echo ""

# Format code
echo "📝 Step 1/3: Formatting code..."
./scripts/format.sh
echo ""

# Lint code
echo "🔍 Step 2/3: Linting code..."
./scripts/lint.sh
echo ""

# Type check
echo "🔎 Step 3/3: Type checking..."
./scripts/typecheck.sh
echo ""

echo "✨ All quality checks passed successfully!"
