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

    def test_content_contains_tool_names(self):
        """The agent skills doc should reference the known tool names."""
        result = agent._load_agent_skills()
        for tool_name in ["get_os_info", "list_files", "create_file", "delete_file", "get_file_content"]:
            assert tool_name in result, f"Expected '{tool_name}' to appear in agent_skills.md"

    def test_content_mentions_demand_mapping(self):
        result = agent._load_agent_skills()
        assert "demand" in result.lower() or "mapping" in result.lower()


# ── Additional confirmation_check edge cases ────────────────────────────────

class TestConfirmationCheckExtended:
    """Extra edge cases beyond the basic parametrized tests."""

    def test_numeric_input(self):
        assert agent.confirmation_check("123") == "invalid"

    def test_special_characters(self):
        assert agent.confirmation_check("@#$%") == "invalid"

    def test_newline_input(self):
        assert agent.confirmation_check("\n") == "invalid"

    def test_tab_input(self):
        assert agent.confirmation_check("\t") == "invalid"

    def test_unicode_input(self):
        assert agent.confirmation_check("是") == "invalid"

    def test_confirmation_word_with_punctuation(self):
        """Trailing punctuation should NOT match."""
        assert agent.confirmation_check("yes!") == "invalid"
        assert agent.confirmation_check("no.") == "invalid"

    def test_only_whitespace(self):
        assert agent.confirmation_check("   ") == "invalid"

    def test_all_caps_deny(self):
        assert agent.confirmation_check("CANCEL") == "deny"
        assert agent.confirmation_check("STOP") == "deny"
        assert agent.confirmation_check("DENY") == "deny"

    def test_all_caps_confirm(self):
        assert agent.confirmation_check("OK") == "confirm"
        assert agent.confirmation_check("OKAY") == "confirm"
        assert agent.confirmation_check("CONFIRM") == "confirm"

    def test_mixed_case_deny_words(self):
        assert agent.confirmation_check("Cancel") == "deny"
        assert agent.confirmation_check("Stop") == "deny"

    def test_repeated_word(self):
        assert agent.confirmation_check("yesyes") == "invalid"
        assert agent.confirmation_check("nono") == "invalid"


# ── Additional get_tool_call_id edge cases ──────────────────────────────────

class TestGetToolCallIdExtended:
    """Additional grouping and hashing behaviour."""

    def test_deeply_nested_path(self):
        tc = {"name": "create_file", "args": {"file_name": "a/b/c/d/file.txt"}}
        result = agent.get_tool_call_id(tc)
        assert "create_file" in result
        assert "folder" in result

    def test_deeply_nested_groups_by_parent(self):
        """Two files in the same deep folder should share an id."""
        tc1 = {"name": "create_file", "args": {"file_name": "a/b/c/one.txt"}}
        tc2 = {"name": "create_file", "args": {"file_name": "a/b/c/two.txt"}}
        assert agent.get_tool_call_id(tc1) == agent.get_tool_call_id(tc2)

    def test_different_tools_same_folder_differ(self):
        """Different tool names in the same folder should produce different ids."""
        tc1 = {"name": "create_file", "args": {"file_name": "docs/a.txt"}}
        tc2 = {"name": "delete_file", "args": {"file_name": "docs/a.txt"}}
        assert agent.get_tool_call_id(tc1) != agent.get_tool_call_id(tc2)

    def test_get_file_content_groups_by_folder(self):
        tc = {"name": "get_file_content", "args": {"file_name": "reports/q1.csv"}}
        result = agent.get_tool_call_id(tc)
        assert "get_file_content" in result
        assert "folder" in result

    def test_non_file_tool_with_different_args(self):
        """Non-file tools with differing args should produce different ids."""
        tc1 = {"name": "custom_tool", "args": {"key": "value1"}}
        tc2 = {"name": "custom_tool", "args": {"key": "value2"}}
        assert agent.get_tool_call_id(tc1) != agent.get_tool_call_id(tc2)

    def test_non_file_tool_same_args_same_id(self):
        tc1 = {"name": "custom_tool", "args": {"key": "v"}}
        tc2 = {"name": "custom_tool", "args": {"key": "v"}}
        assert agent.get_tool_call_id(tc1) == agent.get_tool_call_id(tc2)

    def test_empty_string_file_name(self):
        """An empty file_name is still a string so the folder branch runs."""
        tc = {"name": "create_file", "args": {"file_name": ""}}
        result = agent.get_tool_call_id(tc)
        assert "folder" in result

    def test_file_name_with_spaces(self):
        tc = {"name": "create_file", "args": {"file_name": "my folder/my file.txt"}}
        result = agent.get_tool_call_id(tc)
        assert "folder" in result


# ── Additional add_tool_confirmation_to_dict tests ──────────────────────────

class TestAddToolConfirmationExtended:
    def setup_method(self):
        agent.confirmed_tool_calls.clear()

    def test_deny_is_stored(self):
        agent.add_tool_confirmation_to_dict("id_deny", {"file_name": "x.txt"}, "deny")
        assert agent.confirmed_tool_calls["id_deny"]["user_confirmation"] == "deny"

    def test_invalid_is_stored(self):
        agent.add_tool_confirmation_to_dict("id_inv", {}, "invalid")
        assert agent.confirmed_tool_calls["id_inv"]["user_confirmation"] == "invalid"

    def test_stored_args_structure(self):
        args = {"file_name": "report.csv", "content": "data"}
        agent.add_tool_confirmation_to_dict("id_struct", args, "confirm")
        entry = agent.confirmed_tool_calls["id_struct"]
        assert entry["tool_call"]["id"] == "id_struct"
        assert entry["tool_call"]["args"] == args

    def test_clear_and_re_add(self):
        agent.add_tool_confirmation_to_dict("id_a", {}, "confirm")
        agent.confirmed_tool_calls.clear()
        assert len(agent.confirmed_tool_calls) == 0
        agent.add_tool_confirmation_to_dict("id_a", {}, "deny")
        assert agent.confirmed_tool_calls["id_a"]["user_confirmation"] == "deny"

    def test_many_entries(self):
        for i in range(20):
            agent.add_tool_confirmation_to_dict(f"id_{i}", {}, "confirm")
        assert len(agent.confirmed_tool_calls) == 20


# ── tools_condition node ────────────────────────────────────────────────────

class TestToolsCondition:
    """Tests for the tools_condition function that checks confirmation state."""

    def setup_method(self):
        agent.confirmed_tool_calls.clear()

    def _make_msg(self, tool_calls=None, content=""):
        class FakeMsg:
            def __init__(self, tc, c):
                if tc is not None:
                    self.tool_calls = tc
                self.content = c
        return FakeMsg(tool_calls, content)

    def test_no_tool_calls_returns_state(self):
        state = {"messages": [self._make_msg(None)]}
        result = agent.tools_condition(state)
        assert result == state

    def test_unconfirmed_returns_messages(self):
        """When no prior confirmation, just returns messages."""
        tc = [{"name": "list_files", "args": {}}]
        state = {"messages": [self._make_msg(tc)]}
        result = agent.tools_condition(state)
        assert "messages" in result

    def test_previously_confirmed_returns_pending_action(self):
        """When the tool was previously confirmed, pending_action should be set with confirmed=true."""
        tc = [{"name": "create_file", "args": {"file_name": "docs/a.txt"}}]
        tool_id = agent.get_tool_call_id(tc[0])
        agent.add_tool_confirmation_to_dict(tool_id, tc[0].get("args", {}), "confirm")

        state = {"messages": [self._make_msg(tc)]}
        result = agent.tools_condition(state)
        assert "pending_action" in result
        assert result["pending_action"][0]["confirmed"] == "true"


# ── Additional routing edge cases ───────────────────────────────────────────

class TestRoutingExtended:
    def test_route_to_tool_or_llm_with_none_pending(self):
        state = {"pending_action": None, "messages": []}
        assert agent.route_to_tool_or_llm_for_processing(state) == "tool_calling_llm"

    def test_route_to_tool_with_multiple_pending(self):
        state = {
            "pending_action": [
                {"tool_name": "create_file"},
                {"tool_name": "delete_file"},
            ],
            "messages": [],
        }
        assert agent.route_to_tool_or_llm_for_processing(state) == "execute_tool"


class TestRouteConfirmationRequiredExtended:
    def _make_msg(self, tool_calls=None):
        class FakeMsg:
            def __init__(self, tc):
                if tc is not None:
                    self.tool_calls = tc
                self.content = ""
        return FakeMsg(tool_calls)

    def test_empty_tool_calls_list_routes_to_end(self):
        from langgraph.graph import END
        state = {"messages": [self._make_msg([])]}
        # Empty list is falsy, should route to END
        assert agent.route_confirmation_required_check(state) == END

    def test_multiple_tool_calls_routes_to_confirmation(self):
        tc = [
            {"name": "create_file", "args": {"file_name": "a.txt"}},
            {"name": "delete_file", "args": {"file_name": "b.txt"}},
        ]
        state = {"messages": [self._make_msg(tc)]}
        assert agent.route_confirmation_required_check(state) == "confirmation_required"


class TestRouteToConfirmationOrToolExtended:
    def test_multiple_pending_first_confirmed(self):
        state = {"pending_action": [
            {"confirmed": "true"},
            {"confirmed": "false"},
        ]}
        assert agent.route_to_confirmation_or_tool(state) == "execute_tool"

    def test_multiple_pending_first_unconfirmed(self):
        state = {"pending_action": [
            {"confirmed": "false"},
            {"confirmed": "true"},
        ]}
        assert agent.route_to_confirmation_or_tool(state) == "user_confirmation"

    def test_missing_confirmed_key(self):
        state = {"pending_action": [{"tool_name": "list_files"}]}
        assert agent.route_to_confirmation_or_tool(state) == "user_confirmation"


class TestRouteAfterExecuteToolExtended:
    def _make_msg(self, tool_calls=None):
        class FakeMsg:
            def __init__(self, tc):
                if tc is not None:
                    self.tool_calls = tc
                self.content = ""
        return FakeMsg(tool_calls)

    def test_empty_tool_calls_routes_to_end(self):
        from langgraph.graph import END
        state = {"messages": [self._make_msg([])]}
        assert agent.route_after_execute_tool(state) == END

    def test_multiple_messages_uses_last(self):
        """Only the last message matters for routing."""
        tc = [{"name": "create_file", "args": {}}]
        state = {"messages": [self._make_msg(None), self._make_msg(tc)]}
        assert agent.route_after_execute_tool(state) == "tools"


class TestRouteAfterExecutionExtended:
    def test_none_pending_routes_to_llm(self):
        state = {"pending_action": None}
        assert agent.route_after_execution(state) == "tool_calling_llm"

    def test_missing_pending_key_routes_to_llm(self):
        state = {}
        assert agent.route_after_execution(state) == "tool_calling_llm"

    def test_multiple_pending_routes_to_confirm_next(self):
        state = {"pending_action": [
            {"tool_name": "create_file"},
            {"tool_name": "delete_file"},
        ]}
        assert agent.route_after_execution(state) == "confirm_next"
