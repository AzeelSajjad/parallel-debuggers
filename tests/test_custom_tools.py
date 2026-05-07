"""Unit tests for the memory-tool factory.

We invoke the tool callables directly (not via the SDK) to verify they
read/write the underlying SharedMemory correctly.
"""

import asyncio
from pathlib import Path

from memory.store import SharedMemory
from tools.custom_tools import SERVER_NAME, build_memory_tools


def _by_name(sdk_tools):
    return {t.name: t for t in sdk_tools}


def test_factory_returns_three_tool_names(tmp_path: Path) -> None:
    mem = SharedMemory(tmp_path / "mem.json", task_id="t1")
    _, names, sdk_tools = build_memory_tools(mem, agent_id="dbg-1")
    assert names == [
        f"mcp__{SERVER_NAME}__read_failed_approaches",
        f"mcp__{SERVER_NAME}__propose_approach",
        f"mcp__{SERVER_NAME}__record_outcome",
    ]
    assert {t.name for t in sdk_tools} == {
        "read_failed_approaches",
        "propose_approach",
        "record_outcome",
    }


def test_read_empty_returns_first_debugger_message(tmp_path: Path) -> None:
    mem = SharedMemory(tmp_path / "mem.json", task_id="t1")
    _, _, sdk_tools = build_memory_tools(mem, agent_id="dbg-1")
    tools = _by_name(sdk_tools)
    out = asyncio.run(tools["read_failed_approaches"].handler({}))
    text = out["content"][0]["text"]
    assert "first debugger" in text


def test_propose_then_read_shows_in_flight(tmp_path: Path) -> None:
    mem = SharedMemory(tmp_path / "mem.json", task_id="t1")
    _, _, sdk_tools = build_memory_tools(mem, agent_id="dbg-1")
    tools = _by_name(sdk_tools)

    out = asyncio.run(
        tools["propose_approach"].handler(
            {"approach": "change + to -", "hypothesis": "operator wrong"}
        )
    )
    msg = out["content"][0]["text"]
    assert "Reserved attempt_id=" in msg
    attempt_id = msg.split("attempt_id=")[1].split(".")[0]

    read_out = asyncio.run(tools["read_failed_approaches"].handler({}))
    text = read_out["content"][0]["text"]
    assert "IN-FLIGHT" in text
    assert "change + to -" in text
    assert attempt_id


def test_record_outcome_flips_to_failed(tmp_path: Path) -> None:
    mem = SharedMemory(tmp_path / "mem.json", task_id="t1")
    _, _, sdk_tools = build_memory_tools(mem, agent_id="dbg-1")
    tools = _by_name(sdk_tools)

    out = asyncio.run(
        tools["propose_approach"].handler(
            {"approach": "approach A", "hypothesis": "h"}
        )
    )
    attempt_id = out["content"][0]["text"].split("attempt_id=")[1].split(".")[0]

    asyncio.run(
        tools["record_outcome"].handler(
            {"attempt_id": attempt_id, "success": False, "detail": "didnt work"}
        )
    )

    attempts = mem.get_all_attempts()
    assert len(attempts) == 1
    assert attempts[0].status == "failed"
    assert attempts[0].result_detail == "didnt work"


def test_record_outcome_success_excludes_from_failed_list(tmp_path: Path) -> None:
    mem = SharedMemory(tmp_path / "mem.json", task_id="t1")
    _, _, sdk_tools = build_memory_tools(mem, agent_id="dbg-1")
    tools = _by_name(sdk_tools)

    out = asyncio.run(
        tools["propose_approach"].handler(
            {"approach": "winning move", "hypothesis": "h"}
        )
    )
    attempt_id = out["content"][0]["text"].split("attempt_id=")[1].split(".")[0]
    asyncio.run(
        tools["record_outcome"].handler(
            {"attempt_id": attempt_id, "success": True, "detail": "fixed"}
        )
    )

    read_out = asyncio.run(tools["read_failed_approaches"].handler({}))
    text = read_out["content"][0]["text"]
    assert "winning move" not in text
    assert "first debugger" in text


def test_two_debuggers_share_memory(tmp_path: Path) -> None:
    """Different agent_ids, same SharedMemory, must see each other's writes."""
    mem = SharedMemory(tmp_path / "mem.json", task_id="t1")
    _, _, tools_a_list = build_memory_tools(mem, agent_id="dbg-A")
    _, _, tools_b_list = build_memory_tools(mem, agent_id="dbg-B")
    tools_a = _by_name(tools_a_list)
    tools_b = _by_name(tools_b_list)

    asyncio.run(
        tools_a["propose_approach"].handler(
            {"approach": "A's idea", "hypothesis": "h"}
        )
    )
    read_out = asyncio.run(tools_b["read_failed_approaches"].handler({}))
    text = read_out["content"][0]["text"]
    assert "A's idea" in text
    assert "IN-FLIGHT" in text
