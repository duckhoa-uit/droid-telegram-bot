# OpenCode Configuration

This directory contains your OpenCode configuration files.

## Setup

1. Copy the example config:
   ```bash
   cp opencode.jsonc.example opencode.jsonc
   ```

2. Edit `opencode.jsonc` with your preferred model and API keys.

3. (Optional) Add additional config files:
   - `antigravity.json` - For Google Antigravity auth
   - `antigravity-accounts.json` - OAuth tokens (auto-generated)
   - `oh-my-opencode.json` - For oh-my-opencode plugin

## Example Configurations

### Using Anthropic API directly
```jsonc
{
  "$schema": "https://opencode.ai/config.json",
  "model": "anthropic/claude-sonnet-4",
  "provider": {
    "anthropic": {
      "apiKey": "${ANTHROPIC_API_KEY}"
    }
  }
}
```

### Using OpenAI
```jsonc
{
  "$schema": "https://opencode.ai/config.json",
  "model": "openai/gpt-4o",
  "provider": {
    "openai": {
      "apiKey": "${OPENAI_API_KEY}"
    }
  }
}
```

### Using Google Antigravity (requires OAuth)
```jsonc
{
  "$schema": "https://opencode.ai/config.json",
  "model": "google/antigravity-claude-opus-4-5-thinking-medium",
  "plugin": ["opencode-antigravity-auth@1.2.7"],
  "provider": {
    "google": {
      "models": {
        // Custom model definitions
      }
    }
  }
}
```

## Notes

- API keys can be set via environment variables (e.g., `${ANTHROPIC_API_KEY}`)
- Or set them as Fly.io secrets: `fly secrets set ANTHROPIC_API_KEY=sk-...`
- The `antigravity-accounts.json` file contains OAuth tokens and is gitignored
