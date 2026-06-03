FROM python:3.12-slim

WORKDIR /app

# Dependencias del sistema (incluye las necesarias para sentence-transformers)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Dependencias Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Código
COPY . .

# Directorio para ChromaDB
RUN mkdir -p /app/data/chroma_db

# Usuario no-root
RUN useradd -m lycan && chown -R lycan:lycan /app/data
USER lycan

CMD ["python", "main.py"]
