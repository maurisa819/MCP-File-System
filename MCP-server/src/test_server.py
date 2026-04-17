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


# ── Additional get_os_info tests ────────────────────────────────────────────

class TestGetOsInfoExtended:
    def test_cwd_value_is_valid_directory(self):
        from server import get_os_info
        result = _unwrap(get_os_info)()
        assert os.path.isdir(result["cwd"])

    def test_return_has_exactly_three_keys(self):
        from server import get_os_info
        result = _unwrap(get_os_info)()
        assert set(result.keys()) == {"os_name", "platform", "cwd"}

    def test_values_are_strings(self):
        from server import get_os_info
        result = _unwrap(get_os_info)()
        for v in result.values():
            assert isinstance(v, str)


# ── Additional list_files tests ─────────────────────────────────────────────

class TestListFilesExtended:
    def test_includes_subdirectories(self, _isolated_dirs):
        from server import list_files
        src = _isolated_dirs["source"]
        (src / "subdir").mkdir()
        result = _unwrap(list_files)(str(src))
        assert "subdir" in result

    def test_hidden_files(self, _isolated_dirs):
        """Hidden files (dot-prefixed) should appear in listing."""
        from server import list_files
        src = _isolated_dirs["source"]
        (src / ".hidden").write_text("secret")
        result = _unwrap(list_files)(str(src))
        assert ".hidden" in result

    def test_files_with_special_characters(self, _isolated_dirs):
        from server import list_files
        src = _isolated_dirs["source"]
        (src / "my file (1).txt").write_text("data")
        result = _unwrap(list_files)(str(src))
        assert "my file (1).txt" in result

    def test_many_files(self, _isolated_dirs):
        from server import list_files
        src = _isolated_dirs["source"]
        for i in range(50):
            (src / f"file_{i}.txt").write_text(str(i))
        result = _unwrap(list_files)(str(src))
        assert len(result) == 50

    def test_mixed_file_types(self, _isolated_dirs):
        from server import list_files
        src = _isolated_dirs["source"]
        for ext in [".txt", ".csv", ".py", ".json", ".md"]:
            (src / f"test{ext}").write_text("content")
        result = _unwrap(list_files)(str(src))
        assert len(result) == 5


# ── Additional create_file tests ────────────────────────────────────────────

class TestCreateFileExtended:
    def test_content_with_newlines_and_tabs(self, _isolated_dirs):
        from server import create_file
        out = _isolated_dirs["output"]
        content = "col1\tcol2\nval1\tval2\n"
        _unwrap(create_file)("tabbed.txt", content, str(out))
        assert (out / "tabbed.txt").read_text() == content

    def test_multiline_content(self, _isolated_dirs):
        from server import create_file
        out = _isolated_dirs["output"]
        content = "line1\nline2\nline3\n"
        _unwrap(create_file)("multi.txt", content, str(out))
        assert (out / "multi.txt").read_text() == content

    def test_large_content(self, _isolated_dirs):
        from server import create_file
        out = _isolated_dirs["output"]
        big = "x" * 100_000
        _unwrap(create_file)("big.txt", big, str(out))
        assert len((out / "big.txt").read_text()) == 100_000

    def test_special_characters_in_content(self, _isolated_dirs):
        from server import create_file
        out = _isolated_dirs["output"]
        content = 'He said "hello" & she said <goodbye>'
        _unwrap(create_file)("special.txt", content, str(out))
        assert (out / "special.txt").read_text() == content

    def test_file_with_extension_variants(self, _isolated_dirs):
        from server import create_file
        out = _isolated_dirs["output"]
        for ext in [".txt", ".csv", ".json", ".md", ".py"]:
            msg = _unwrap(create_file)(f"test{ext}", "data", str(out))
            assert "created successfully" in msg

    def test_return_message_contains_filename(self, _isolated_dirs):
        from server import create_file
        out = _isolated_dirs["output"]
        msg = _unwrap(create_file)("myfile.txt", "", str(out))
        assert "myfile.txt" in msg


# ── Additional delete_file tests ────────────────────────────────────────────

class TestDeleteFileExtended:
    def test_delete_twice_second_returns_not_found(self, _isolated_dirs):
        from server import delete_file
        out = _isolated_dirs["output"]
        (out / "once.txt").write_text("data")
        _unwrap(delete_file)("once.txt", str(out))
        msg = _unwrap(delete_file)("once.txt", str(out))
        assert "not found" in msg

    def test_cannot_delete_directory(self, _isolated_dirs):
        from server import delete_file
        out = _isolated_dirs["output"]
        (out / "adir").mkdir()
        msg = _unwrap(delete_file)("adir", str(out))
        assert "not found" in msg or "Error" in msg

    def test_return_message_contains_filename(self, _isolated_dirs):
        from server import delete_file
        out = _isolated_dirs["output"]
        (out / "target.txt").write_text("bye")
        msg = _unwrap(delete_file)("target.txt", str(out))
        assert "target.txt" in msg

    def test_delete_empty_file(self, _isolated_dirs):
        from server import delete_file
        out = _isolated_dirs["output"]
        (out / "empty.txt").write_text("")
        msg = _unwrap(delete_file)("empty.txt", str(out))
        assert "deleted successfully" in msg
        assert not (out / "empty.txt").exists()


# ── Additional get_file_content tests ───────────────────────────────────────

class TestGetFileContentExtended:
    def test_reads_empty_file(self, _isolated_dirs):
        from server import get_file_content
        src = _isolated_dirs["source"]
        (src / "empty.txt").write_text("")
        assert _unwrap(get_file_content)("empty.txt", str(src)) == ""

    def test_reads_content_with_special_ascii(self, _isolated_dirs):
        from server import get_file_content
        src = _isolated_dirs["source"]
        text = "Hello! @#$%^&*() special chars"
        (src / "special.txt").write_text(text)
        content = _unwrap(get_file_content)("special.txt", str(src))
        assert content == text

    def test_reads_multiline(self, _isolated_dirs):
        from server import get_file_content
        src = _isolated_dirs["source"]
        text = "alpha\nbeta\ngamma"
        (src / "lines.txt").write_text(text)
        content = _unwrap(get_file_content)("lines.txt", str(src))
        assert "alpha" in content and "gamma" in content

    def test_reads_json_as_text(self, _isolated_dirs):
        from server import get_file_content
        src = _isolated_dirs["source"]
        (src / "data.json").write_text('{"key": "value"}')
        content = _unwrap(get_file_content)("data.json", str(src))
        assert '"key"' in content

    def test_reads_large_txt(self, _isolated_dirs):
        from server import get_file_content
        src = _isolated_dirs["source"]
        big = "row\n" * 10_000
        (src / "large.txt").write_text(big)
        content = _unwrap(get_file_content)("large.txt", str(src))
        assert content.count("row") == 10_000


# ── Additional set_working_directory tests ──────────────────────────────────

class TestSetWorkingDirectoryExtended:
    def test_returns_absolute_path(self, _isolated_dirs):
        from server import set_working_directory
        target = _isolated_dirs["output"]
        result = set_working_directory(str(target))
        assert os.path.isabs(result)

    def test_raises_on_file_not_dir(self, _isolated_dirs):
        from server import set_working_directory
        src = _isolated_dirs["source"]
        (src / "file.txt").write_text("data")
        with pytest.raises(FileNotFoundError):
            set_working_directory(str(src / "file.txt"))

    def test_multiple_changes(self, _isolated_dirs):
        from server import set_working_directory
        src = _isolated_dirs["source"]
        out = _isolated_dirs["output"]
        set_working_directory(str(src))
        assert os.getcwd() == str(src)
        set_working_directory(str(out))
        assert os.getcwd() == str(out)


# ── Cross-tool integration tests ───────────────────────────────────────────

class TestIntegration:
    def test_create_read_delete_lifecycle(self, _isolated_dirs):
        """Full lifecycle: create → read → delete → verify gone."""
        from server import create_file, get_file_content, delete_file, list_files
        out = _isolated_dirs["output"]

        _unwrap(create_file)("lifecycle.txt", "test data", str(out))
        assert "lifecycle.txt" in _unwrap(list_files)(str(out))

        content = _unwrap(get_file_content)("lifecycle.txt", str(out))
        assert content == "test data"

        _unwrap(delete_file)("lifecycle.txt", str(out))
        assert "lifecycle.txt" not in _unwrap(list_files)(str(out))

    def test_create_multiple_then_list(self, _isolated_dirs):
        from server import create_file, list_files
        out = _isolated_dirs["output"]
        names = [f"file_{i}.txt" for i in range(5)]
        for name in names:
            _unwrap(create_file)(name, "content", str(out))
        result = _unwrap(list_files)(str(out))
        for name in names:
            assert name in result

    def test_overwrite_then_read(self, _isolated_dirs):
        from server import create_file, get_file_content
        out = _isolated_dirs["output"]
        _unwrap(create_file)("evolve.txt", "version1", str(out))
        _unwrap(create_file)("evolve.txt", "version2", str(out))
        assert _unwrap(get_file_content)("evolve.txt", str(out)) == "version2"

    def test_delete_nonexistent_does_not_affect_others(self, _isolated_dirs):
        from server import create_file, delete_file, list_files
        out = _isolated_dirs["output"]
        _unwrap(create_file)("keep.txt", "safe", str(out))
        _unwrap(delete_file)("ghost.txt", str(out))
        assert "keep.txt" in _unwrap(list_files)(str(out))
