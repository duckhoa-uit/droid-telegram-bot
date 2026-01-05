#!/bin/bash
# OpenCode Telegram Bot - Config Export Script
# This script exports your local OpenCode config for deployment to a VPS

set -e

OUTPUT_DIR="${1:-./deploy-config}"
CONFIG_DIR="$HOME/.config/opencode"

echo "🚀 OpenCode Config Export Script"
echo "================================="

# Create output directory
mkdir -p "$OUTPUT_DIR"

# Check if config exists
if [ ! -d "$CONFIG_DIR" ]; then
    echo "❌ OpenCode config not found at $CONFIG_DIR"
    exit 1
fi

echo "📁 Exporting configs to $OUTPUT_DIR..."

# Copy config files (excluding sensitive auth file by default)
cp "$CONFIG_DIR/opencode.jsonc" "$OUTPUT_DIR/" 2>/dev/null || echo "⚠️  opencode.jsonc not found"
cp "$CONFIG_DIR/oh-my-opencode.json" "$OUTPUT_DIR/" 2>/dev/null || echo "⚠️  oh-my-opencode.json not found"
cp "$CONFIG_DIR/antigravity.json" "$OUTPUT_DIR/" 2>/dev/null || echo "⚠️  antigravity.json not found"
cp "$CONFIG_DIR/package.json" "$OUTPUT_DIR/" 2>/dev/null || echo "⚠️  package.json not found"

# Ask about auth tokens
echo ""
read -p "📋 Include antigravity-accounts.json (OAuth tokens)? [y/N]: " include_auth
if [[ "$include_auth" =~ ^[Yy]$ ]]; then
    if [ -f "$CONFIG_DIR/antigravity-accounts.json" ]; then
        cp "$CONFIG_DIR/antigravity-accounts.json" "$OUTPUT_DIR/"
        echo "✅ Included antigravity-accounts.json (KEEP SECURE!)"
    else
        echo "⚠️  antigravity-accounts.json not found"
    fi
else
    echo "ℹ️  Skipped antigravity-accounts.json - you'll need to run 'opencode auth' on VPS"
fi

# List exported files
echo ""
echo "📦 Exported files:"
ls -la "$OUTPUT_DIR/"

echo ""
echo "✅ Config export complete!"
echo ""
echo "📌 Next steps:"
echo "1. Copy $OUTPUT_DIR/* to VPS at ~/.config/opencode/"
echo "2. Run 'bun install' or 'npm install' in ~/.config/opencode/"
echo "3. If you didn't include auth tokens, run 'opencode auth' on VPS"
echo ""
echo "Example SCP command:"
echo "  scp -r $OUTPUT_DIR/* root@your-vps:~/.config/opencode/"
