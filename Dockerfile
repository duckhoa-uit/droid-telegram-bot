FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    unzip \
    git \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install Bun
RUN curl -fsSL https://bun.com/install | bash
ENV BUN_INSTALL="/root/.bun"
ENV PATH="$BUN_INSTALL/bin:$PATH"

# Install OpenCode - download binary directly
RUN curl -fsSL https://opencode.ai/install | bash || true
ENV OPENCODE_INSTALL="/root/.opencode"
ENV PATH="$OPENCODE_INSTALL/bin:$PATH"

# Verify installations
RUN echo "Bun version:" && bun --version || echo "Bun not found"
RUN echo "OpenCode path:" && ls -la /root/.opencode/bin/ 2>/dev/null || echo "OpenCode not in expected path"
RUN echo "Checking opencode:" && which opencode || echo "opencode not in PATH"

# Copy OpenCode config (includes plugin config and auth templates)
COPY config/opencode /root/.config/opencode

# Create necessary directories for OpenCode
RUN mkdir -p /root/.local/share/opencode/storage \
    && mkdir -p /root/.cache/opencode/node_modules

# Pre-install the antigravity plugin during build to speed up startup
RUN cd /root/.cache/opencode && bun add opencode-antigravity-auth@1.2.7 || true

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY bot.py .
COPY start.sh .
RUN chmod +x start.sh

# Create volume mount points
RUN mkdir -p /data/sessions /data/opencode/storage /data/opencode/cache /data/opencode/config

# Environment
ENV OPENCODE_SESSIONS_FILE=/data/sessions/sessions.json
ENV OPENCODE_SERVER_URL=http://127.0.0.1:8080
ENV OPENCODE_PATH=/root/.opencode/bin/opencode
ENV OPENCODE_DEFAULT_CWD=/app

CMD ["./start.sh"]
