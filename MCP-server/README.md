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
pip install pytest
```

## Running the Server

### Start the server with FastMCP
```bash
cd src
fastmcp run server.py --reload --transport http --port 8080
```

**Options explained:**
- `--reload`: Automatically restart the server when changes are detected
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

## Deactivate Virtual Environment
```bash
deactivate
```
