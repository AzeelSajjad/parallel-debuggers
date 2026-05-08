# brain

Parallel agent coordination via shared **negative memory**. Builders run concurrently; if their output fails the test suite, debuggers swarm in parallel and share a memory of every approach already tried — so the next debugger doesn't waste a turn rediscovering a known dead end.

Built on the [Claude Agent SDK](https://github.com/anthropics/claude-agent-sdk-python).

## The idea

Most parallel-agent setups share *positive* memory: "here's what worked." That's useful but doesn't help the failure case. The pattern here is the inverse:

- Every debugger logs the approach it intends to try **before** it edits any code (`status: in_progress`). This *reserves* the approach.
- After tests run, the orchestrator overwrites the row with the real outcome (`succeeded` or `failed`).
- The next debugger reads the store and is told, in its system prompt: *"these approaches did not work or are currently being tried — propose something materially different."*

Result: N concurrent debuggers explore N different angles instead of converging on the same fix.

## Pipeline

```
task.json
   │
   ▼
   ┌──────────────────────────────────────────┐
   │  Phase 1: builders                       │
   │  ── N builders run in parallel,          │
   │     each in its own workspace fork       │
   │  ── pytest runs on every fork            │
   │  ── if any fork passes → done            │
   └──────────────────────────────────────────┘
                  │ (no fork passed)
                  ▼
   ┌──────────────────────────────────────────┐
   │  Phase 2: debugger rounds                │
   │  ── promote closest-to-passing fork      │
   │     to canonical                         │
   │  ── M debuggers run in parallel against  │
   │     forks of canonical                   │
   │  ── shared SharedMemory; each debugger   │
   │     calls read_failed_approaches first,  │
   │     then propose_approach BEFORE editing │
   │  ── pytest runs on every fork            │
   │  ── if any fork passes → done            │
   │  ── else: pivot canonical to best fork,  │
   │     repeat (up to max_debug_rounds)      │
   └──────────────────────────────────────────┘
```

## Install

Requires Python 3.11+ and the `claude` CLI authenticated (`claude /login`).

```sh
git clone <this-repo> brain
cd brain
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
```

## Quickstart

Run the built-in flatten example end-to-end:

```sh
.venv/bin/python scripts/run_task.py examples/flatten_task.json
```

Force the debug loop with deliberately broken pre-seeded code:

```sh
.venv/bin/python scripts/smoke_force_debug_loop.py
```

Run the unit tests (no API calls):

```sh
.venv/bin/python -m pytest tests/ -v
```

## Write your own task

A task is a JSON file:

```json
{
  "task_id": "my-feature",
  "description": "Write `mymod.py` containing a function `do_thing(x)` that ...",
  "test_files": {
    "test_mymod.py": "from mymod import do_thing\n\ndef test_basic():\n    ...\n"
  }
}
```

The test files are the spec — builders read them and write code to satisfy them. Debuggers, if they engage, fix that code without modifying the tests.

```sh
.venv/bin/python scripts/run_task.py my-task.json
```

Embedding multi-line Python in JSON by hand is unpleasant. The two `scripts/gen_*_task.py` files show the recommended pattern: write the source as a Python triple-string, dump to JSON.

## Use brain on another project

`run_task.py` is project-agnostic. From any directory:

```sh
/path/to/brain/.venv/bin/python /path/to/brain/scripts/run_task.py \
    /tmp/mytask.json \
    --run-dir /tmp/mytask-run \
    --into  /path/to/myproject/src \
    --python /path/to/myproject/.venv/bin/python
```

- `--into TARGET` copies the canonical workspace into TARGET on success. Unrelated files in TARGET are preserved; matching files are overwritten. `__pycache__` and `.pytest_cache` are skipped.
- `--python PATH` is the interpreter pytest runs under — point at the target project's venv when your tests `import django` (etc.).
- `--run-dir DIR` is where the orchestrator stages forks/canonical/memory.
- `--num-builders`, `--num-debuggers`, `--max-debug-rounds` tune parallelism and budget.

## Architecture

| dir | role |
|---|---|
| `memory/store.py` | `SharedMemory` — file-locked JSON, atomic write via tmp+rename |
| `tools/custom_tools.py` | `build_memory_tools(memory, agent_id)` — three SDK MCP tools |
| `agents/builder.py` | `BuilderAgent` — cwd=workspace, no Bash, reads tests as spec |
| `agents/debugger.py` | `DebuggerAgent` — optional `memory=` switches it to memory-aware prompt |
| `runner/tests.py` | `run_tests(workspace, python_executable=...)` — pytest subprocess |
| `orchestrator/swarm.py` | `run_debugger_swarm()` — N debuggers in parallel, one fork each |
| `orchestrator/run.py` | `run_orchestrator()` — phase 1 (builders) → phase 2 (debug loop) |
| `scripts/run_task.py` | JSON-driven CLI |
| `scripts/smoke_*.py` | Component smokes that invoke the real Claude SDK |

## Cost

Real Claude calls are not free. Per smoke:
- `smoke_builder.py` — ~$0.05–$0.10
- `smoke_debugger.py` — ~$0.05–$0.10
- `smoke_swarm.py` (3 debuggers) — ~$0.30–$0.45
- `smoke_force_debug_loop.py` (debug-loop, 2 debuggers) — ~$0.30–$0.40
- Full pipeline on a small task — ~$0.10–$0.20 happy path, up to ~$1 worst case

Unit tests in `tests/` make zero API calls.

## What it's good for

- Single-module Python tasks fully specified by a pytest suite (utility libs, leetcode-shaped problems, small parsers).
- Fixing broken Python modules where the tests are the source of truth.
- Researching parallel-agent coordination patterns — the negative-memory primitive is the interesting part.

## What it isn't

- A general application builder. No multi-language test runners (yet), no real deployment, no environment management, no cross-task project state, no UI.
- An autonomous coder for sprawling codebases. Builders write into a flat workspace; the orchestrator does not understand a project's package structure.
- Production-grade. The dedup is string-level (relies on the model). For research and small-task automation it works well; for production critical paths it would need semantic dedup, hooks to enforce file-modification rules, and richer telemetry.

## Further reading

- `CLAUDE.md` — invariants and gotchas for working in this repo.
- The design doc with the original constraints and design rationale.
