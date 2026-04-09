FROM python:3.11-slim

WORKDIR /app

# System dependencies (needed for some packages like psycopg, httpx, etc.)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Upgrade pip
RUN pip install --no-cache-dir --upgrade pip

# Copy requirements first (better caching)
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy project
COPY . .

# Create safe temp directory
RUN mkdir -p /tmp/output

# Expose port (Render expects this)
EXPOSE 10000

# Start app
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port $PORT"]