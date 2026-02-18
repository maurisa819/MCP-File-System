# My First MCP Server

A simple Model Context Protocol (MCP) server built with FastMCP that provides utilities for OS information, file management, and text processing.

## Prerequisites

- Python 3.13 or higher
- FastMCP framework (included in the virtual environment)

## Setup

### 1. Navigate to the project directory
```bash
cd /path/to/MCP-server
```

### 2. Create a virtual environment (if not already present)

#### macOS and Linux
```bash
python3 -m venv src/mcp
```

#### Windows
```cmd
python -m venv src/mcp
```

### 3. Activate the virtual environment

#### macOS and Linux
```bash
source src/mcp/bin/activate
```

#### Windows
```cmd
src\mcp\Scripts\activate
```

You should see `(mcp)` appear in your terminal prompt.

### 4. Install dependencies
```bash
pip install --upgrade pip
pip install fastmcp
pip install asyncio
pip install python-docx
pip install python-pptx
pip install openpyxl
```

## Running the Server

### Start the server with FastMCP
```bash
cd src
fastmcp run server.py --transport http --port 8080
```

**Options explained:**
- `--transport http`: Use HTTP as the transport protocol
- `--port 8080`: Run the server on port 8080

The server will start and be available at `http://localhost:8080`.

### Using the Client
To test the server, run the client in another terminal:

Activate the virtual environment
#### macOS and Linux
```bash
cd src && source mcp/bin/activate
```

Run the client
``` bash
python3 client.py
```

#### Windows
```cmd
cd src
mcp\Scripts\activate
python client.py
```

## Available Tools

The server provides the following tools:
- `get_os_info`: Retrieves operating system information
- `list_files`: Lists files in a specified directory
- `create_file`: Creates a new file with specified content
- `delete_file`: Deletes a specified file
- `get_file_content`: Reads and returns the content of a file

## Deactivate Virtual Environment
```bash
deactivate
```

## Docker Deployment

### Build Docker Image
Build the Docker image for the MCP server:
```bash
docker build -t mcp-server:latest .
```

### Run Docker Container
Run the MCP server in a Docker container:
```bash
docker run -p 8080:8080 mcp-server:latest
```

**Port mapping:**
- `-p 8080:8080`: Maps port 8080 on your host to port 8080 in the container

The server will be available at `http://localhost:8080`.

### Run Container with Custom Port
To run the server on a different port:
```bash
docker run -p 9000:8080 mcp-server:latest
```
This maps port 9000 on your host to port 8080 in the container.

### Stop Docker Container
To stop a running container, use:
```bash
docker ps  # Find the container ID
docker stop <container-id>
```

### Remove Docker Image
```bash
docker rmi mcp-server:latest
```

### Using Docker Compose (Recommended)
Docker Compose provides an easier way to manage the container. A `docker-compose.yml` file is included.

**Start the server:**
```bash
docker-compose up -d
```

**View logs (mcsp-server):**
```bash
docker-compose logs -f mcp-server
```

**View logs (ollama):**
```bash
docker-compose logs -f ollama
```

**Stop the server:**
```bash
docker-compose down
```

**Rebuild the image:**
```bash
docker-compose up -d --build
```
