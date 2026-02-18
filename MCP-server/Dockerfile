# Use official Python runtime as a parent image
FROM python:3.13-slim

# Set working directory in container
WORKDIR /app

# Copy the requirements file
COPY requirements.txt .

# Install dependencies
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy the server code into the container
COPY src/server.py .

# Expose the port the server runs on
EXPOSE 8080

# Set environment variables
ENV PYTHONUNBUFFERED=1

# Run the MCP server with fastmcp
CMD ["fastmcp", "run", "server.py", "--transport", "http", "--port", "8080", "--host", "0.0.0.0"]
