"""Unit tests for MCP server tool functions (server.py).

These tests exercise the raw Python functions behind the @mcp.tool decorators
using a temporary directory so nothing is written outside the test sandbox.
"""

import os
import pytest

# ---------------------------------------------------------------------------
# We need to import the tool functions from server.py, but that module runs
# side-effects at import time (creates dirs, changes cwd).  To keep tests
# isolated we monkeypatch the environment first.
# ---------------------------------------------------------------------------

def _unwrap(tool_or_fn):
    """FastMCP's @mcp.tool wraps functions into FunctionTool objects.
    Return the raw callable so tests can invoke it directly."""
    return getattr(tool_or_fn, "fn", tool_or_fn)


@pytest.fixture(autouse=True)
def _isolated_dirs(tmp_path, monkeypatch):
    """Redirect SOURCE_DIR / OUTPUT_DIR to temp folders before every test."""
    src = tmp_path / "source"
    out = tmp_path / "output"
    src.mkdir()
    out.mkdir()

    monkeypatch.setenv("SOURCE_DIR", str(src))
    monkeypatch.setenv("OUTPUT_DIR", str(out))
    monkeypatch.chdir(src)

    import server
    monkeypatch.setattr(server, "source_dir", str(src))
    monkeypatch.setattr(server, "output_dir", str(out))

    yield {"source": src, "output": out}


# ── get_os_info ─────────────────────────────────────────────────────────────

class TestGetOsInfo:
    def test_returns_dict(self):
        from server import get_os_info
        result = _unwrap(get_os_info)()
        assert isinstance(result, dict)

    def test_keys_present(self):
        from server import get_os_info
        result = _unwrap(get_os_info)()
        assert "os_name" in result
        assert "platform" in result
        assert "cwd" in result

    def test_os_name_matches_runtime(self):
        from server import get_os_info
        assert _unwrap(get_os_info)()["os_name"] == os.name

    def test_platform_matches_runtime(self):
        from server import get_os_info
        assert _unwrap(get_os_info)()["platform"] == os.sys.platform


# ── list_files ──────────────────────────────────────────────────────────────

class TestListFiles:
    def test_empty_directory(self, _isolated_dirs):
        from server import list_files
        assert _unwrap(list_files)(_isolated_dirs["source"].as_posix()) == []

    def test_lists_created_files(self, _isolated_dirs):
        from server import list_files
        src = _isolated_dirs["source"]
        (src / "a.txt").write_text("a")
        (src / "b.txt").write_text("b")
        result = _unwrap(list_files)(str(src))
        assert sorted(result) == ["a.txt", "b.txt"]

    def test_nonexistent_directory_returns_empty(self):
        from server import list_files
        result = _unwrap(list_files)("/this/path/does/not/exist")
        assert result == []

    def test_default_directory_is_source(self, _isolated_dirs):
        from server import list_files
        src = _isolated_dirs["source"]
        (src / "default.txt").write_text("hi")
        result = _unwrap(list_files)(str(src))
        assert "default.txt" in result


# ── create_file ─────────────────────────────────────────────────────────────

class TestCreateFile:
    def test_creates_empty_file(self, _isolated_dirs):
        from server import create_file
        out = _isolated_dirs["output"]
        msg = _unwrap(create_file)("empty.txt", "", str(out))
        assert "created successfully" in msg
        assert (out / "empty.txt").exists()
        assert (out / "empty.txt").read_text() == ""

    def test_creates_file_with_content(self, _isolated_dirs):
        from server import create_file
        out = _isolated_dirs["output"]
        _unwrap(create_file)("hello.txt", "Hello, World!", str(out))
        assert (out / "hello.txt").read_text() == "Hello, World!"

    def test_overwrites_existing_file(self, _isolated_dirs):
        from server import create_file
        out = _isolated_dirs["output"]
        _unwrap(create_file)("dup.txt", "first", str(out))
        _unwrap(create_file)("dup.txt", "second", str(out))
        assert (out / "dup.txt").read_text() == "second"

    def test_returns_error_for_invalid_directory(self):
        from server import create_file
        msg = _unwrap(create_file)("x.txt", "", "/no/such/dir")
        assert "Error" in msg

    def test_file_name_with_subdirectory(self, _isolated_dirs):
        from server import create_file
        out = _isolated_dirs["output"]
        sub = out / "sub"
        sub.mkdir()
        msg = _unwrap(create_file)("nested.txt", "data", str(sub))
        assert "created successfully" in msg
        assert (sub / "nested.txt").read_text() == "data"


# ── delete_file ─────────────────────────────────────────────────────────────

class TestDeleteFile:
    def test_deletes_existing_file(self, _isolated_dirs):
        from server import delete_file
        out = _isolated_dirs["output"]
        (out / "gone.txt").write_text("bye")
        msg = _unwrap(delete_file)("gone.txt", str(out))
        assert "deleted successfully" in msg
        assert not (out / "gone.txt").exists()

    def test_file_not_found(self, _isolated_dirs):
        from server import delete_file
        out = _isolated_dirs["output"]
        msg = _unwrap(delete_file)("nope.txt", str(out))
        assert "not found" in msg

    def test_delete_then_list(self, _isolated_dirs):
        from server import create_file, delete_file, list_files
        out = _isolated_dirs["output"]
        _unwrap(create_file)("temp.txt", "tmp", str(out))
        assert "temp.txt" in _unwrap(list_files)(str(out))
        _unwrap(delete_file)("temp.txt", str(out))
        assert "temp.txt" not in _unwrap(list_files)(str(out))


# ── get_file_content ────────────────────────────────────────────────────────

class TestGetFileContent:
    def test_reads_txt_file(self, _isolated_dirs):
        from server import get_file_content
        src = _isolated_dirs["source"]
        (src / "readme.txt").write_text("hello world")
        assert _unwrap(get_file_content)("readme.txt", str(src)) == "hello world"

    def test_missing_file_returns_empty(self, _isolated_dirs):
        from server import get_file_content
        src = _isolated_dirs["source"]
        assert _unwrap(get_file_content)("ghost.txt", str(src)) == ""

    def test_reads_csv_file(self, _isolated_dirs):
        from server import get_file_content
        src = _isolated_dirs["source"]
        (src / "data.csv").write_text("a,b,c\n1,2,3\n")
        content = _unwrap(get_file_content)("data.csv", str(src))
        assert "a,b,c" in content
        assert "1,2,3" in content


# ── set_working_directory ───────────────────────────────────────────────────

class TestSetWorkingDirectory:
    def test_changes_to_valid_directory(self, _isolated_dirs):
        from server import set_working_directory
        target = _isolated_dirs["output"]
        set_working_directory(str(target))
        assert os.getcwd() == str(target)

    def test_raises_on_nonexistent_directory(self):
        from server import set_working_directory
        with pytest.raises(FileNotFoundError):
            set_working_directory("/no/such/dir")

    def test_returns_cwd_when_already_there(self, _isolated_dirs):
        from server import set_working_directory
        src = _isolated_dirs["source"]
        os.chdir(str(src))
        result = set_working_directory(str(src))
        assert result == str(src)

    def test_none_defaults_to_cwd(self, _isolated_dirs):
        from server import set_working_directory
        cwd = os.getcwd()
        result = set_working_directory(None)
        assert result == cwd
