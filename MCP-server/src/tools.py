import os
import platform
import psutil
import subprocess
import json

def get_os_info() -> str:
    """
    Retrieves information about the operating system.
    Returns:
        str: the host information in JSON string
    """
    info: dict[str, str] = {
        "system": platform.system(),
        "release": platform.release(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "memory_gb": str(round(psutil.virtual_memory().total / (1024**3), 2)),
    }

    cpu_count = psutil.cpu_count(logical=True)
    if cpu_count is None:
        info["cpu_count"] = "-1"
    else:
        info["cpu_count"] = str(cpu_count)
    
    try:
        cpu_model = subprocess.check_output(
            ["sysctl", "-n", "machdep.cpu.brand_string"]
        ).decode().strip()
        info["cpu_model"] = cpu_model
    except Exception:
        info["cpu_model"] = "Unknown"

    return json.dumps(info, indent=4)


def list_files() -> list:
    """Lists files in the current directory."""
    try:
        # Defaulting to the current working directory
        return os.listdir(".")
    except Exception as e:
        return [f"Error listing files: {str(e)}"]


def create_file(file_name: str, content: str = "") -> str:
    """Creates a file with the specified content."""
    try:
        with open(file_name, 'w', encoding='utf-8') as f:
            f.write(content)
        return f"Successfully created file: '{file_name}'"
    except Exception as e:
        return f"Error creating file: {str(e)}"


def delete_file(file_name: str) -> str:
    """Deletes a specified file."""
    try:
        if os.path.exists(file_name):
            os.remove(file_name)
            return f"Successfully deleted file: '{file_name}'"
        else:
            return f"Error: File '{file_name}' not found."
    except Exception as e:
        return f"Error deleting file: {str(e)}"


def get_file_content(file_name: str) -> str:
    """Reads and returns the contents of a file."""
    try:
        if os.path.exists(file_name):
            with open(file_name, 'r', encoding='utf-8') as f:
                return f.read()
        else:
            return f"Error: File '{file_name}' not found."
    except Exception as e:
        return f"Error reading file: {str(e)}"

if __name__ == '__main__':
    print(get_os_info())
