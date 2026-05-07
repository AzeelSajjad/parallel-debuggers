"""SDK custom tools that expose the negative-memory store to debuggers.

`build_memory_tools(memory, agent_id)` returns (mcp_server_config, tool_names).
The tools close over the SharedMemory and agent_id, so each debugger gets its
own bound set even when many run in the same process.
"""

from __future__ import annotations

from claude_agent_sdk import SdkMcpTool, create_sdk_mcp_server, tool
from claude_agent_sdk.types import McpSdkServerConfig

from memory.store import SharedMemory

SERVER_NAME = "negative_memory"


def build_memory_tools(
    memory: SharedMemory,
    agent_id: str,
) -> tuple[McpSdkServerConfig, list[str], list[SdkMcpTool]]:
    @tool(
        "read_failed_approaches",
        (
            "Return every approach that has already failed or is currently in "
            "flight. You MUST NOT propose any approach equivalent to one of "
            "these. Call this BEFORE proposing your own approach."
        ),
        {},
    )
    async def read_failed_approaches(args):
        attempts = memory.get_failed_approaches()
        if not attempts:
            text = "(no prior failed or in-flight approaches — you're the first debugger)"
        else:
            lines = []
            for a in attempts:
                tag = "IN-FLIGHT" if a.status == "in_progress" else "FAILED"
                detail = f" — outcome: {a.result_detail}" if a.result_detail else ""
                lines.append(
                    f"- [{tag}] approach: {a.approach!r} | hypothesis: {a.hypothesis!r}{detail}"
                )
            text = "Approaches you must NOT repeat:\n" + "\n".join(lines)
        return {"content": [{"type": "text", "text": text}]}

    @tool(
        "propose_approach",
        (
            "Reserve an approach in shared memory before attempting it. Call this "
            "BEFORE editing any code. Returns an attempt_id you'll need for "
            "record_outcome. The 'approach' string should describe the fix in 1-2 "
            "specific sentences (mention file/line and the change)."
        ),
        {"approach": str, "hypothesis": str},
    )
    async def propose_approach(args):
        attempt_id = memory.record_attempt(
            agent_id=agent_id,
            approach=args["approach"],
            hypothesis=args["hypothesis"],
        )
        return {
            "content": [
                {
                    "type": "text",
                    "text": f"Reserved attempt_id={attempt_id}. Now apply the fix.",
                }
            ]
        }

    @tool(
        "record_outcome",
        (
            "After your fix is applied, record whether you believe it will work. "
            "Always call this before stopping, even if you bail without editing."
        ),
        {"attempt_id": str, "success": bool, "detail": str},
    )
    async def record_outcome(args):
        memory.record_result(
            attempt_id=args["attempt_id"],
            success=args["success"],
            detail=args["detail"],
        )
        verdict = "success" if args["success"] else "failure"
        return {
            "content": [
                {
                    "type": "text",
                    "text": f"Recorded {args['attempt_id']} as {verdict}.",
                }
            ]
        }

    sdk_tools = [read_failed_approaches, propose_approach, record_outcome]
    server = create_sdk_mcp_server(
        name=SERVER_NAME,
        version="1.0.0",
        tools=sdk_tools,
    )
    tool_names = [
        f"mcp__{SERVER_NAME}__read_failed_approaches",
        f"mcp__{SERVER_NAME}__propose_approach",
        f"mcp__{SERVER_NAME}__record_outcome",
    ]
    return server, tool_names, sdk_tools
