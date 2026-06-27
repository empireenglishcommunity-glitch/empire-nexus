FROM python:3.12-slim

LABEL maintainer="Empire English Community"
LABEL description="30-Day Challenge Discord Bot"

# Set timezone (configurable at runtime via TZ env var)
ENV TZ=Asia/Dubai
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# Create app directory
WORKDIR /app

# Install dependencies first (layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Ensure fonts directory is included (for Arabic PDF certificates)
COPY fonts/ /app/fonts/

# Create persistent directories
RUN mkdir -p /app/output /app/data_persist

# Volumes for persistent data (SQLite DB + certificates)
VOLUME ["/app/data_persist", "/app/output"]

# Health indicator — verify the database is accessible
HEALTHCHECK --interval=60s --timeout=10s --retries=3 \
  CMD python -c "import sqlite3; sqlite3.connect('/app/data_persist/challenge.db').execute('SELECT 1')" || exit 1

# Run the bot
CMD ["python", "run.py"]
