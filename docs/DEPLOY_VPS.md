# VPS Deployment Guide

This guide covers deploying the OpenCode Telegram Bot to any Ubuntu/Debian VPS.

## Prerequisites

- Ubuntu/Debian VPS with SSH access
- SSH key pair for server access
- At least 1GB RAM recommended

## Quick Setup (One-liner)

SSH into your VPS and run:

```bash
curl -fsSL https://raw.githubusercontent.com/duckhoa-uit/droid-telegram-bot/main/scripts/setup-vps.sh | bash
```

This installs everything automatically. Then follow the on-screen instructions to configure your bot.

## Manual Setup

### 1. Update System & Install Dependencies

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install required packages
sudo apt install -y curl git python3 python3-pip python3-venv unzip

# Install Bun (required for OpenCode plugins)
curl -fsSL https://bun.sh/install | bash
source ~/.bashrc
```

### 2. Install OpenCode

```bash
curl -fsSL https://opencode.ai/install | bash
source ~/.bashrc

# Verify installation
opencode --version
```

### 3. Create Application Directory

```bash
sudo mkdir -p /opt/opencode-bot
sudo chown $USER:$USER /opt/opencode-bot
cd /opt/opencode-bot
```

### 4. Clone Repository

```bash
cd /opt/opencode-bot
git clone https://github.com/duckhoa-uit/droid-telegram-bot.git .
```

### 5. Setup Python Environment

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 6. Configure OpenCode

```bash
# Create OpenCode config directory
mkdir -p ~/.config/opencode

# Copy config files
cp -r config/opencode/* ~/.config/opencode/

# Create data directories
mkdir -p /opt/opencode-bot/data/sessions
mkdir -p ~/.local/share/opencode/storage
mkdir -p ~/.cache/opencode
```

### 7. Setup Antigravity Auth

You need to authenticate with the Antigravity plugin. Run OpenCode once to trigger the auth flow:

```bash
opencode auth login
```

Select **OAuth with Google (Antigravity)** and complete the browser authentication.

Alternatively, copy your existing `antigravity-accounts.json` to `~/.config/opencode/`:

```bash
# If you have existing auth, copy it
scp your-local-machine:~/.config/opencode/antigravity-accounts.json ~/.config/opencode/
```

### 8. Create Environment File

```bash
cat > /opt/opencode-bot/.env << 'EOF'
TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here
TELEGRAM_ALLOWED_USER_IDS=your_telegram_user_id

# OpenCode settings
OPENCODE_PATH=/home/YOUR_USERNAME/.opencode/bin/opencode
OPENCODE_SERVER_URL=http://127.0.0.1:8080
OPENCODE_SESSIONS_FILE=/opt/opencode-bot/data/sessions/sessions.json
OPENCODE_DEFAULT_CWD=/opt/opencode-bot
EOF
```

Replace:
- `your_telegram_bot_token_here` with your bot token from [@BotFather](https://t.me/BotFather)
- `your_telegram_user_id` with your Telegram user ID (get it from [@userinfobot](https://t.me/userinfobot))
- `YOUR_USERNAME` with your actual username

## 9. Create Systemd Services

The repository includes pre-configured systemd service files in `systemd/`.

### Install Service Files

```bash
# Copy and configure service files (adjusts paths automatically)
cd /opt/opencode-bot

# Install OpenCode server service
sudo sed -e "s|/home/ubuntu|$HOME|g" \
         -e "s|User=ubuntu|User=$USER|g" \
         -e "s|Group=ubuntu|Group=$USER|g" \
         systemd/opencode-server.service | sudo tee /etc/systemd/system/opencode-server.service

# Install Telegram bot service  
sudo sed -e "s|/home/ubuntu|$HOME|g" \
         -e "s|User=ubuntu|User=$USER|g" \
         -e "s|Group=ubuntu|Group=$USER|g" \
         systemd/opencode-telegram-bot.service | sudo tee /etc/systemd/system/opencode-telegram-bot.service
```

### Enable and Start Services

```bash
sudo systemctl daemon-reload
sudo systemctl enable opencode-server opencode-telegram-bot
sudo systemctl start opencode-server
sudo systemctl start opencode-telegram-bot
```

## 10. Verify Deployment

### Check service status:

```bash
sudo systemctl status opencode-server
sudo systemctl status opencode-telegram-bot
```

### View logs:

```bash
# OpenCode server logs
sudo journalctl -u opencode-server -f

# Bot logs
sudo journalctl -u opencode-telegram-bot -f
```

### Test the bot:

Send a message to your bot on Telegram!

## Maintenance

### Update the bot:

```bash
cd /opt/opencode-bot
git pull
source venv/bin/activate
pip install -r requirements.txt
sudo systemctl restart opencode-telegram-bot
```

### Update OpenCode:

```bash
opencode upgrade
sudo systemctl restart opencode-server opencode-telegram-bot
```

### View recent logs:

```bash
sudo journalctl -u opencode-telegram-bot --since "1 hour ago"
```

### Restart services:

```bash
sudo systemctl restart opencode-server opencode-telegram-bot
```

## Optional: Setup Auto-Updates

Create a cron job to pull updates automatically:

```bash
crontab -e
```

Add:

```cron
# Update bot daily at 3 AM
0 3 * * * cd /opt/opencode-bot && git pull && /opt/opencode-bot/venv/bin/pip install -r requirements.txt -q
```

## Troubleshooting

### Bot not responding

1. Check if services are running:
   ```bash
   sudo systemctl status opencode-server opencode-telegram-bot
   ```

2. Check OpenCode server health:
   ```bash
   curl http://127.0.0.1:8080/health
   ```

3. View bot logs for errors:
   ```bash
   sudo journalctl -u opencode-telegram-bot -n 100
   ```

### Antigravity auth errors

Re-authenticate:
```bash
sudo systemctl stop opencode-server opencode-telegram-bot
opencode auth login
sudo systemctl start opencode-server opencode-telegram-bot
```

### Session not found errors

Clear stale sessions:
```bash
rm /opt/opencode-bot/data/sessions/sessions.json
sudo systemctl restart opencode-telegram-bot
```

### Out of memory

1. Check memory usage: `free -h`
2. Consider upgrading your VPS or reducing concurrent sessions

## VPS Providers

Here are some VPS options:

| Provider | RAM | CPU | Storage | Monthly Cost |
|----------|-----|-----|---------|--------------|
| Oracle Cloud (Free Tier) | Up to 24GB | 4 ARM cores | 200GB | **$0** |
| Hetzner | 2GB | 1 vCPU | 20GB | €3.79 |
| DigitalOcean | 1GB | 1 vCPU | 25GB | $6 |
| Vultr | 1GB | 1 vCPU | 25GB | $6 |
| Linode | 1GB | 1 vCPU | 25GB | $5 |
