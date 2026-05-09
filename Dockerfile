FROM python:3.9-slim

WORKDIR /app

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --no-cache-dir gunicorn

# Pre-download the sentence-transformers model so it's cached in the image
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"

# Copy server code
COPY server/ ./server/
COPY .env ./

WORKDIR /app/server

# Create media directory
RUN mkdir -p /app/server/media/insurance_docs /app/server/media/user_uploads

# Collect static files
RUN python manage.py collectstatic --noinput 2>/dev/null || true

# Run migrations
RUN python manage.py migrate --noinput

EXPOSE 8000

CMD ["gunicorn", "core.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3", "--timeout", "300"]
