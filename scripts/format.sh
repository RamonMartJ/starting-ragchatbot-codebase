#!/bin/bash
# Format all Python code in the backend directory using black
# This script ensures consistent code formatting across the codebase

set -e

echo "🎨 Formatting Python code with black..."
uv run black backend/

echo "✅ Formatting complete!"
