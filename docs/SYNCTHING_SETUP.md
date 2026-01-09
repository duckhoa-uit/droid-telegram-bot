# SyncThing Setup Guide

Sync your local repos with your VPS so changes are automatically reflected. This lets you code locally and immediately use the Telegram bot to interact with your updated code.

## How It Works

```
┌─────────────────┐     SyncThing      ┌─────────────────┐
│   Local Mac     │  ←───────────────→ │      VPS        │
│   ~/repos/      │   Real-time sync   │ ~/repos/        │
└─────────────────┘                    └─────────────────┘
                                              ↓
                                       Telegram Bot
                                              ↓
                                       Chat with repos!
```

## Prerequisites

- VPS already set up with the Telegram bot (see [DEPLOY_VPS.md](DEPLOY_VPS.md))
- Local machine with your repos

## Setup on VPS

### 1. Install SyncThing

```bash
# Add SyncThing repository
curl -s https://syncthing.net/release-key.txt | sudo gpg --dearmor -o /usr/share/keyrings/syncthing-archive-keyring.gpg
echo "deb [signed-by=/usr/share/keyrings/syncthing-archive-keyring.gpg] https://apt.syncthing.net/ syncthing stable" | sudo tee /etc/apt/sources.list.d/syncthing.list

# Install
sudo apt update
sudo apt install -y syncthing
```

### 2. Create Repos Directory

```bash
mkdir -p ~/repos
```

### 3. Start SyncThing (First Run)

```bash
syncthing
```

Press `Ctrl+C` after it starts to stop it. This creates the config files.

### 4. Configure Remote Access

Edit the config to allow remote web UI access:

```bash
# New versions use this path:
nano ~/.local/state/syncthing/config.xml

# Older versions use:
# nano ~/.config/syncthing/config.xml
```

Find and change:
```xml
<gui enabled="true" tls="false" debugging="false">
    <address>127.0.0.1:8384</address>
```

To:
```xml
<gui enabled="true" tls="true" debugging="false">
    <address>0.0.0.0:8384</address>
```

Add authentication (important!):
```xml
    <user>your_username</user>
    <password>your_password_hash</password>
```

### 5. Enable Systemd Service

SyncThing installed via `apt` includes a built-in service. Just enable it:

```bash
# Enable and start for your user
sudo systemctl enable syncthing@$USER
sudo systemctl start syncthing@$USER

# Verify it's running
sudo systemctl status syncthing@$USER
```

> **Note:** The `@$USER` syntax runs SyncThing as your user, not root.

### 6. Open Firewall (if needed)

```bash
# Allow SyncThing ports
sudo ufw allow 8384/tcp   # Web UI
sudo ufw allow 22000/tcp  # Sync protocol
sudo ufw allow 21027/udp  # Discovery
```

## Setup on Local Machine (macOS)

### 1. Install SyncThing

```bash
brew install syncthing

# Start as background service
brew services start syncthing
```

### 2. Access Web UI

Open: http://127.0.0.1:8384

### 3. Add VPS as Remote Device

1. Get your VPS Device ID:
   - SSH into VPS: `syncthing -device-id` or check the web UI at `http://YOUR_VPS_IP:8384`

2. In local SyncThing web UI:
   - Go to **Actions** → **Show ID** (copy your local ID)
   - Click **Add Remote Device**
   - Paste VPS Device ID
   - Name it (e.g., "VPS")
   - Save

3. On VPS web UI, accept the connection request

### 4. Share Your Repos Folder

1. In local SyncThing:
   - Click **Add Folder**
   - Folder Path: `~/repos` (or wherever your repos are)
   - Folder Label: "repos"
   - Under **Sharing** tab, check your VPS device
   - Save

2. On VPS, accept the folder share
   - Set folder path to `~/repos`

## Configure the Telegram Bot

Update your VPS `.env` to point to the synced repos:

```bash
# Edit /opt/opencode-bot/.env
OPENCODE_DEFAULT_CWD=/home/YOUR_USERNAME/repos
```

Restart the bot:
```bash
sudo systemctl restart opencode-telegram-bot
```

## Usage

1. **Make changes locally** → SyncThing syncs to VPS (usually within seconds)
2. **Open Telegram** → `/new ~/repos/my-project`
3. **Chat with your code** → OpenCode sees your latest changes!

## Tips

### Ignore Node Modules and Build Artifacts

Create `.stignore` in your repos folder:

```bash
cat > ~/repos/.stignore << 'EOF'
node_modules
.next
dist
build
.git
*.log
.DS_Store
__pycache__
.venv
venv
EOF
```

### Monitor Sync Status

```bash
# Check if syncthing is running
sudo systemctl status syncthing

# View sync status
syncthing cli show connections
```

### Conflict Resolution

SyncThing creates `.sync-conflict-*` files if both sides change simultaneously. Check for these periodically:

```bash
find ~/repos -name "*.sync-conflict-*"
```

## Troubleshooting

### Devices Not Connecting

1. Check firewall allows ports 22000, 21027
2. Verify both devices show as "Connected" in web UI
3. Check `journalctl -u syncthing -f` for errors

### Slow Sync

1. Reduce folder size with `.stignore`
2. Check VPS network/disk speed
3. Consider using "Send Only" on local for one-way sync

### Web UI Not Accessible on VPS

```bash
# Check if running
sudo systemctl status syncthing

# Check it's listening
sudo netstat -tlnp | grep 8384
```

## Security Notes

- **Enable HTTPS** on the web UI (SyncThing does this by default)
- **Set a strong GUI password**
- **Consider SSH tunneling** instead of exposing port 8384:
  ```bash
  ssh -L 8384:localhost:8384 user@your-vps
  # Then access http://localhost:8384
  ```

## Alternative: One-Way Sync with rsync

If you only need to push changes TO the VPS (simpler setup):

```bash
# Add to your local shell aliases
alias sync-repos='rsync -avz --delete --exclude="node_modules" --exclude=".git" ~/repos/ user@your-vps:~/repos/'
```

Or use a file watcher like `fswatch` for automatic sync.
