# Migration Roadmap: Droid → OpenCode

## Overview

This document outlines the 4-phase migration plan to refactor the Telegram bot from Factory's Droid CLI to OpenCode.

**Current State:** Bot uses `droid exec` via subprocess  
**Target State:** Bot uses `opencode run` (Phase 1-2) or `opencode-client` API (Phase 3-4)

---

## Phase 1: CLI Drop-in Migration (Minimal Changes)

**Goal:** Replace `droid` CLI calls with `opencode run` while preserving all functionality.

**Estimated Effort:** 2-4 hours

### Tasks

| Task | File | Description |
|------|------|-------------|
| 1.1 | `bot.py` | Rename `DROID_PATH` → `OPENCODE_PATH` |
| 1.2 | `bot.py` | Update command construction: `droid exec` → `opencode run` |
| 1.3 | `bot.py` | Add `--format json` flag for streaming |
| 1.4 | `bot.py` | Change `-s` → `--session` for session continuation |
| 1.5 | `bot.py` | Adapt `--auto` flag handling (config-based in OpenCode) |
| 1.6 | `bot.py` | Update `/status` to use `opencode --version` |
| 1.7 | `bot.py` | Update all user-facing text: "Droid" → "OpenCode" |
| 1.8 | `.env.example` | Update environment variable names |
| 1.9 | `README.md` | Update documentation |

### Command Mapping

```python
# Before (Droid)
cmd = [DROID_PATH, "exec"]
if autonomy_level != "off":
    cmd.extend(["--auto", autonomy_level])
if session_id:
    cmd.extend(["-s", session_id])
cmd.append(message)

# After (OpenCode)
cmd = [OPENCODE_PATH, "run", "--format", "json"]
if session_id:
    cmd.extend(["--session", session_id])
cmd.append(message)
```

### Autonomy Level Handling

OpenCode uses config-based permissions instead of `--auto` flag:

| Droid `--auto` | OpenCode Equivalent |
|----------------|---------------------|
| `off` | Default (asks for permissions) |
| `low` | `permissions.bash: "deny"` |
| `medium` | `permissions.bash: "ask"` |
| `high` | `permissions.bash: "allow"` |
| `unsafe` | All permissions: `"allow"` |

**Implementation:** Create per-session `opencode.json` or use environment config.

---

## Phase 2: Server Daemon Mode

**Goal:** Run `opencode serve` as daemon for faster response times (no cold boot).

**Estimated Effort:** 1-2 hours

### Tasks

| Task | Description |
|------|-------------|
| 2.1 | Create systemd service for `opencode serve --port 8080` |
| 2.2 | Update CLI calls to use `--attach http://localhost:8080` |
| 2.3 | Add health check for server availability |
| 2.4 | Implement fallback to direct CLI if server unavailable |

### Benefits
- ~5-10x faster response time (no process startup)
- Shared session state across requests
- Better resource utilization

---

## Phase 3: HTTP API Migration

**Goal:** Replace subprocess calls with `opencode-client` Python library.

**Estimated Effort:** 4-6 hours

### Tasks

| Task | Description |
|------|-------------|
| 3.1 | Add `opencode-client` to `requirements.txt` |
| 3.2 | Create `OpenCodeService` class wrapping the client |
| 3.3 | Replace `handle_message_streaming()` with async API calls |
| 3.4 | Replace `handle_message_simple()` with sync API calls |
| 3.5 | Migrate session management to client's built-in tracking |
| 3.6 | Implement SSE streaming for real-time updates |

### Architecture

```
┌─────────────┐     ┌──────────────────┐     ┌─────────────┐
│  Telegram   │────▶│  opencode serve  │────▶│   OpenCode  │
│    Bot      │◀────│  :8080 (daemon)  │◀────│   AI/LLM    │
└─────────────┘     └──────────────────┘     └─────────────┘
       │                    ▲
       │                    │
       └── opencode-client ─┘
           (Python async)
```

### Code Example

```python
from opencode_client import OpenCodeClient

class OpenCodeService:
    def __init__(self):
        self.client = OpenCodeClient(
            base_url="http://localhost:8080",
            model_provider="anthropic",
            model="claude-sonnet-4",
        )
    
    async def send_message(self, text: str, session_id: str = None):
        if not session_id:
            session = await self.client.create_current_session()
            session_id = session.id
        
        response = await self.client.send_message(text, session_id=session_id)
        return response.to_string(), session_id
```

---

## Phase 4: Oh-My-OpenCode Integration (Optional)

**Goal:** Leverage multi-agent orchestration for enhanced capabilities.

**Estimated Effort:** 2-4 hours

### Tasks

| Task | Description |
|------|-------------|
| 4.1 | Install and configure oh-my-opencode plugin |
| 4.2 | Add `/agent` command to select agents (Sisyphus, Oracle, etc.) |
| 4.3 | Configure specialized agents for different task types |
| 4.4 | Enable background agent execution |

### Available Agents

| Agent | Model | Use Case |
|-------|-------|----------|
| Sisyphus | Claude Opus 4.5 | Primary orchestrator |
| Oracle | GPT 5.2 | Strategy, debugging |
| Librarian | Claude Sonnet 4.5 | Docs, research |
| Frontend Engineer | Gemini 3 Pro | UI generation |

---

## Testing Checklist

### Phase 1 Verification

- [ ] `/start` shows welcome message
- [ ] `/help` displays all commands
- [ ] `/new` creates new session
- [ ] `/new ~/path` creates session in specified directory
- [ ] `/session` lists sessions
- [ ] `/session <id>` switches to session
- [ ] `/auto` shows current level
- [ ] `/auto high` sets autonomy (via config)
- [ ] `/cwd` shows working directory
- [ ] `/stream` toggles streaming
- [ ] `/status` shows OpenCode version
- [ ] `/git status` runs git command
- [ ] `/stop` terminates running process
- [ ] Reply-to-message continues session
- [ ] Live streaming updates work
- [ ] Session persistence across bot restarts

---

## Rollback Plan

If issues occur during migration:

1. Keep original `bot.py` as `bot_droid.py`
2. Environment variable `USE_DROID=true` to switch back
3. Both CLIs can coexist (`droid` and `opencode`)

---

## Timeline

| Phase | Duration | Dependencies |
|-------|----------|--------------|
| Phase 1 | Day 1 | OpenCode CLI installed |
| Phase 2 | Day 1-2 | Phase 1 complete |
| Phase 3 | Day 2-3 | Phase 2 complete, opencode-client installed |
| Phase 4 | Day 3+ | Phase 3 complete, oh-my-opencode configured |

---

## Notes

- OpenCode requires >= 1.0.150
- JSON streaming format may differ from Droid - verify event types
- Session IDs format may differ - test continuation
- Permission system is config-based, not CLI-flag based
