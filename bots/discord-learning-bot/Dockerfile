FROM python:3.12-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Create persistent data directory
RUN mkdir -p /app/data_persist /app/output

# Run the bot
CMD ["python", "run.py"]
