# VPS Deployment Guide

This guide explains how to deploy the OpenCode Telegram Bot to a VPS with the same configuration as your local setup.

## Prerequisites

- VPS with Ubuntu 22.04+ or Debian 12+
- Root access or sudo privileges
- Python 3.10+

## Step 1: Install OpenCode

```bash
# Install OpenCode
curl -fsSL https://opencode.ai/install | bash

# Verify installation
~/.opencode/bin/opencode --version
```

## Step 2: Install Dependencies

```bash
# Install Python dependencies
apt update && apt install -y python3 python3-pip

# Install bot dependencies
pip3 install python-telegram-bot
```

## Step 3: Clone the Bot

```bash
# Create directory
mkdir -p /opt/opencode-telegram
cd /opt/opencode-telegram

# Copy bot files (or git clone)
# git clone https://github.com/duckhoa-uit/opencode-telegram-bot.git .
```

## Step 4: Configure OpenCode

OpenCode uses `~/.config/opencode/` for configuration. You need to replicate your local config.

### 4.1 Create config directory

```bash
mkdir -p ~/.config/opencode
```

### 4.2 Copy opencode.jsonc

Create `~/.config/opencode/opencode.jsonc`:

```jsonc
{
  "$schema": "https://opencode.ai/config.json",
  "theme": "opencode",
  "model": "google/antigravity-claude-opus-4-5-thinking-medium",
  "autoupdate": true,
  "plugin": [
    "opencode-antigravity-auth@1.2.7",
    "oh-my-opencode"
  ],
  "provider": {
    "google": {
      "models": {
        "antigravity-gemini-3-pro-low": {
          "name": "Gemini 3 Pro Low (Antigravity)",
          "limit": { "context": 1048576, "output": 65535 },
          "modalities": { "input": ["text", "image", "pdf"], "output": ["text"] }
        },
        "antigravity-gemini-3-pro-high": {
          "name": "Gemini 3 Pro High (Antigravity)",
          "limit": { "context": 1048576, "output": 65535 },
          "modalities": { "input": ["text", "image", "pdf"], "output": ["text"] }
        },
        "antigravity-gemini-3-flash": {
          "name": "Gemini 3 Flash (Antigravity)",
          "limit": { "context": 1048576, "output": 65536 },
          "modalities": { "input": ["text", "image", "pdf"], "output": ["text"] }
        },
        "antigravity-claude-sonnet-4-5": {
          "name": "Claude Sonnet 4.5 (Antigravity)",
          "limit": { "context": 200000, "output": 64000 },
          "modalities": { "input": ["text", "image", "pdf"], "output": ["text"] }
        },
        "antigravity-claude-sonnet-4-5-thinking-low": {
          "name": "Claude Sonnet 4.5 Think Low (Antigravity)",
          "limit": { "context": 200000, "output": 64000 },
          "modalities": { "input": ["text", "image", "pdf"], "output": ["text"] }
        },
        "antigravity-claude-sonnet-4-5-thinking-medium": {
          "name": "Claude Sonnet 4.5 Think Medium (Antigravity)",
          "limit": { "context": 200000, "output": 64000 },
          "modalities": { "input": ["text", "image", "pdf"], "output": ["text"] }
        },
        "antigravity-claude-sonnet-4-5-thinking-high": {
          "name": "Claude Sonnet 4.5 Think High (Antigravity)",
          "limit": { "context": 200000, "output": 64000 },
          "modalities": { "input": ["text", "image", "pdf"], "output": ["text"] }
        },
        "antigravity-claude-opus-4-5-thinking-low": {
          "name": "Claude Opus 4.5 Think Low (Antigravity)",
          "limit": { "context": 200000, "output": 64000 },
          "modalities": { "input": ["text", "image", "pdf"], "output": ["text"] }
        },
        "antigravity-claude-opus-4-5-thinking-medium": {
          "name": "Claude Opus 4.5 Think Medium (Antigravity)",
          "limit": { "context": 200000, "output": 64000 },
          "modalities": { "input": ["text", "image", "pdf"], "output": ["text"] }
        },
        "antigravity-claude-opus-4-5-thinking-high": {
          "name": "Claude Opus 4.5 Think High (Antigravity)",
          "limit": { "context": 200000, "output": 64000 },
          "modalities": { "input": ["text", "image", "pdf"], "output": ["text"] }
        }
      }
    }
  }
}
```

### 4.3 Copy oh-my-opencode.json

Create `~/.config/opencode/oh-my-opencode.json`:

```json
{
  "$schema": "https://raw.githubusercontent.com/code-yeongyu/oh-my-opencode/master/assets/oh-my-opencode.schema.json",
  "google_auth": false,
  "agents": {
    "Sisyphus": {
      "model": "google/antigravity-claude-opus-4-5-thinking-high"
    },
    "librarian": {
      "model": "google/antigravity-claude-sonnet-4-5-thinking-medium"
    },
    "oracle": {
      "model": "google/antigravity-claude-opus-4-5-thinking-high"
    },
    "frontend-ui-ux-engineer": {
      "model": "google/antigravity-gemini-3-pro-high"
    },
    "document-writer": {
      "model": "google/antigravity-gemini-3-flash"
    },
    "multimodal-looker": {
      "model": "google/antigravity-gemini-3-flash"
    }
  }
}
```

### 4.4 Copy antigravity.json

Create `~/.config/opencode/antigravity.json`:

```json
{
  "$schema": "https://raw.githubusercontent.com/NoeFabris/opencode-antigravity-auth/main/assets/antigravity.schema.json",
  "quiet_mode": false,
  "debug": false,
  "log_dir": null,
  "keep_thinking": false,
  "session_recovery": true,
  "auto_resume": true,
  "resume_text": "continue",
  "empty_response_max_attempts": 4,
  "empty_response_retry_delay_ms": 2000,
  "tool_id_recovery": true,
  "claude_tool_hardening": true,
  "proactive_token_refresh": true,
  "proactive_refresh_buffer_seconds": 1800,
  "proactive_refresh_check_interval_seconds": 300,
  "auto_update": true,
  "signature_cache": {
    "enabled": true,
    "memory_ttl_seconds": 3600,
    "disk_ttl_seconds": 172800,
    "write_interval_seconds": 60
  }
}
```

### 4.5 Authenticate with Antigravity

**IMPORTANT:** Antigravity uses OAuth tokens that are tied to your Google account. You need to:

1. Copy `~/.config/opencode/antigravity-accounts.json` from your local machine to the VPS
2. This file contains your OAuth tokens - keep it secure!

```bash
# On your local machine
scp ~/.config/opencode/antigravity-accounts.json root@your-vps:~/.config/opencode/

# Or manually copy the contents
```

**Alternative:** Run `opencode auth` on the VPS to authenticate fresh:

```bash
~/.opencode/bin/opencode auth
# Follow the OAuth flow in a browser
```

## Step 5: Install OpenCode Plugins

```bash
cd ~/.config/opencode

# Install node dependencies for plugins
npm install

# Or if using bun
bun install
```

## Step 6: Configure the Bot

Create `/opt/opencode-telegram/.env`:

```bash
TELEGRAM_BOT_TOKEN=your-telegram-bot-token
TELEGRAM_ALLOWED_USER_IDS=your-user-id
OPENCODE_PATH=/root/.opencode/bin/opencode
OPENCODE_DEFAULT_CWD=/root
OPENCODE_LOG_FILE=/var/log/opencode-telegram/bot.log
OPENCODE_SESSIONS_FILE=/var/lib/opencode-telegram/sessions.json
```

Create log directories:

```bash
mkdir -p /var/log/opencode-telegram
mkdir -p /var/lib/opencode-telegram
```

## Step 7: Install Systemd Service

```bash
# Copy service file
cp /opt/opencode-telegram/opencode-telegram.service /etc/systemd/system/

# Edit the service to use EnvironmentFile
sed -i 's|Environment=TELEGRAM_BOT_TOKEN=.*|EnvironmentFile=/opt/opencode-telegram/.env|' /etc/systemd/system/opencode-telegram.service

# Reload systemd
systemctl daemon-reload

# Enable and start
systemctl enable opencode-telegram
systemctl start opencode-telegram

# Check status
systemctl status opencode-telegram
journalctl -u opencode-telegram -f
```

## Step 8: Test

```bash
# Test opencode directly
~/.opencode/bin/opencode run --format json "say hello"

# Check bot logs
tail -f /var/log/opencode-telegram/bot.log
```

## Troubleshooting

### OpenCode not found
```bash
export PATH="$HOME/.opencode/bin:$PATH"
# Add to ~/.bashrc for persistence
```

### Authentication errors
```bash
# Re-authenticate
~/.opencode/bin/opencode auth
```

### Plugin errors
```bash
cd ~/.config/opencode
rm -rf node_modules bun.lock
bun install
```

## Security Notes

1. **antigravity-accounts.json** contains OAuth tokens - protect it!
2. Set proper file permissions:
   ```bash
   chmod 600 ~/.config/opencode/antigravity-accounts.json
   chmod 600 /opt/opencode-telegram/.env
   ```
3. Consider running the bot as a non-root user

## Files to Copy from Local Machine

| File | Location on VPS |
|------|-----------------|
| `bot.py` | `/opt/opencode-telegram/bot.py` |
| `requirements.txt` | `/opt/opencode-telegram/requirements.txt` |
| `.env` | `/opt/opencode-telegram/.env` |
| `opencode.jsonc` | `~/.config/opencode/opencode.jsonc` |
| `oh-my-opencode.json` | `~/.config/opencode/oh-my-opencode.json` |
| `antigravity.json` | `~/.config/opencode/antigravity.json` |
| `antigravity-accounts.json` | `~/.config/opencode/antigravity-accounts.json` |
