"""Unit tests for the LG-Agent helper functions and routing logic.

These tests cover the pure-Python helpers (confirmation_check,
get_tool_call_id, routing functions) WITHOUT requiring Ollama or the MCP
server to be running.
"""

import os
import sys
import pytest

# Add the AI Agent directory to the path so we can import LG-Agent
sys.path.insert(0, os.path.dirname(__file__))

# We rename the import because Python can't import a module named with a hyphen.
import importlib
agent = importlib.import_module("LG-Agent")


# ── confirmation_check ──────────────────────────────────────────────────────

class TestConfirmationCheck:
    @pytest.mark.parametrize("word", ["yes", "y", "confirm", "ok", "okay"])
    def test_confirmation_words(self, word):
        assert agent.confirmation_check(word) == "confirm"

    @pytest.mark.parametrize("word", ["no", "n", "deny", "cancel", "stop"])
    def test_denial_words(self, word):
        assert agent.confirmation_check(word) == "deny"

    def test_invalid_input(self):
        assert agent.confirmation_check("maybe") == "invalid"

    def test_empty_string(self):
        assert agent.confirmation_check("") == "invalid"

    def test_case_insensitive_yes(self):
        assert agent.confirmation_check("YES") == "confirm"

    def test_case_insensitive_no(self):
        assert agent.confirmation_check("NO") == "deny"

    def test_mixed_case(self):
        assert agent.confirmation_check("Confirm") == "confirm"

    def test_leading_trailing_whitespace(self):
        assert agent.confirmation_check("  yes  ") == "confirm"
        assert agent.confirmation_check("  no  ") == "deny"

    def test_partial_match_not_accepted(self):
        assert agent.confirmation_check("yesterday") == "invalid"
        assert agent.confirmation_check("nope") == "invalid"

    def test_sentence_not_accepted(self):
        assert agent.confirmation_check("yes please") == "invalid"


# ── get_tool_call_id ────────────────────────────────────────────────────────

class TestGetToolCallId:
    def test_file_tool_groups_by_folder(self):
        tc = {"name": "create_file", "args": {"file_name": "docs/readme.txt"}}
        result = agent.get_tool_call_id(tc)
        assert "create_file" in result
        assert "folder" in result
        assert "docs" in result

    def test_same_folder_same_id(self):
        tc1 = {"name": "create_file", "args": {"file_name": "docs/a.txt"}}
        tc2 = {"name": "create_file", "args": {"file_name": "docs/b.txt"}}
        assert agent.get_tool_call_id(tc1) == agent.get_tool_call_id(tc2)

    def test_different_folders_different_ids(self):
        tc1 = {"name": "create_file", "args": {"file_name": "docs/a.txt"}}
        tc2 = {"name": "create_file", "args": {"file_name": "images/a.txt"}}
        assert agent.get_tool_call_id(tc1) != agent.get_tool_call_id(tc2)

    def test_bare_filename_uses_separator(self):
        tc = {"name": "delete_file", "args": {"file_name": "readme.txt"}}
        result = agent.get_tool_call_id(tc)
        assert "delete_file" in result
        assert "folder" in result

    def test_non_file_tool_hashes_args(self):
        tc = {"name": "get_os_info", "args": {}}
        result = agent.get_tool_call_id(tc)
        assert "get_os_info" in result
        assert "folder" not in result

    def test_missing_args_key(self):
        tc = {"name": "get_os_info"}
        result = agent.get_tool_call_id(tc)
        assert isinstance(result, str)

    def test_none_args(self):
        tc = {"name": "list_files", "args": None}
        result = agent.get_tool_call_id(tc)
        assert isinstance(result, str)


# ── add_tool_confirmation_to_dict ───────────────────────────────────────────

class TestAddToolConfirmation:
    def setup_method(self):
        agent.confirmed_tool_calls.clear()

    def test_adds_new_entry(self):
        agent.add_tool_confirmation_to_dict("id_1", {"file_name": "a.txt"}, "confirm")
        assert "id_1" in agent.confirmed_tool_calls
        assert agent.confirmed_tool_calls["id_1"]["user_confirmation"] == "confirm"

    def test_does_not_overwrite_existing(self):
        agent.add_tool_confirmation_to_dict("id_1", {"file_name": "a.txt"}, "confirm")
        agent.add_tool_confirmation_to_dict("id_1", {"file_name": "b.txt"}, "deny")
        assert agent.confirmed_tool_calls["id_1"]["user_confirmation"] == "confirm"

    def test_multiple_entries(self):
        agent.add_tool_confirmation_to_dict("id_1", {}, "confirm")
        agent.add_tool_confirmation_to_dict("id_2", {}, "deny")
        assert len(agent.confirmed_tool_calls) == 2


# ── routing functions ───────────────────────────────────────────────────────

class TestRouting:
    """Test the pure routing functions that inspect State and return a node name."""

    def test_route_to_tool_when_pending(self):
        state = {"pending_action": [{"tool_name": "create_file"}], "messages": []}
        assert agent.route_to_tool_or_llm_for_processing(state) == "execute_tool"

    def test_route_to_llm_when_no_pending(self):
        state = {"pending_action": [], "messages": []}
        assert agent.route_to_tool_or_llm_for_processing(state) == "tool_calling_llm"

    def test_route_to_llm_when_pending_missing(self):
        state = {"messages": []}
        assert agent.route_to_tool_or_llm_for_processing(state) == "tool_calling_llm"


class TestRouteConfirmationRequired:
    """route_confirmation_required_check returns END when no tool_calls."""

    def _make_msg(self, tool_calls=None):
        class FakeMsg:
            def __init__(self, tc):
                if tc is not None:
                    self.tool_calls = tc
                self.content = ""
        return FakeMsg(tool_calls)

    def test_no_tool_calls_routes_to_end(self):
        from langgraph.graph import END
        state = {"messages": [self._make_msg(None)]}
        assert agent.route_confirmation_required_check(state) == END

    def test_with_tool_calls_routes_to_confirmation(self):
        tc = [{"name": "list_files", "args": {}}]
        state = {"messages": [self._make_msg(tc)]}
        assert agent.route_confirmation_required_check(state) == "confirmation_required"


class TestRouteToConfirmationOrTool:
    def test_confirmed_routes_to_execute(self):
        state = {"pending_action": [{"confirmed": "true"}]}
        assert agent.route_to_confirmation_or_tool(state) == "execute_tool"

    def test_unconfirmed_routes_to_user_confirmation(self):
        state = {"pending_action": [{"confirmed": "false"}]}
        assert agent.route_to_confirmation_or_tool(state) == "user_confirmation"

    def test_empty_pending_routes_to_user_confirmation(self):
        state = {"pending_action": []}
        assert agent.route_to_confirmation_or_tool(state) == "user_confirmation"


class TestRouteAfterExecuteTool:
    def _make_msg(self, tool_calls=None):
        class FakeMsg:
            def __init__(self, tc):
                if tc is not None:
                    self.tool_calls = tc
                self.content = ""
        return FakeMsg(tool_calls)

    def test_tool_calls_routes_to_tools(self):
        tc = [{"name": "create_file", "args": {}}]
        state = {"messages": [self._make_msg(tc)]}
        assert agent.route_after_execute_tool(state) == "tools"

    def test_no_tool_calls_routes_to_end(self):
        from langgraph.graph import END
        state = {"messages": [self._make_msg(None)]}
        assert agent.route_after_execute_tool(state) == END


class TestRouteAfterExecution:
    def test_more_pending_routes_to_confirm_next(self):
        state = {"pending_action": [{"tool_name": "delete_file"}]}
        assert agent.route_after_execution(state) == "confirm_next"

    def test_no_pending_routes_to_llm(self):
        state = {"pending_action": []}
        assert agent.route_after_execution(state) == "tool_calling_llm"


# ── _load_agent_skills ──────────────────────────────────────────────────────

class TestLoadAgentSkills:
    def test_returns_string(self):
        result = agent._load_agent_skills()
        assert isinstance(result, str)

    def test_content_is_nonempty(self):
        result = agent._load_agent_skills()
        assert len(result) > 0

    def test_missing_file_returns_empty(self, monkeypatch, tmp_path):
        monkeypatch.setattr(os.path, "abspath", lambda _: str(tmp_path / "fake.py"))
        result = agent._load_agent_skills()
        assert result == ""
