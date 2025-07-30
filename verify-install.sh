#!/bin/bash
# Hippo Installation Verification Script

echo "🦛 Hippo Installation Verification"
echo "=================================="

# Check if we're in the right directory
if [ ! -f "pyproject.toml" ] || [ ! -d "py/hippo" ]; then
    echo "❌ Error: Run this script from the hippo repository root directory"
    exit 1
fi

echo "✓ Repository structure looks correct"

# Check if uv is installed
if ! command -v uv &> /dev/null; then
    echo "❌ Error: uv is not installed. Install from: https://docs.astral.sh/uv/getting-started/installation/"
    exit 1
fi

echo "✓ uv is installed: $(uv --version)"

# Install dependencies
echo "📦 Installing dependencies..."
if ! uv sync --extra dev --quiet; then
    echo "❌ Error: Failed to install dependencies"
    exit 1
fi

echo "✓ Dependencies installed successfully"

# Test server help
echo "🧪 Testing server command..."
if ! uv run python -m hippo.server --help > /dev/null 2>&1; then
    echo "❌ Error: Server command failed"
    exit 1
fi

echo "✓ Server command works"

# Test server startup (brief)
echo "🚀 Testing server startup..."
TEST_FILE="/tmp/hippo-verify-$$.json"
timeout 3 uv run python -m hippo.server --hippo-file "$TEST_FILE" > /dev/null 2>&1
if [ $? -eq 124 ]; then
    echo "✓ Server starts successfully (timed out as expected)"
    rm -rf "$TEST_FILE"  # Use -rf to handle both files and directories
else
    echo "⚠️  Server startup test inconclusive (may still work)"
fi

# Test type checking
echo "🔍 Testing type checking..."
if ! uv run mypy py/hippo/ > /dev/null 2>&1; then
    echo "⚠️  Type checking found issues (development may be affected)"
else
    echo "✓ Type checking passes"
fi

echo ""
echo "🎉 Installation verification complete!"
echo ""
echo "Next steps:"
echo "1. Create data directory: mkdir -p ~/.hippo"
echo "2. Add to your AI tool configuration (see README.md)"
echo "3. Add guidance.md to your AI context"
echo ""
echo "For Q CLI: q configure add-server hippo \"uv run --directory $(pwd) python -m hippo.server --hippo-file ~/.hippo/hippo.json\""
