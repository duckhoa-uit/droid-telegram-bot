# OpenCode Telegram Bot

A Telegram bot that interfaces with [OpenCode AI Coding Agent](https://opencode.ai), allowing you to interact with OpenCode via Telegram messages.

## Features

- 💬 **Chat with OpenCode** - Send messages and get AI-powered responses
- ⚡ **Live Streaming** - Watch tool calls in real-time as OpenCode works
- 📂 **Session Management** - Persistent sessions with working directory context
- 🔐 **Access Control** - Restrict bot access to specific Telegram users
- 🎚️ **Autonomy Levels** - Control permissions (off/low/medium/high/unsafe)
- 🔧 **Git Integration** - Quick `/git` commands for common operations
- 🤖 **Multi-Model** - Supports Claude, GPT, Gemini via OpenCode

## Prerequisites

- Python 3.10+
- [OpenCode](https://opencode.ai) installed and configured
- Telegram bot token (from [@BotFather](https://t.me/botfather))
- Your Telegram user ID (from [@userinfobot](https://t.me/userinfobot))

## Quick Start

### 1. Install OpenCode

```bash
# Install OpenCode
curl -fsSL https://opencode.ai/install | bash

# Verify installation
~/.opencode/bin/opencode --version

# Authenticate (follow OAuth flow)
~/.opencode/bin/opencode auth
```

### 2. Clone and Install

```bash
git clone https://github.com/duckhoa-uit/opencode-telegram-bot.git
cd opencode-telegram-bot
pip install -r requirements.txt
```

### 3. Configure Environment

```bash
cp .env.example .env
# Edit .env with your values
```

Required environment variables:
- `TELEGRAM_BOT_TOKEN` - Your bot token from BotFather
- `TELEGRAM_ALLOWED_USER_IDS` - Comma-separated Telegram user IDs

### 4. Run

```bash
# Direct
python bot.py

# Or with environment variables inline
TELEGRAM_BOT_TOKEN=your-token TELEGRAM_ALLOWED_USER_IDS=123456 python bot.py
```

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `TELEGRAM_BOT_TOKEN` | ✅ | - | Telegram bot token from @BotFather |
| `TELEGRAM_ALLOWED_USER_IDS` | ✅ | - | Comma-separated Telegram user IDs |
| `OPENCODE_PATH` | ❌ | `opencode` | Path to OpenCode CLI |
| `OPENCODE_DEFAULT_CWD` | ❌ | `~` | Default working directory |
| `OPENCODE_SERVER_URL` | ❌ | `http://127.0.0.1:8080` | OpenCode server URL for HTTP API mode |
| `OPENCODE_MODEL_PROVIDER` | ❌ | `anthropic` | Model provider for API mode |
| `OPENCODE_MODEL` | ❌ | `claude-sonnet-4-20250514` | Model ID for API mode |
| `OPENCODE_LOG_FILE` | ❌ | `./bot.log` | Log file path |
| `OPENCODE_SESSIONS_FILE` | ❌ | `./sessions.json` | Sessions file |

## Commands

| Command | Description |
|---------|-------------|
| `/start` | Welcome message and quick help |
| `/help` | Detailed help |
| `/new [path]` | Start new session (optionally in directory) |
| `/session` | List recent sessions |
| `/session <id>` | Switch to a session |
| `/auto [level]` | Set autonomy level (off/low/medium/high/unsafe) |
| `/cwd` | Show current working directory |
| `/stream` | Toggle live tool updates on/off |
| `/status` | Bot and OpenCode status |
| `/git [args]` | Run git commands in current directory |
| `/stop` | Stop currently running process |

## Autonomy Levels

Control permissions with the `/auto` command:

| Level | Description |
|-------|-------------|
| `off` | Read-only mode (default) - no tool execution |
| `low` | Safe tools only |
| `medium` | Most tools allowed |
| `high` | All tools, asks for risky ones |
| `unsafe` | Skip all permission checks |

> **Note:** OpenCode uses config-based permissions. See `~/.config/opencode/opencode.jsonc` for configuration.

## Usage Tips

- **Reply to continue** - Reply to any bot message to continue that session
- **Working directories** - Use `/new ~/projects/myapp` to set context
- **Live updates** - Watch OpenCode's progress with streaming enabled (default)
- **Autonomy control** - Use `/auto high` to enable tool execution
- **Permission prompts** - Bot shows Once/Always/Deny buttons for elevated permissions

## Production Deployment

See [DEPLOYMENT.md](DEPLOYMENT.md) for detailed VPS deployment instructions.

### Quick Deploy with systemd

```bash
# Copy service file
sudo cp opencode-telegram.service /etc/systemd/system/

# Edit with your environment variables
sudo nano /etc/systemd/system/opencode-telegram.service

# Enable and start
sudo systemctl enable opencode-telegram
sudo systemctl start opencode-telegram

# Check status
sudo systemctl status opencode-telegram
```

### Export Config for VPS

```bash
# Export your local OpenCode config
./scripts/export-config.sh ./deploy-config

# Copy to VPS
scp -r ./deploy-config/* root@your-vps:~/.config/opencode/
```

## OpenCode Configuration

The bot uses your OpenCode configuration from `~/.config/opencode/`:

| File | Purpose |
|------|---------|
| `opencode.jsonc` | Main config (model, plugins, providers) |
| `oh-my-opencode.json` | Agent configuration (if using oh-my-opencode) |
| `antigravity.json` | Antigravity plugin settings |
| `antigravity-accounts.json` | OAuth tokens (keep secure!) |

## Security Notes

- **Never commit tokens** - Use environment variables or `.env` files
- **Protect OAuth tokens** - `antigravity-accounts.json` contains sensitive data
- **Restrict access** - Always set `TELEGRAM_ALLOWED_USER_IDS`
- **Review permissions** - The bot can execute commands via OpenCode

## Migration from Droid

See [MIGRATION_ROADMAP.md](MIGRATION_ROADMAP.md) for the full migration plan.

## License

MIT License - see [LICENSE](LICENSE)

## Contributing

Contributions welcome! Please open an issue or PR.
