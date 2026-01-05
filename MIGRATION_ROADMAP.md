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

## Phase 2: Server Daemon Mode ✅ COMPLETED

**Goal:** Run `opencode serve` as daemon for faster response times (no cold boot).

**Estimated Effort:** 1-2 hours

### Tasks

| Task | Description | Status |
|------|-------------|--------|
| 2.1 | Create systemd service for `opencode serve --port 8080` | ✅ Done |
| 2.2 | Update CLI calls to use `--attach http://localhost:8080` | ✅ Done |
| 2.3 | Add health check for server availability | ✅ Done |
| 2.4 | Implement fallback to direct CLI if server unavailable | ✅ Done |

### Implementation Details

- Added `opencode-serve.service` systemd unit file
- New `OPENCODE_SERVER_URL` environment variable (default: `http://127.0.0.1:8080`)
- `is_server_available()` function with 30-second caching
- `build_opencode_command()` helper adds `--attach` flag when server is available
- New `/server` command to check daemon status
- `/status` now shows server connection status

### Benefits
- ~5-10x faster response time (no process startup)
- Shared session state across requests
- Better resource utilization

---

## Phase 3: HTTP API Migration ✅ COMPLETED

**Goal:** Replace subprocess calls with direct HTTP API calls to OpenCode server.

**Estimated Effort:** 4-6 hours

### Tasks

| Task | Description | Status |
|------|-------------|--------|
| 3.1 | Add `httpx` to `requirements.txt` | ✅ Done |
| 3.2 | Create `OpenCodeAPIClient` class with async HTTP methods | ✅ Done |
| 3.3 | Update `handle_message_streaming()` to use HTTP API first, fallback to CLI | ✅ Done |
| 3.4 | Update `handle_message_simple()` to use HTTP API first, fallback to CLI | ✅ Done |
| 3.5 | Update `handle_message_streaming_unsafe()` to use HTTP API | ✅ Done |
| 3.6 | Add `OPENCODE_MODEL_PROVIDER` and `OPENCODE_MODEL` env vars | ✅ Done |

### Implementation Details

- Added `OpenCodeAPIClient` class in bot.py with async methods:
  - `create_session()` - POST /session
  - `list_sessions()` - GET /session
  - `abort_session()` - POST /session/{id}/abort
  - `send_message()` - POST /session/{id}/message
  - `send_message_streaming()` - POST /session/{id}/message with callbacks
- Added `handle_message_via_api()` and `handle_message_via_api_unsafe()` functions
- All message handlers now try HTTP API first, then fallback to CLI if:
  - Server is unavailable
  - API returns an error
  - API call throws an exception
- Session creation is handled automatically when no session_id is provided
- Tool call updates are extracted from API response parts

### Benefits
- Fixes the `--format json` + `--attach` issue (no more CLI parsing)
- Direct HTTP communication is more reliable
- Better error handling with proper HTTP status codes
- Automatic fallback to CLI ensures backwards compatibility

### Architecture

```
┌─────────────┐     ┌──────────────────┐     ┌─────────────┐
│  Telegram   │────▶│  opencode serve  │────▶│   OpenCode  │
│    Bot      │◀────│  :8080 (daemon)  │◀────│   AI/LLM    │
└─────────────┘     └──────────────────┘     └─────────────┘
       │                    ▲
       │                    │
       └── httpx (async) ───┘
            HTTP API
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
