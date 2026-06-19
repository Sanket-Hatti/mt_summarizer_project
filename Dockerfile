# Dockerfile for mt_summarizer_project
# Based on python:3.12-slim with system dependencies for Tesseract and Poppler
FROM python:3.12-slim

# Install system dependencies required for OCR and PDF processing
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    tesseract-ocr \
    tesseract-ocr-eng \
    poppler-utils \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Create app directory
WORKDIR /app

# Copy requirements first for caching
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt \
    && python -c "import nltk; nltk.download('punkt'); nltk.download('punkt_tab')"

# Copy application source
COPY . /app

# Ensure runtime directories exist
RUN mkdir -p /app/uploads /app/results

# Environment
ENV PYTHONUNBUFFERED=1
ENV FLASK_ENV=production

# Expose port
EXPOSE 5000

# Use gunicorn to serve the app
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "app:app", "--workers", "2", "--timeout", "120"]
