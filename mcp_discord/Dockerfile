FROM python:3.12-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source
COPY . .

# Expose MCP HTTP port
EXPOSE 8080

# Run MCP server
CMD ["python", "server.py"]
