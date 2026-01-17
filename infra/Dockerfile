# /infrastructure/Dockerfile
FROM python:3.11-slim

WORKDIR /app

# Move up one level to grab requirements
COPY ../requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the app source code
COPY ../app ./app

# Expose port and run from the app package
EXPOSE 8000
CMD ["python", "app/main.py"]