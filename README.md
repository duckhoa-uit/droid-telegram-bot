# OpenCode Telegram Bot

A Telegram bot that interfaces with [OpenCode AI Coding Agent](https://opencode.ai), allowing you to interact with OpenCode via Telegram messages.

## Features

- 💬 **Chat with OpenCode** - Send messages and get AI-powered responses
- ⚡ **Live Streaming** - Watch tool calls in real-time as OpenCode works
- 📂 **Session Management** - Persistent sessions with working directory context
- 🔐 **Access Control** - Restrict bot access to specific Telegram users
- 🔧 **Git Integration** - Quick `/git` commands for common operations
- 🚀 **Deploy to Fly.io** - One-command deployment to the cloud

## Quick Start

### Option 1: Deploy to a VPS (Recommended)

Deploy to any Ubuntu/Debian VPS with a one-liner:

```bash
# SSH into your VPS, then run:
curl -fsSL https://raw.githubusercontent.com/duckhoa-uit/droid-telegram-bot/main/scripts/setup-vps.sh | bash
```

See [docs/DEPLOY_VPS.md](docs/DEPLOY_VPS.md) for full instructions.

### Option 2: Deploy to Fly.io

1. **Install Fly CLI**
   ```bash
   curl -L https://fly.io/install.sh | sh
   fly auth login
   ```

2. **Clone and configure**
   ```bash
   git clone https://github.com/duckhoa-uit/droid-telegram-bot.git
   cd opencode-telegram-bot
   
   # Copy your OpenCode config
   cp ~/.config/opencode/opencode.jsonc config/opencode/
   # If using Antigravity auth:
   cp ~/.config/opencode/antigravity.json config/opencode/
   cp ~/.config/opencode/antigravity-accounts.json config/opencode/
   ```

3. **Deploy**
   ```bash
   fly apps create your-bot-name
   fly volumes create bot_data --size 1 --region sin
   fly secrets set TELEGRAM_BOT_TOKEN="your-bot-token"
   fly secrets set TELEGRAM_ALLOWED_USER_IDS="your-telegram-id"
   fly deploy
   ```

### Option 3: Run Locally

```bash
# Install dependencies
pip install -r requirements.txt

# Configure
cp .env.example .env
# Edit .env with your values

# Run
python bot.py
```

## Configuration

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `TELEGRAM_BOT_TOKEN` | ✅ | - | Telegram bot token from @BotFather |
| `TELEGRAM_ALLOWED_USER_IDS` | ✅ | - | Comma-separated Telegram user IDs |
| `OPENCODE_PATH` | ❌ | `opencode` | Path to OpenCode CLI |
| `OPENCODE_DEFAULT_CWD` | ❌ | `~` | Default working directory |
| `OPENCODE_SERVER_URL` | ❌ | `http://127.0.0.1:8080` | OpenCode server URL |

### OpenCode Config

Copy your OpenCode configuration to `config/opencode/`:

```
config/opencode/
├── opencode.jsonc          # Main config (model, plugins)
├── antigravity.json        # Antigravity settings (optional)
└── antigravity-accounts.json # OAuth tokens (optional, gitignored)
```

See [config/opencode/README.md](config/opencode/README.md) for configuration examples.

## Commands

| Command | Description |
|---------|-------------|
| `/start` | Welcome message |
| `/help` | Detailed help |
| `/new [path]` | Start new session |
| `/session` | List sessions |
| `/session <id>` | Switch to session |
| `/cwd` | Show working directory |
| `/stream` | Toggle live updates |
| `/status` | Bot status |
| `/git [args]` | Run git commands |
| `/stop` | Stop running process |

## Project Structure

```
droid-telegram-bot/
├── bot.py              # Main bot application
├── requirements.txt    # Python dependencies
├── Dockerfile          # Container build (Fly.io)
├── fly.toml            # Fly.io configuration
├── start.sh            # Container startup script
├── config/
│   └── opencode/       # OpenCode configuration
├── docs/
│   └── DEPLOY_VPS.md         # VPS deployment guide
├── scripts/
│   └── setup-vps.sh          # VPS setup script
├── systemd/
│   ├── opencode-server.service        # OpenCode server service
│   └── opencode-telegram-bot.service  # Bot service
└── .env.example        # Environment template
```

## Security Notes

- **Never commit tokens** - Use environment variables or Fly secrets
- **Protect OAuth tokens** - `antigravity-accounts.json` is gitignored
- **Restrict access** - Always set `TELEGRAM_ALLOWED_USER_IDS`

## Getting Your IDs

- **Telegram Bot Token**: Message [@BotFather](https://t.me/botfather) and create a bot
- **Your Telegram ID**: Message [@userinfobot](https://t.me/userinfobot)

## Deployment Comparison

| Platform | RAM | CPU | Storage | Monthly Cost |
|----------|-----|-----|---------|--------------|
| Oracle Cloud (Free Tier) | Up to 24GB | 4 ARM cores | 200GB | **$0** |
| Hetzner | 2GB | 1 vCPU | 20GB | €3.79 |
| Fly.io | 512MB-2GB | Shared | 1GB | $5-15 |
| DigitalOcean | 1GB | 1 vCPU | 25GB | $6 |

## License

MIT License - see [LICENSE](LICENSE)

## Contributing

Contributions welcome! Please open an issue or PR.
