FROM python:3.12-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Create persistent data directories
RUN mkdir -p /app/data_persist /app/output /app/backups

# Run the bot
CMD ["python", "run.py"]
