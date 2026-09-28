FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy script
COPY music_organizer.py .

# Set entrypoint
ENTRYPOINT ["python", "music_organizer.py"]
