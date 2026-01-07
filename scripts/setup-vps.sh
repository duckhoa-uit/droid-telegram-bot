#!/bin/bash
#
# OpenCode Telegram Bot - VPS Setup Script
# 
# Usage: curl -fsSL https://raw.githubusercontent.com/duckhoa-uit/droid-telegram-bot/main/scripts/setup-vps.sh | bash
#
# This script sets up the OpenCode Telegram Bot on any Ubuntu/Debian VPS
#

set -e

echo "=========================================="
echo "OpenCode Telegram Bot - VPS Setup"
echo "=========================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if running as root
if [ "$EUID" -eq 0 ]; then
    echo -e "${RED}Please do not run this script as root. Run as your regular user.${NC}"
    exit 1
fi

# Detect username
USERNAME=$(whoami)
HOME_DIR=$(eval echo ~$USERNAME)

echo -e "${GREEN}Running as user: $USERNAME${NC}"
echo -e "${GREEN}Home directory: $HOME_DIR${NC}"

# Step 1: Update system
echo -e "\n${YELLOW}[1/8] Updating system...${NC}"
sudo apt update && sudo apt upgrade -y

# Step 2: Install dependencies
echo -e "\n${YELLOW}[2/8] Installing dependencies...${NC}"
sudo apt install -y curl git python3 python3-pip python3-venv unzip

# Step 3: Install Bun
echo -e "\n${YELLOW}[3/8] Installing Bun...${NC}"
if ! command -v bun &> /dev/null; then
    curl -fsSL https://bun.sh/install | bash
    export BUN_INSTALL="$HOME_DIR/.bun"
    export PATH="$BUN_INSTALL/bin:$PATH"
else
    echo "Bun already installed"
fi

# Step 4: Install OpenCode
echo -e "\n${YELLOW}[4/8] Installing OpenCode...${NC}"
if ! command -v opencode &> /dev/null; then
    curl -fsSL https://opencode.ai/install | bash
    export PATH="$HOME_DIR/.opencode/bin:$PATH"
else
    echo "OpenCode already installed"
fi

# Step 5: Clone repository
echo -e "\n${YELLOW}[5/8] Setting up application...${NC}"
APP_DIR="/opt/opencode-bot"

if [ -d "$APP_DIR" ]; then
    echo "Application directory exists, updating..."
    cd "$APP_DIR"
    git pull
else
    sudo mkdir -p "$APP_DIR"
    sudo chown $USERNAME:$USERNAME "$APP_DIR"
    git clone https://github.com/duckhoa-uit/droid-telegram-bot.git "$APP_DIR"
    cd "$APP_DIR"
fi

# Step 6: Setup Python environment
echo -e "\n${YELLOW}[6/8] Setting up Python environment...${NC}"
if [ ! -d "$APP_DIR/venv" ]; then
    python3 -m venv "$APP_DIR/venv"
fi
source "$APP_DIR/venv/bin/activate"
pip install -r requirements.txt

# Step 7: Setup OpenCode config
echo -e "\n${YELLOW}[7/8] Setting up OpenCode configuration...${NC}"
mkdir -p "$HOME_DIR/.config/opencode"
mkdir -p "$HOME_DIR/.local/share/opencode/storage"
mkdir -p "$HOME_DIR/.cache/opencode"
mkdir -p "$APP_DIR/data/sessions"

# Copy config files if they don't exist
if [ ! -f "$HOME_DIR/.config/opencode/opencode.jsonc" ]; then
    cp -r "$APP_DIR/config/opencode/"* "$HOME_DIR/.config/opencode/"
    echo "Copied OpenCode config files"
fi

# Step 8: Create environment file template
echo -e "\n${YELLOW}[8/8] Creating configuration files...${NC}"

if [ ! -f "$APP_DIR/.env" ]; then
    cat > "$APP_DIR/.env" << EOF
# Telegram Bot Configuration
TELEGRAM_BOT_TOKEN=YOUR_BOT_TOKEN_HERE
TELEGRAM_ALLOWED_USER_IDS=YOUR_USER_ID_HERE

# OpenCode Settings
OPENCODE_PATH=$HOME_DIR/.opencode/bin/opencode
OPENCODE_SERVER_URL=http://127.0.0.1:8080
OPENCODE_SESSIONS_FILE=$APP_DIR/data/sessions/sessions.json
OPENCODE_DEFAULT_CWD=$APP_DIR
EOF
    echo -e "${YELLOW}Created .env template - please edit with your credentials${NC}"
fi

# Install systemd service files from repo
echo -e "\n${GREEN}Installing systemd service files...${NC}"

# Copy service files and substitute paths
sed -e "s|/home/ubuntu|$HOME_DIR|g" \
    -e "s|User=ubuntu|User=$USERNAME|g" \
    -e "s|Group=ubuntu|Group=$USERNAME|g" \
    "$APP_DIR/systemd/opencode-server.service" | sudo tee /etc/systemd/system/opencode-server.service > /dev/null

sed -e "s|/home/ubuntu|$HOME_DIR|g" \
    -e "s|User=ubuntu|User=$USERNAME|g" \
    -e "s|Group=ubuntu|Group=$USERNAME|g" \
    "$APP_DIR/systemd/opencode-telegram-bot.service" | sudo tee /etc/systemd/system/opencode-telegram-bot.service > /dev/null

sudo systemctl daemon-reload

echo ""
echo "=========================================="
echo -e "${GREEN}Setup Complete!${NC}"
echo "=========================================="
echo ""
echo "Next steps:"
echo ""
echo "1. Edit the .env file with your credentials:"
echo -e "   ${YELLOW}nano $APP_DIR/.env${NC}"
echo ""
echo "2. Setup Antigravity auth (for Google AI models):"
echo -e "   ${YELLOW}opencode auth login${NC}"
echo "   Select 'OAuth with Google (Antigravity)' and complete browser auth"
echo ""
echo "3. Start the services:"
echo -e "   ${YELLOW}sudo systemctl enable opencode-server opencode-telegram-bot${NC}"
echo -e "   ${YELLOW}sudo systemctl start opencode-server${NC}"
echo -e "   ${YELLOW}sudo systemctl start opencode-telegram-bot${NC}"
echo ""
echo "4. Check status:"
echo -e "   ${YELLOW}sudo systemctl status opencode-telegram-bot${NC}"
echo ""
echo "5. View logs:"
echo -e "   ${YELLOW}sudo journalctl -u opencode-telegram-bot -f${NC}"
echo ""
