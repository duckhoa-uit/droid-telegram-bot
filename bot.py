#!/usr/bin/env python3
"""
OpenCode Telegram Bot - A Telegram interface for OpenCode AI Coding Agent

This bot allows you to interact with OpenCode via Telegram messages,
with live streaming of tool calls and session management.

Repository: https://github.com/duckhoa-uit/opencode-telegram-bot
License: MIT
"""
import subprocess
import logging
import os
import json
import select
import uuid
import re
import html
import urllib.request
import urllib.error
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, MessageHandler, CommandHandler, CallbackQueryHandler, filters, ContextTypes
from telegram.constants import ParseMode
from datetime import datetime

# Load environment variables from .env file
load_dotenv()

# Configuration from environment variables
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
ALLOWED_USER_IDS = os.environ.get("TELEGRAM_ALLOWED_USER_IDS", "")  # Comma-separated list
LOG_FILE = os.environ.get("OPENCODE_LOG_FILE", "./bot.log")
SESSIONS_FILE = os.environ.get("OPENCODE_SESSIONS_FILE", "./sessions.json")
OPENCODE_PATH = os.environ.get("OPENCODE_PATH", "opencode")  # Path to opencode CLI
DEFAULT_CWD = os.environ.get("OPENCODE_DEFAULT_CWD", os.path.expanduser("~"))
OPENCODE_SERVER_URL = os.environ.get("OPENCODE_SERVER_URL", "http://127.0.0.1:8080")  # Daemon server URL

# Validate required config
if not BOT_TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN environment variable is required")

# Parse allowed user IDs
def parse_allowed_users():
    if not ALLOWED_USER_IDS:
        return set()
    try:
        return {int(uid.strip()) for uid in ALLOWED_USER_IDS.split(",") if uid.strip()}
    except ValueError as e:
        raise ValueError(f"Invalid TELEGRAM_ALLOWED_USER_IDS format: {e}")

ALLOWED_USERS = parse_allowed_users()

def is_authorized(user_id):
    """Check if a user is authorized to use the bot"""
    if not ALLOWED_USERS:
        # If no users specified, deny all (secure by default)
        return False
    return user_id in ALLOWED_USERS

def is_valid_opencode_session(session_id):
    """Check if a session ID is valid for OpenCode (must start with 'ses_')"""
    if not session_id:
        return False
    return session_id.startswith("ses_")

# Ensure directories exist (only if not using current directory)
if os.path.dirname(LOG_FILE):
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
if os.path.dirname(SESSIONS_FILE):
    os.makedirs(os.path.dirname(SESSIONS_FILE), exist_ok=True)

# State
streaming_mode = True  # Default on
sessions = {}  # message_id -> {session_id, cwd, header_msg_id}
session_headers = {}  # Store header message ids for active sessions
active_session_per_user = {}  # user_id -> {session_id, cwd, last_msg_id} - fallback for non-reply messages
pending_permissions = {}  # request_id -> {user_message, session_id, cwd, user_id, chat_id, original_msg_id}
session_history = []  # List of all sessions with metadata for /session command
session_autonomy = {}  # session_id -> "low"|"medium"|"high"|"unsafe" (default: off)
active_processes = {}  # user_id -> {"process": Process, "status_msg": Message} - for /stop command

# Server daemon state
_server_available = None  # None = unknown, True/False = cached result
_server_check_time = 0  # Last time we checked server availability

# Context to prepend to messages so OpenCode knows about bot features
BOT_CONTEXT = """[Telegram Bot Context: You're running inside a Telegram bot. The user can use /new <path> to change the working directory for their session (e.g., /new ~/projects/myapp). Don't suggest using cd to change directories - instead tell them to use /new <path>.]

"""

def is_server_available(force_check=False):
    """Check if OpenCode server daemon is running and available"""
    global _server_available, _server_check_time
    import time
    
    # Cache result for 30 seconds to avoid hammering the server
    current_time = time.time()
    if not force_check and _server_available is not None and (current_time - _server_check_time) < 30:
        return _server_available
    
    try:
        # Try to connect to the server - OpenCode serves HTML at root, just check connectivity
        req = urllib.request.Request(f"{OPENCODE_SERVER_URL}/", method='HEAD')
        with urllib.request.urlopen(req, timeout=2) as response:
            _server_available = response.status == 200
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError):
        _server_available = False
    
    _server_check_time = current_time
    logger.info(f"OpenCode server available: {_server_available}")
    return _server_available

def get_server_status():
    """Get detailed server status for /server command"""
    try:
        req = urllib.request.Request(f"{OPENCODE_SERVER_URL}/", method='HEAD')
        with urllib.request.urlopen(req, timeout=2) as response:
            if response.status == 200:
                return True, {"status": "running", "url": OPENCODE_SERVER_URL}
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError) as e:
        return False, str(e)
    return False, "Unknown error"

def build_opencode_command(session_id=None, use_server=True):
    """Build OpenCode command with optional --attach flag for server mode"""
    cmd = [OPENCODE_PATH, "run"]
    
    # Add --attach flag if server is available
    if use_server and is_server_available():
        cmd.extend(["--attach", OPENCODE_SERVER_URL])
    
    cmd.extend(["--format", "json"])
    
    if session_id:
        cmd.extend(["--session", session_id])
    
    return cmd

def load_sessions():
    """Load sessions from JSON file"""
    global sessions, active_session_per_user, session_history, session_autonomy
    try:
        if os.path.exists(SESSIONS_FILE):
            with open(SESSIONS_FILE, 'r') as f:
                data = json.load(f)
                sessions = {int(k): v for k, v in data.get("sessions", {}).items()}
                active_session_per_user = {int(k): v for k, v in data.get("active_session_per_user", {}).items()}
                session_history = data.get("session_history", [])
                session_autonomy = data.get("session_autonomy", {})
                logger.info(f"Loaded {len(sessions)} sessions, {len(session_history)} history entries, {len(session_autonomy)} autonomy settings")
    except Exception as e:
        logger.error(f"Failed to load sessions: {e}")

def save_sessions():
    """Save sessions to JSON file"""
    try:
        data = {
            "sessions": {str(k): v for k, v in sessions.items()},
            "active_session_per_user": {str(k): v for k, v in active_session_per_user.items()},
            "session_history": session_history[-100:],  # Keep last 100 sessions
            "session_autonomy": session_autonomy
        }
        with open(SESSIONS_FILE, 'w') as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        logger.error(f"Failed to save sessions: {e}")

def add_to_session_history(session_id, cwd, first_message=None):
    """Add a session to history"""
    if not session_id:
        return
    # Check if already exists
    for entry in session_history:
        if entry.get("session_id") == session_id:
            return
    session_history.append({
        "session_id": session_id,
        "cwd": cwd,
        "started": datetime.now().isoformat(),
        "first_message": (first_message[:50] + "...") if first_message and len(first_message) > 50 else first_message
    })
    save_sessions()

def markdown_to_html(text):
    """Convert markdown to Telegram HTML format"""
    if not text:
        return text
    
    # Extract code blocks first to protect them
    code_blocks = []
    def save_code_block(match):
        code_blocks.append(match.group(0))
        return f"§§CODEBLOCK{len(code_blocks)-1}§§"
    
    # Save fenced code blocks ```...```
    text = re.sub(r'```(\w*)\n(.*?)```', save_code_block, text, flags=re.DOTALL)
    
    # Save inline code `...`
    inline_codes = []
    def save_inline_code(match):
        inline_codes.append(match.group(1))
        return f"§§INLINECODE{len(inline_codes)-1}§§"
    text = re.sub(r'(?<!`)`([^`]+)`(?!`)', save_inline_code, text)
    
    # Escape HTML in the remaining text
    text = html.escape(text)
    
    # Convert markdown formatting to HTML
    text = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', text)
    text = re.sub(r'__(.+?)__', r'<b>\1</b>', text)
    text = re.sub(r'(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)', r'<i>\1</i>', text)
    text = re.sub(r'(?<!_)_(?!_)(.+?)(?<!_)_(?!_)', r'<i>\1</i>', text)
    text = re.sub(r'~~(.+?)~~', r'<s>\1</s>', text)
    text = re.sub(r'^#{1,6}\s+(.+)$', r'<b>\1</b>', text, flags=re.MULTILINE)
    text = re.sub(r'^[\-\*]\s+', '• ', text, flags=re.MULTILINE)
    
    # Restore inline code
    for i, code in enumerate(inline_codes):
        escaped_code = html.escape(code)
        text = text.replace(f"§§INLINECODE{i}§§", f"<code>{escaped_code}</code>")
    
    # Restore code blocks
    for i, block in enumerate(code_blocks):
        match = re.match(r'```(\w*)\n(.*?)```', block, re.DOTALL)
        if match:
            code = match.group(2)
            escaped_code = html.escape(code.strip())
            text = text.replace(f"§§CODEBLOCK{i}§§", f"<pre>{escaped_code}</pre>")
        else:
            text = text.replace(f"§§CODEBLOCK{i}§§", block)
    
    return text

async def send_formatted_message(message, text):
    """Send a message with HTML formatting, falling back to plain text if needed"""
    try:
        html_text = markdown_to_html(text)
        return await message.reply_text(html_text, parse_mode=ParseMode.HTML)
    except Exception as e:
        logger.warning(f"HTML parsing failed, sending plain text: {e}")
        return await message.reply_text(text)

# Logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_user.id):
        await update.message.reply_text("⛔ Unauthorized. Contact the bot administrator.")
        return
    stream_status = "ON" if streaming_mode else "OFF"
    await update.message.reply_text(
        "🤖 OpenCode Telegram Bot ready!\n\n"
        "Commands:\n"
        "/new <path> - Start new session in directory\n"
        "/cwd - Show/change working directory\n"
        f"/stream - Toggle live updates (currently: {stream_status})\n"
        "/session - List/switch sessions\n"
        "/status - Check bot status\n"
        "/help - Show detailed help\n\n"
        "💡 Reply to any message to continue that session"
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_user.id):
        return
    stream_status = "ON" if streaming_mode else "OFF"
    await update.message.reply_text(
        "🤖 <b>OpenCode Telegram Bot Help</b>\n\n"
        "This bot connects to OpenCode AI Coding Agent.\n\n"
        "<b>📝 Usage:</b>\n"
        "• Send any message to interact with OpenCode\n"
        "• Reply to a message to continue that session\n"
        "• Use /new to start fresh in a directory\n\n"
        "<b>⚙️ Commands:</b>\n"
        "/start - Welcome message\n"
        "/help - This help\n"
        "/new [path] - New session (optional directory)\n"
        "/session - List/switch sessions\n"
        "/auto [level] - Set autonomy (off/low/medium/high/unsafe)\n"
        "/cwd - Show current working directory\n"
        f"/stream - Toggle live tool updates ({stream_status})\n"
        "/status - Bot and OpenCode status\n"
        "/server - Check daemon server status\n"
        "/git [cmd] - Quick git commands\n\n"
        "<b>💡 Tips:</b>\n"
        "• Live updates show which tools OpenCode uses\n"
        "• Sessions persist across messages\n"
        "• Use /auto high to enable tool execution\n"
        "• Timeout is 5 minutes per request",
        parse_mode=ParseMode.HTML
    )

def resolve_cwd(path_arg):
    """Resolve a path argument to an absolute path for cwd"""
    if not path_arg:
        return DEFAULT_CWD
    
    # If it starts with /, it's already absolute
    if path_arg.startswith("/"):
        resolved = path_arg
    # If it starts with ~, expand it
    elif path_arg.startswith("~"):
        resolved = os.path.expanduser(path_arg)
    # Otherwise assume it's relative to DEFAULT_CWD
    else:
        resolved = os.path.join(DEFAULT_CWD, path_arg)
    
    # Verify the path exists
    if os.path.isdir(resolved):
        return resolved
    else:
        return None

def get_git_status(cwd):
    """Get git status summary for a directory"""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--git-dir"],
            cwd=cwd, capture_output=True, text=True, timeout=5
        )
        if result.returncode != 0:
            return None, "Not a git repo"
        
        branch_result = subprocess.run(
            ["git", "branch", "--show-current"],
            cwd=cwd, capture_output=True, text=True, timeout=5
        )
        branch = branch_result.stdout.strip() or "detached HEAD"
        
        status_result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=cwd, capture_output=True, text=True, timeout=5
        )
        changes = status_result.stdout.strip().split('\n') if status_result.stdout.strip() else []
        num_changes = len(changes)
        
        if num_changes == 0:
            return "clean", f"on {branch} (clean)"
        else:
            return "dirty", f"on {branch} ({num_changes} uncommitted)"
    except Exception as e:
        return None, f"git error: {e}"

async def new_session(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start a new session - supports /new <path> to set working directory"""
    if not is_authorized(update.effective_user.id):
        return
    
    message_text = update.message.text
    arg = message_text[4:].strip() if len(message_text) > 4 else ""
    
    resolved_cwd = resolve_cwd(arg) if arg else DEFAULT_CWD
    
    if arg and resolved_cwd is None:
        if "/" in arg or "~" in arg:
            await update.message.reply_text(f"❌ Directory not found: {arg}")
            return
        resolved_cwd = DEFAULT_CWD
        prompt = arg
    elif arg and resolved_cwd:
        prompt = None
    else:
        resolved_cwd = DEFAULT_CWD
        prompt = None
    
    user_id = update.effective_user.id
    temp_session_ref = str(uuid.uuid4())[:8]
    
    # Send header with git status
    short_cwd = resolved_cwd.replace(os.path.expanduser("~"), "~")
    git_state, git_info = get_git_status(resolved_cwd)
    if git_state == "clean":
        git_line = f"✓ Git: {git_info}"
    elif git_state == "dirty":
        git_line = f"⚠️ Git: {git_info}"
    else:
        git_line = f"Git: {git_info}"
    
    header_text = f"📂 {short_cwd}\n🆔 Session: {temp_session_ref}\n{git_line}"
    header_msg = await update.message.reply_text(header_text)
    
    if prompt:
        status_text = "Working..." if streaming_mode else "Thinking..."
        status_msg = await update.message.reply_text(status_text)
        
        try:
            if streaming_mode:
                response, session_id = await handle_message_streaming(prompt, None, status_msg, resolved_cwd, user_id=user_id)
            else:
                response, session_id = await handle_message_simple(prompt, None, resolved_cwd)
            
            response = response or "No response from OpenCode"
            
            if len(response) > 4000:
                response = response[:4000] + "\n\n[Response truncated]"
            
            await status_msg.delete()
            reply_msg = await send_formatted_message(update.message, response)
            
            actual_session_id = session_id or temp_session_ref
            session_data = {
                "session_id": actual_session_id,
                "cwd": resolved_cwd,
                "header_msg_id": header_msg.message_id
            }
            sessions[reply_msg.message_id] = session_data
            sessions[header_msg.message_id] = session_data
            
            active_session_per_user[user_id] = {
                "session_id": actual_session_id,
                "cwd": resolved_cwd,
                "last_msg_id": reply_msg.message_id
            }
            
            add_to_session_history(actual_session_id, resolved_cwd, prompt)
            save_sessions()
            
            if session_id:
                short_session = session_id[:8] if len(session_id) > 8 else session_id
                new_header = f"📂 {short_cwd}\n🆔 Session: {short_session}"
                try:
                    await header_msg.edit_text(new_header)
                except:
                    pass
            
            logger.info(f"New session started: {actual_session_id} in {resolved_cwd}")
            
        except subprocess.TimeoutExpired:
            await status_msg.edit_text("Request timed out (5 min limit).")
        except Exception as e:
            await status_msg.edit_text(f"Error: {str(e)}")
            logger.error(f"Error: {e}")
    else:
        session_data = {
            "session_id": None,
            "cwd": resolved_cwd,
            "header_msg_id": header_msg.message_id,
            "awaiting_first_message": True
        }
        sessions[header_msg.message_id] = session_data
        
        instruction_msg = await update.message.reply_text(
            f"🆕 New session started in `{short_cwd}`\n\nReply to continue.",
            parse_mode="Markdown"
        )
        sessions[instruction_msg.message_id] = session_data
        
        active_session_per_user[user_id] = {
            "session_id": None,
            "cwd": resolved_cwd,
            "last_msg_id": instruction_msg.message_id
        }
        save_sessions()

async def cwd_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show or change current working directory"""
    if not is_authorized(update.effective_user.id):
        return
    
    user_id = update.effective_user.id
    
    if user_id in active_session_per_user:
        cwd = active_session_per_user[user_id].get("cwd") or DEFAULT_CWD
    else:
        cwd = DEFAULT_CWD
    
    short_cwd = cwd.replace(os.path.expanduser("~"), "~")
    git_state, git_info = get_git_status(cwd)
    
    await update.message.reply_text(
        f"📂 Current directory: `{short_cwd}`\n"
        f"Git: {git_info}\n\n"
        f"Use /new <path> to change directory",
        parse_mode="Markdown"
    )

async def stream_toggle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global streaming_mode
    if not is_authorized(update.effective_user.id):
        return
    streaming_mode = not streaming_mode
    status = "ON" if streaming_mode else "OFF"
    await update.message.reply_text(f"Live tool updates: {status}")

async def auto_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Set autonomy level for current session: /auto low|medium|high|unsafe"""
    if not is_authorized(update.effective_user.id):
        return
    
    user_id = update.effective_user.id
    args = update.message.text.split()[1:]  # Get args after /auto
    
    # Get current session
    session_id = None
    if user_id in active_session_per_user:
        session_id = active_session_per_user[user_id].get("session_id")
    
    if not args:
        # Show current level
        current = session_autonomy.get(session_id, "off") if session_id else "off"
        await update.message.reply_text(
            f"Current autonomy: `{current}`\n\n"
            f"Usage: `/auto <level>`\n"
            f"Levels: `off` | `low` | `medium` | `high` | `unsafe`\n\n"
            f"• off = read-only (no tool execution)\n"
            f"• low = safe tools only\n"
            f"• medium = most tools allowed\n"
            f"• high = all tools, asks for risky ones\n"
            f"• unsafe = skip all permission checks",
            parse_mode="Markdown"
        )
        return
    
    level = args[0].lower()
    valid_levels = ["off", "low", "medium", "high", "unsafe"]
    
    if level not in valid_levels:
        await update.message.reply_text(f"Invalid level. Use: {', '.join(valid_levels)}")
        return
    
    if not session_id:
        await update.message.reply_text("No active session. Start one with /new first.")
        return
    
    emoji = {"off": "👁", "low": "🔒", "medium": "🔓", "high": "⚡", "unsafe": "⚠️"}
    
    session_autonomy[session_id] = level
    save_sessions()
    await update.message.reply_text(f"{emoji.get(level, '')} Autonomy set to `{level}` for this session", parse_mode="Markdown")

async def stop_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Stop the currently running opencode process for this user"""
    if not is_authorized(update.effective_user.id):
        return
    
    user_id = update.effective_user.id
    
    if user_id not in active_processes:
        await update.message.reply_text("No active process to stop.")
        return
    
    proc_info = active_processes.pop(user_id)
    process = proc_info.get("process")
    status_msg = proc_info.get("status_msg")
    
    if process and process.poll() is None:
        try:
            process.terminate()
            process.wait(timeout=2)
        except:
            process.kill()
        
        if status_msg:
            try:
                await status_msg.edit_text("🛑 Stopped by user")
            except:
                pass
        
        await update.message.reply_text("✓ Process stopped")
        logger.info(f"User {user_id} stopped active process")
    else:
        await update.message.reply_text("Process already finished.")

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_user.id):
        return
    try:
        opencode_result = subprocess.run([OPENCODE_PATH, "--version"], capture_output=True, text=True, timeout=10)
        opencode_version = opencode_result.stdout.strip() or "unknown"
        stream_status = "ON" if streaming_mode else "OFF"
        active_sessions = len(sessions)
        
        # Check server daemon status
        server_available = is_server_available(force_check=True)
        server_status = "🟢 Connected" if server_available else "🔴 Not running"
        
        user_id = update.effective_user.id
        active_user_session = ""
        if user_id in active_session_per_user:
            active = active_session_per_user[user_id]
            sid = active.get("session_id", "")[:8] if active.get("session_id") else "pending"
            cwd = active.get("cwd", "").replace(os.path.expanduser("~"), "~") if active.get("cwd") else "default"
            active_user_session = f"\n\nYour active session: {sid} in {cwd}"
        
        status_msg = (f"✅ Bot Status: Running\n"
                     f"🤖 OpenCode: {opencode_version}\n"
                     f"🖥️ Server: {server_status}\n"
                     f"⚡ Live updates: {stream_status}\n"
                     f"📊 Active sessions: {active_sessions}{active_user_session}")
        await update.message.reply_text(status_msg)
    except Exception as e:
        await update.message.reply_text(f"Error: {e}")

async def server_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Check OpenCode server daemon status"""
    if not is_authorized(update.effective_user.id):
        return
    
    available, data = get_server_status()
    
    if available:
        if isinstance(data, dict):
            info_lines = ["🟢 <b>OpenCode Server Running</b>\n"]
            info_lines.append(f"URL: <code>{OPENCODE_SERVER_URL}</code>")
            if "version" in data:
                info_lines.append(f"Version: {data['version']}")
            if "uptime" in data:
                info_lines.append(f"Uptime: {data['uptime']}")
            await update.message.reply_text("\n".join(info_lines), parse_mode=ParseMode.HTML)
        else:
            await update.message.reply_text(
                f"🟢 <b>OpenCode Server Running</b>\n"
                f"URL: <code>{OPENCODE_SERVER_URL}</code>",
                parse_mode=ParseMode.HTML
            )
    else:
        await update.message.reply_text(
            f"🔴 <b>OpenCode Server Not Available</b>\n\n"
            f"URL: <code>{OPENCODE_SERVER_URL}</code>\n"
            f"Error: {data}\n\n"
            f"<i>The bot will use direct CLI mode (slower cold starts).\n"
            f"To enable daemon mode, start the server with:</i>\n"
            f"<code>opencode serve --port 8080</code>",
            parse_mode=ParseMode.HTML
        )

async def git_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Execute git commands"""
    if not is_authorized(update.effective_user.id):
        return
    
    user_id = update.effective_user.id
    
    if user_id in active_session_per_user:
        cwd = active_session_per_user[user_id].get("cwd") or DEFAULT_CWD
    else:
        cwd = DEFAULT_CWD
    
    text = update.message.text
    git_args = text[4:].strip() if len(text) > 4 else ""
    
    if not git_args:
        git_state, git_info = get_git_status(cwd)
        short_cwd = cwd.replace(os.path.expanduser("~"), "~")
        await update.message.reply_text(
            f"📂 {short_cwd}\nGit: {git_info}\n\n"
            "Usage: /git <command>\n"
            "Examples: /git status, /git pull, /git log --oneline -5"
        )
        return
    
    short_cwd = cwd.replace(os.path.expanduser("~"), "~")
    status_msg = await update.message.reply_text(f"Running git {git_args.split()[0]}...")
    
    try:
        result = subprocess.run(
            f"git {git_args}",
            shell=True,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=30
        )
        output = result.stdout.strip() or result.stderr.strip() or "(no output)"
        if len(output) > 3500:
            output = output[:3500] + "\n\n[truncated]"
        
        await status_msg.edit_text(f"📂 {short_cwd}\n```\n$ git {git_args}\n{output}\n```", parse_mode="Markdown")
    except subprocess.TimeoutExpired:
        await status_msg.edit_text("Command timed out")
    except Exception as e:
        await status_msg.edit_text(f"Error: {e}")

async def session_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """List sessions or switch to a specific session"""
    if not is_authorized(update.effective_user.id):
        return
    
    user_id = update.effective_user.id
    args = update.message.text.split()[1:] if len(update.message.text.split()) > 1 else []
    
    if args:
        target = args[0]
        found = None
        for entry in session_history:
            if entry["session_id"].startswith(target):
                found = entry
                break
        
        if found:
            active_session_per_user[user_id] = {
                "session_id": found["session_id"],
                "cwd": found["cwd"],
                "last_msg_id": None
            }
            save_sessions()
            short_cwd = found["cwd"].replace(os.path.expanduser("~"), "~")
            await update.message.reply_text(
                f"✓ Switched to session `{found['session_id'][:8]}`\n"
                f"📂 {short_cwd}",
                parse_mode="Markdown"
            )
        else:
            await update.message.reply_text(f"Session not found: {target}")
    else:
        if not session_history:
            await update.message.reply_text("No sessions yet. Use /new to start one.")
            return
        
        lines = ["<b>Recent Sessions</b>\n"]
        for entry in reversed(session_history[-10:]):
            sid = entry["session_id"][:8]
            cwd = entry["cwd"].replace(os.path.expanduser("~"), "~")
            msg = entry.get("first_message", "")[:30] or "N/A"
            
            current = ""
            if user_id in active_session_per_user:
                if active_session_per_user[user_id].get("session_id") == entry["session_id"]:
                    current = " ✓"
            
            lines.append(f"<code>{sid}</code> {cwd}{current}\n  <i>{msg}</i>\n")
        
        lines.append("\nUse <code>/session [id]</code> to switch")
        await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML)

async def handle_permission_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle Once/Always/Deny button presses for permission requests"""
    query = update.callback_query
    await query.answer()
    
    if not is_authorized(query.from_user.id):
        return
    
    data = query.data
    if not data.startswith("perm_"):
        return
    
    parts = data.split("_")
    action = parts[1]  # once, always, or deny
    request_id = parts[2]
    
    if request_id not in pending_permissions:
        await query.edit_message_text("Permission request expired.")
        return
    
    req = pending_permissions.pop(request_id)
    
    if action == "deny":
        await query.edit_message_text("❌ Action denied.")
        return
    
    # If "always", set this session to unsafe mode
    if action == "always" and req["session_id"]:
        session_autonomy[req["session_id"]] = "unsafe"
        save_sessions()
        await query.edit_message_text("✓ Session set to unsafe mode. Re-running...")
    else:
        await query.edit_message_text("✓ Allowed once. Re-running...")
    
    status_msg = await context.bot.send_message(
        chat_id=req["chat_id"],
        text="Working... (with elevated permissions)"
    )
    
    try:
        response, new_session_id = await handle_message_streaming_unsafe(
            req["user_message"], 
            req["session_id"], 
            status_msg, 
            req["cwd"],
            user_id=req["user_id"]
        )
        
        response = response or "No response from OpenCode"
        if len(response) > 4000:
            response = response[:4000] + "\n\n[Response truncated]"
        
        await status_msg.delete()
        reply_msg = await context.bot.send_message(
            chat_id=req["chat_id"],
            text=markdown_to_html(response),
            parse_mode=ParseMode.HTML
        )
        
        actual_session_id = new_session_id or req["session_id"]
        sessions[reply_msg.message_id] = {
            "session_id": actual_session_id,
            "cwd": req["cwd"],
            "header_msg_id": None
        }
        active_session_per_user[req["user_id"]] = {
            "session_id": actual_session_id,
            "cwd": req["cwd"],
            "last_msg_id": reply_msg.message_id
        }
        
        # Propagate "always" to new session_id if it changed
        if action == "always" and actual_session_id and actual_session_id != req["session_id"]:
            session_autonomy[actual_session_id] = "unsafe"
        
        save_sessions()
        
    except Exception as e:
        await status_msg.edit_text(f"Error: {str(e)}")

async def handle_message_streaming_unsafe(user_message, session_id, status_msg, cwd=None, user_id=None):
    """Handle message with elevated permissions (unsafe mode)"""
    
    env = os.environ.copy()
    working_dir = cwd or DEFAULT_CWD
    
    # Build OpenCode command with optional server attachment
    # For unsafe mode, we rely on the opencode.json permissions config
    cmd = build_opencode_command(session_id, use_server=True)
    
    # Add bot context on first message of session so OpenCode knows about /new command
    message_with_context = BOT_CONTEXT + user_message if not session_id else user_message
    cmd.append(message_with_context)
    
    using_server = "--attach" in cmd
    logger.info(f"Running opencode (elevated) in cwd: {working_dir} (server: {using_server})")
    
    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env,
        cwd=working_dir,
        bufsize=1
    )
    
    # Track process for /stop command
    if user_id:
        active_processes[user_id] = {"process": process, "status_msg": status_msg}
    
    final_response = ""
    new_session_id = None
    tool_updates = []
    last_update = ""
    
    while True:
        line = process.stdout.readline()
        if not line:
            if process.poll() is not None:
                break
            continue
        
        line = line.strip()
        if not line:
            continue
        
        try:
            data = json.loads(line)
            event_type = data.get("type", "")
            
            # Extract session ID from any event
            if not new_session_id and "sessionID" in data:
                new_session_id = data.get("sessionID")
            
            if event_type == "tool_use":
                part = data.get("part", {})
                tool_display = format_opencode_tool_call(part)
                tool_updates.append(tool_display)
                display_tools = tool_updates[-5:]
                new_status = "Working... (elevated)\n\n" + "\n".join(display_tools)
                if new_status != last_update:
                    try:
                        await status_msg.edit_text(new_status)
                        last_update = new_status
                    except:
                        pass
            elif event_type == "text":
                part = data.get("part", {})
                text = part.get("text", "")
                if text:
                    final_response += text
            elif event_type == "error":
                final_response = f"Error: {data.get('message', '') or data.get('error', 'Unknown error')}"
        except json.JSONDecodeError:
            extracted = extract_final_text(line)
            if extracted:
                final_response = extracted
            if not new_session_id:
                new_session_id = extract_session_id(line)
    
    stderr = process.stderr.read()
    if stderr and not final_response:
        final_response = stderr.strip()
    
    process.wait()
    
    # Clean up process tracking
    if user_id and user_id in active_processes:
        del active_processes[user_id]
    
    return final_response.strip(), new_session_id

def format_tool_call(data):
    """Format a tool call with relevant details for display (legacy format)"""
    tool_name = data.get("toolName", "") or data.get("name", "unknown")
    params = data.get("input", {}) or data.get("parameters", {}) or data.get("args", {})
    if isinstance(params, str):
        try:
            params = json.loads(params)
        except:
            params = {}
    
    detail = ""
    if tool_name in ["Read", "Edit", "MultiEdit", "Create"]:
        file_path = params.get("file_path", "") or params.get("path", "")
        if file_path:
            if len(file_path) > 50:
                detail = "..." + file_path[-47:]
            else:
                detail = file_path
    elif tool_name == "Grep":
        pattern = params.get("pattern", "")
        if pattern:
            short_pattern = pattern[:20] + "..." if len(pattern) > 20 else pattern
            detail = f"'{short_pattern}'"
    elif tool_name == "Glob":
        patterns = params.get("patterns", [])
        if patterns and isinstance(patterns, list):
            detail = ", ".join(patterns[:2])
    elif tool_name == "LS":
        dir_path = params.get("directory_path", "") or params.get("path", "")
        if dir_path:
            detail = dir_path.split("/")[-1] if "/" in dir_path else dir_path
    elif tool_name == "Execute":
        cmd = params.get("command", "")
        if cmd:
            detail = cmd[:40] + "..." if len(cmd) > 40 else cmd
    elif tool_name == "WebSearch":
        query = params.get("query", "")
        if query:
            detail = f"'{query[:25]}...'" if len(query) > 25 else f"'{query}'"
    
    if detail:
        return f"→ {tool_name}: {detail}"
    else:
        return f"→ {tool_name}"

def format_opencode_tool_call(part):
    """Format an OpenCode tool_use event for display"""
    tool_name = part.get("tool", "unknown")
    state = part.get("state", {})
    input_data = state.get("input", {})
    status = state.get("status", "")
    title = state.get("title", "")
    
    if isinstance(input_data, str):
        try:
            input_data = json.loads(input_data)
        except:
            input_data = {}
    
    detail = ""
    
    # Use title if available
    if title:
        detail = title[:50] + "..." if len(title) > 50 else title
    # Otherwise extract from input based on tool type
    elif tool_name == "bash":
        cmd = input_data.get("command", "")
        if cmd:
            detail = cmd[:40] + "..." if len(cmd) > 40 else cmd
    elif tool_name in ["read", "write", "edit"]:
        file_path = input_data.get("path", "") or input_data.get("file", "")
        if file_path:
            if len(file_path) > 50:
                detail = "..." + file_path[-47:]
            else:
                detail = file_path
    elif tool_name == "glob":
        pattern = input_data.get("pattern", "")
        if pattern:
            detail = pattern[:40] + "..." if len(pattern) > 40 else pattern
    elif tool_name == "grep":
        pattern = input_data.get("pattern", "")
        if pattern:
            detail = f"'{pattern[:25]}...'" if len(pattern) > 25 else f"'{pattern}'"
    elif tool_name == "web_search":
        query = input_data.get("query", "")
        if query:
            detail = f"'{query[:25]}...'" if len(query) > 25 else f"'{query}'"
    
    # Status indicator
    status_icon = "✓" if status == "completed" else "⏳" if status == "running" else ""
    
    if detail:
        return f"{status_icon} {tool_name}: {detail}".strip()
    else:
        return f"{status_icon} {tool_name}".strip()

def extract_final_text(line):
    """Extract finalText from a completion JSON line"""
    if '"finalText"' not in line:
        return None
    try:
        data = json.loads(line)
        return data.get("finalText", "")
    except json.JSONDecodeError:
        try:
            start = line.find('"finalText":"') + len('"finalText":"')
            if start > len('"finalText":"'):
                rest = line[start:]
                end_patterns = ['","numTurns"', '","durationMs"', '","session_id"']
                end_pos = len(rest)
                for pattern in end_patterns:
                    pos = rest.find(pattern)
                    if pos != -1 and pos < end_pos:
                        end_pos = pos
                text = rest[:end_pos]
                return text.replace('\\n', '\n').replace('\\"', '"').replace('\\\\', '\\')
        except:
            pass
    return None

def extract_session_id(line):
    """Extract session_id from a completion JSON line"""
    try:
        data = json.loads(line)
        return data.get("session_id")
    except json.JSONDecodeError:
        try:
            if '"session_id":"' in line:
                start = line.find('"session_id":"') + len('"session_id":"')
                rest = line[start:]
                end = rest.find('"')
                if end != -1:
                    return rest[:end]
        except:
            pass
    return None

async def handle_message_streaming(user_message, session_id, status_msg, cwd=None, autonomy_level="off", user_id=None):
    """Handle message with streaming tool updates. Returns (response, session_id)"""
    
    env = os.environ.copy()
    working_dir = cwd or DEFAULT_CWD
    
    # Build OpenCode command with optional server attachment
    cmd = build_opencode_command(session_id, use_server=True)
    if session_id:
        logger.info(f"Continuing session: {session_id}")
    
    # Add bot context on first message of session so OpenCode knows about /new command
    message_with_context = BOT_CONTEXT + user_message if not session_id else user_message
    cmd.append(message_with_context)
    
    using_server = "--attach" in cmd
    logger.info(f"Running opencode in cwd: {working_dir} (server: {using_server})")
    
    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env,
        cwd=working_dir,
        bufsize=1
    )
    
    # Track process for /stop command
    if user_id:
        active_processes[user_id] = {"process": process, "status_msg": status_msg}
    
    last_update = ""
    final_response = ""
    new_session_id = None
    tool_updates = []
    all_output = []
    
    while True:
        line = process.stdout.readline()
        if not line:
            if process.poll() is not None:
                break
            continue
            
        line = line.strip()
        if not line:
            continue
        
        all_output.append(line)
        logger.info(f"Stream: {line[:150]}...")
        
        try:
            data = json.loads(line)
            event_type = data.get("type", "")
            
            # Extract session ID from any event
            if not new_session_id and "sessionID" in data:
                new_session_id = data.get("sessionID")
            
            if event_type == "tool_use":
                # OpenCode format: part.tool, part.state.input, part.state.output
                part = data.get("part", {})
                tool_display = format_opencode_tool_call(part)
                tool_updates.append(tool_display)
                display_tools = tool_updates[-5:]
                session_indicator = " (continuing)" if session_id else ""
                new_status = f"Working...{session_indicator}\n\n" + "\n".join(display_tools)
                if new_status != last_update:
                    try:
                        await status_msg.edit_text(new_status)
                        last_update = new_status
                    except:
                        pass
            
            elif event_type == "text":
                # OpenCode format: part.text
                part = data.get("part", {})
                text = part.get("text", "")
                if text:
                    final_response += text
            
            elif event_type == "step_finish":
                # Step completed - extract session ID if not already found
                part = data.get("part", {})
                if not new_session_id:
                    new_session_id = data.get("sessionID")
                    
            elif event_type == "error":
                error_msg = data.get("message", "") or data.get("error", "Unknown error")
                final_response = f"Error: {error_msg}"
                
        except json.JSONDecodeError as e:
            # Try legacy extraction for backwards compatibility
            extracted = extract_final_text(line)
            if extracted:
                final_response = extracted
            if not new_session_id:
                new_session_id = extract_session_id(line)
    
    remaining_out = process.stdout.read()
    if remaining_out:
        remaining_out = remaining_out.strip()
        all_output.append(remaining_out)
        
        if not final_response:
            for line in remaining_out.split('\n'):
                line = line.strip()
                if line:
                    extracted = extract_final_text(line)
                    if extracted:
                        final_response = extracted
                        break
        
        if not new_session_id:
            for line in remaining_out.split('\n'):
                line = line.strip()
                if line:
                    new_session_id = extract_session_id(line)
                    if new_session_id:
                        break
    
    stderr = process.stderr.read()
    if stderr:
        logger.warning(f"Stderr: {stderr[:500]}")
        if not final_response:
            final_response = stderr.strip()
    
    process.wait()
    
    if not final_response and all_output:
        for line in reversed(all_output):
            extracted = extract_final_text(line)
            if extracted:
                final_response = extracted
                break
    
    # Clean up process tracking
    if user_id and user_id in active_processes:
        del active_processes[user_id]
    
    return final_response.strip(), new_session_id

async def handle_message_simple(user_message, session_id, cwd=None, autonomy_level="off"):
    """Handle message without streaming. Returns (response, session_id)"""
    
    env = os.environ.copy()
    working_dir = cwd or DEFAULT_CWD
    
    # Build OpenCode command with optional server attachment
    cmd = build_opencode_command(session_id, use_server=True)
    
    # Add bot context on first message of session so OpenCode knows about /new command
    message_with_context = BOT_CONTEXT + user_message if not session_id else user_message
    cmd.append(message_with_context)
    
    using_server = "--attach" in cmd
    logger.info(f"Running opencode in cwd: {working_dir} (server: {using_server})")
    
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=300,
        env=env,
        cwd=working_dir
    )
    
    # Parse JSON output to extract text and session ID
    output = result.stdout.strip()
    final_text = ""
    new_session_id = None
    
    for line in output.split('\n'):
        line = line.strip()
        if not line:
            continue
        try:
            data = json.loads(line)
            event_type = data.get("type", "")
            
            if not new_session_id and "sessionID" in data:
                new_session_id = data.get("sessionID")
            
            if event_type == "text":
                part = data.get("part", {})
                text = part.get("text", "")
                if text:
                    final_text += text
        except json.JSONDecodeError:
            continue
    
    return final_text.strip() or result.stderr.strip(), new_session_id

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_authorized(user_id):
        logger.warning(f"Unauthorized access attempt from user {user_id}")
        return
    
    user_message = update.message.text
    logger.info(f"Received message: {user_message[:100]}...")
    
    session_id = None
    session_cwd = DEFAULT_CWD
    session_data = None
    is_continuation = False
    
    if update.message.reply_to_message:
        replied_msg_id = update.message.reply_to_message.message_id
        if replied_msg_id in sessions:
            session_data = sessions[replied_msg_id]
            if isinstance(session_data, dict):
                session_id = session_data.get("session_id")
                session_cwd = session_data.get("cwd") or DEFAULT_CWD
            else:
                session_id = session_data
            # Validate session ID format for OpenCode
            if not is_valid_opencode_session(session_id):
                session_id = None  # Invalid format, start fresh
            else:
                is_continuation = True
        else:
            if user_id in active_session_per_user:
                active = active_session_per_user[user_id]
                session_id = active.get("session_id")
                session_cwd = active.get("cwd") or DEFAULT_CWD
                # Validate session ID format for OpenCode
                if not is_valid_opencode_session(session_id):
                    session_id = None
                else:
                    is_continuation = True
    else:
        if user_id in active_session_per_user:
            active = active_session_per_user[user_id]
            session_id = active.get("session_id")
            session_cwd = active.get("cwd") or DEFAULT_CWD
            # Validate session ID format for OpenCode
            if not is_valid_opencode_session(session_id):
                session_id = None
            else:
                is_continuation = True
    
    short_cwd = session_cwd.replace(os.path.expanduser("~"), "~")
    short_session = session_id[:8] if session_id else "new"
    
    # Get autonomy level for this session (default: off = read-only)
    autonomy_level = session_autonomy.get(session_id, "off") if session_id else "off"
    
    level_emoji = {"off": "👁", "low": "🔒", "medium": "🔓", "high": "⚡", "unsafe": "⚠️"}
    if autonomy_level != "off":
        status_text = f"Working in {short_cwd} {level_emoji.get(autonomy_level, '')}({autonomy_level})"
    else:
        status_text = f"Working in {short_cwd}" if streaming_mode else f"Thinking in {short_cwd}"
    if is_continuation and session_id:
        status_text += f" (session {short_session})"
    status_msg = await update.message.reply_text(status_text)
    
    try:
        if autonomy_level == "unsafe":
            # Session has unsafe mode - skip all permission checks
            response, new_session_id = await handle_message_streaming_unsafe(user_message, session_id, status_msg, session_cwd, user_id=user_id)
        elif streaming_mode:
            response, new_session_id = await handle_message_streaming(user_message, session_id, status_msg, session_cwd, autonomy_level, user_id=user_id)
        else:
            response, new_session_id = await handle_message_simple(user_message, session_id, session_cwd, autonomy_level)
        
        response = response or "No response from OpenCode"
        
        # Check for permission errors
        if "insufficient permission" in response.lower() or "skip-permissions-unsafe" in response.lower():
            await status_msg.delete()
            
            request_id = str(uuid.uuid4())[:8]
            pending_permissions[request_id] = {
                "user_message": user_message,
                "session_id": new_session_id or session_id,
                "cwd": session_cwd,
                "user_id": user_id,
                "chat_id": update.message.chat_id,
                "original_msg_id": update.message.message_id
            }
            
            keyboard = [
                [
                    InlineKeyboardButton("Once", callback_data=f"perm_once_{request_id}"),
                    InlineKeyboardButton("Always", callback_data=f"perm_always_{request_id}"),
                    InlineKeyboardButton("Deny", callback_data=f"perm_deny_{request_id}")
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                "⚠️ OpenCode needs elevated permissions.\n\n"
                "• *Once* - allow this action only\n"
                "• *Always* - set session to unsafe mode\n"
                "• *Deny* - cancel this action",
                reply_markup=reply_markup,
                parse_mode="Markdown"
            )
            return
        
        if len(response) > 4000:
            response = response[:4000] + "\n\n[Response truncated]"
        
        await status_msg.delete()
        reply_msg = await send_formatted_message(update.message, response)
        
        actual_session_id = new_session_id or session_id
        new_session_data = {
            "session_id": actual_session_id,
            "cwd": session_cwd,
            "header_msg_id": session_data.get("header_msg_id") if isinstance(session_data, dict) else None
        }
        sessions[reply_msg.message_id] = new_session_data
        
        active_session_per_user[user_id] = {
            "session_id": actual_session_id,
            "cwd": session_cwd,
            "last_msg_id": reply_msg.message_id
        }
        
        if actual_session_id and not is_continuation:
            add_to_session_history(actual_session_id, session_cwd, user_message)
        
        # Propagate autonomy level to new session_id if it changed (and not default)
        if autonomy_level != "off" and actual_session_id and actual_session_id != session_id:
            session_autonomy[actual_session_id] = autonomy_level
        
        save_sessions()
        logger.info(f"Response sent ({len(response)} chars)")
        
    except subprocess.TimeoutExpired:
        await status_msg.edit_text("Request timed out (5 min limit).")
    except Exception as e:
        await status_msg.edit_text(f"Error: {str(e)}")
        logger.error(f"Error: {e}")

def main():
    load_sessions()
    
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("new", new_session))
    app.add_handler(CommandHandler("cwd", cwd_command))
    app.add_handler(CommandHandler("stream", stream_toggle))
    app.add_handler(CommandHandler("auto", auto_command))
    app.add_handler(CommandHandler("stop", stop_command))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("server", server_command))
    app.add_handler(CommandHandler("session", session_command))
    app.add_handler(CommandHandler("git", git_command))
    app.add_handler(CallbackQueryHandler(handle_permission_callback, pattern="^perm_"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    logger.info("Starting OpenCode Telegram bot...")
    logger.info(f"Allowed users: {ALLOWED_USERS}")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
