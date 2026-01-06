#!/bin/bash
set -e

echo "Starting OpenCode Telegram Bot..."

# Ensure PATH includes OpenCode and Bun
export PATH="/root/.opencode/bin:/root/.bun/bin:$PATH"

# Debug: Check if opencode exists
echo "Checking OpenCode installation..."
ls -la /root/.opencode/bin/ 2>/dev/null || echo "OpenCode bin directory not found"
which opencode || echo "opencode not in PATH, using full path"

# Use full path as fallback
OPENCODE_BIN="${OPENCODE_PATH:-/root/.opencode/bin/opencode}"

if [ ! -f "$OPENCODE_BIN" ]; then
    echo "ERROR: OpenCode binary not found at $OPENCODE_BIN"
    echo "Attempting to install OpenCode..."
    curl -fsSL https://opencode.ai/install | bash
fi

# ============================================
# PERSISTENT STORAGE SETUP
# ============================================
# Create persistent directories on /data volume
echo "Setting up persistent storage..."
mkdir -p /data/sessions
mkdir -p /data/opencode/storage
mkdir -p /data/opencode/cache
mkdir -p /data/opencode/config

# Copy auth files from config to persistent storage if they don't exist
# (This preserves existing auth across deployments)
if [ -f "/root/.config/opencode/antigravity-accounts.json" ]; then
    if [ ! -f "/data/opencode/config/antigravity-accounts.json" ]; then
        echo "Copying antigravity-accounts.json to persistent storage..."
        cp /root/.config/opencode/antigravity-accounts.json /data/opencode/config/
    fi
fi

if [ -f "/root/.config/opencode/antigravity.json" ]; then
    if [ ! -f "/data/opencode/config/antigravity.json" ]; then
        echo "Copying antigravity.json to persistent storage..."
        cp /root/.config/opencode/antigravity.json /data/opencode/config/
    fi
fi

# Symlink OpenCode storage to persistent volume
# This ensures sessions persist across container restarts
if [ -d "/root/.local/share/opencode/storage" ] && [ ! -L "/root/.local/share/opencode/storage" ]; then
    echo "Moving existing storage to persistent volume..."
    cp -r /root/.local/share/opencode/storage/* /data/opencode/storage/ 2>/dev/null || true
    rm -rf /root/.local/share/opencode/storage
fi
mkdir -p /root/.local/share/opencode
ln -sfn /data/opencode/storage /root/.local/share/opencode/storage

# Symlink cache for plugin persistence
if [ -d "/root/.cache/opencode" ] && [ ! -L "/root/.cache/opencode" ]; then
    echo "Moving existing cache to persistent volume..."
    cp -r /root/.cache/opencode/* /data/opencode/cache/ 2>/dev/null || true
    rm -rf /root/.cache/opencode
fi
mkdir -p /root/.cache
ln -sfn /data/opencode/cache /root/.cache/opencode

# Symlink auth files from persistent storage back to config
if [ -f "/data/opencode/config/antigravity-accounts.json" ]; then
    ln -sf /data/opencode/config/antigravity-accounts.json /root/.config/opencode/antigravity-accounts.json
    echo "Linked antigravity-accounts.json from persistent storage"
fi

if [ -f "/data/opencode/config/antigravity.json" ]; then
    ln -sf /data/opencode/config/antigravity.json /root/.config/opencode/antigravity.json
    echo "Linked antigravity.json from persistent storage"
fi

echo "Persistent storage setup complete."

# ============================================
# PLUGIN INSTALLATION
# ============================================
echo "Ensuring OpenCode plugins are installed..."

# Pre-install plugins using bun to ensure they're ready before server starts
cd /root/.config/opencode
if [ -f "opencode.jsonc" ]; then
    # Extract plugin names and install them
    PLUGINS=$(grep -o '"opencode-[^"]*"' opencode.jsonc 2>/dev/null | tr -d '"' || true)
    if [ -n "$PLUGINS" ]; then
        echo "Installing plugins: $PLUGINS"
        mkdir -p /data/opencode/cache/node_modules
        cd /data/opencode/cache
        for plugin in $PLUGINS; do
            echo "Installing $plugin..."
            bun add "$plugin" 2>/dev/null || echo "Plugin $plugin may already be installed"
        done
    fi
fi
cd /app

# ============================================
# START OPENCODE SERVER
# ============================================
echo "Starting OpenCode server on port 8080..."
"$OPENCODE_BIN" serve --port 8080 &
OPENCODE_PID=$!

# Wait for server to be ready
echo "Waiting for OpenCode server..."
for i in {1..30}; do
    if curl -s http://127.0.0.1:8080/health > /dev/null 2>&1; then
        echo "OpenCode server ready!"
        break
    fi
    if [ $i -eq 30 ]; then
        echo "Warning: OpenCode server health check timed out, continuing anyway..."
    fi
    sleep 1
done

# ============================================
# START TELEGRAM BOT
# ============================================
echo "Starting Telegram bot..."
python bot.py &
BOT_PID=$!

# Handle shutdown gracefully
shutdown() {
    echo "Shutting down..."
    kill $BOT_PID 2>/dev/null || true
    kill $OPENCODE_PID 2>/dev/null || true
    exit 0
}

trap shutdown SIGTERM SIGINT

# Wait for either process to exit
wait -n
EXIT_CODE=$?

echo "A process exited with code $EXIT_CODE"
shutdown
