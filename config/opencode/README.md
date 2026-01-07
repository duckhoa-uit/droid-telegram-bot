# OpenCode Configuration

This directory should contain your OpenCode configuration files.

## Setup

Copy your local OpenCode config files here:

```bash
cp ~/.config/opencode/* config/opencode/
```

The deployment scripts will copy these files to the server:
- **Fly.io**: Dockerfile copies to `/root/.config/opencode/`
- **VPS**: setup-vps.sh copies to `$HOME/.config/opencode/`

## Reference

For OpenCode configuration options, see: https://opencode.ai/docs/config
