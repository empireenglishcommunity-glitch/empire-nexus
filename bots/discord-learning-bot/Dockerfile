FROM python:3.12-slim

WORKDIR /app

# ffmpeg: decode browser recordings (webm/ogg) -> 16k mono wav for Azure
# Pronunciation Assessment (Nutq). Small, no-recommends install.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Create persistent data directories
RUN mkdir -p /app/data_persist /app/output /app/backups

# Run the bot
CMD ["python", "run.py"]
