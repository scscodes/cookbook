# asdk Replication Specification

A complete build spec for reproducing the asdk personal workspace SDK from scratch. This document contains enough architectural detail, interface contracts, and design rationale for a capable agent to implement the system without seeing the original source.

**What this is**: A Python CLI (`sdk`) that provides domain-scoped tooling, an event-sourced memory system, system setup/provisioning, and a context delivery pipeline for AI agent sessions.

**What this is NOT**: A framework, a library for others, or a multi-user system. This is personal tooling for a solo developer across multiple machines and projects.

---

## 1. Project Identity

- **Name**: sdk-core (package), `sdk` (CLI command)
- **Language**: Python 3.10+, strict typing (pyright strict mode)
- **Dependencies**: pydantic >=2.0, pyyaml >=6.0
- **Dev deps**: pytest, pytest-cov, pyright, ruff
- **Standards**: Ruff linting (E/F/I/N/W/UP, line-length 100), pyright strict, pytest

---

## 2. Architecture Overview

```
sdk-root/
├── core/                  # Infrastructure: CLI, command primitives, registry, utils
│   ├── cli.py             # Entry point: main()
│   ├── command.py         # CommandGroup, LeafCommand, Registry, CommandResult
│   ├── registry.py        # Manifest: imports domain handlers, mounts them
│   ├── models.py          # Pydantic models: SdkPaths, SetupSpec, etc.
│   ├── constants.py       # Named constants (no magic strings/numbers)
│   ├── __init__.py
│   ├── __main__.py        # Enables `python -m core`
│   └── utils/
│       ├── config.py      # resolve_paths(): builds SdkPaths from root
│       ├── log.py         # log_event(): NDJSON append to logs/events.jsonl
│       ├── provision.py   # Symlinks, shell rc merging (setup + install)
│       ├── atomic_io.py   # replace_file_text_atomically(): temp + os.replace
│       └── shell_rc.py    # Marker-delimited block stripping for .bashrc
│
├── domains/               # Command implementations (one dir per domain)
│   ├── memory/            # Agent memory: write, list, query, compile, gc
│   ├── setup/             # System provisioning: symlinks + shell rc
│   ├── install/           # Per-domain software installers
│   ├── system/            # System reports (hardware, network, etc.)
│   └── context-library/   # Static config: rules, skills, stances (not a command domain)
│
├── tests/                 # pytest suite mirroring core/ and domains/
├── docs/                  # ADRs, reference docs
├── logs/                  # Gitignored. NDJSON event log.
├── out/                   # Host-keyed output artifacts
│   └── <hostname>/        # CLAUDE.md, context-index.md, reports
├── sdk                    # Thin bash launcher (sets SDK_ROOT, execs Python)
└── pyproject.toml
```

### Design Principles

1. **Domains own commands, core owns infrastructure.** No domain-specific logic in core/. No cross-domain imports.
2. **Python-first, shell only for thin launchers.** The `sdk` file is the only shell script in the critical path.
3. **Event-sourced memory.** Append-only NDJSON events, compiled to markdown. Git history is the audit trail.
4. **Context delivery as a build system.** Raw inputs (memory events, rules, skills) compile into targeted artifacts consumed by AI agent sessions.

---

## 3. CLI Entry Points

Three entry points, all reaching the same `core.cli:main()`:

1. **`~/.local/bin/sdk`** — symlink to `./sdk` (created by `sdk setup`)
2. **`./sdk`** — bash wrapper: sets `SDK_ROOT`, execs `.venv/bin/sdk` or falls back to `python3 -m core`
3. **`.venv/bin/sdk`** — setuptools console_script from `[project.scripts]` in pyproject.toml

### Launcher script (`sdk`)

```bash
#!/usr/bin/env bash
set -euo pipefail
REAL_SCRIPT="$(readlink -f "${BASH_SOURCE[0]}")"
SCRIPT_DIR="$(cd "$(dirname "$REAL_SCRIPT")" && pwd)"
export SDK_ROOT="${SDK_ROOT:-$SCRIPT_DIR}"
if [[ -x "$SCRIPT_DIR/.venv/bin/sdk" ]]; then
  exec "$SCRIPT_DIR/.venv/bin/sdk" "$@"
else
  PYTHONPATH="$SCRIPT_DIR${PYTHONPATH:+:$PYTHONPATH}" exec python3 -m core "$@"
fi
```

### CLI dispatch (`core/cli.py`)

```
sdk <command> [args]
sdk help [command [subcommand]]
sdk -h | --help
```

`main()` parses args, resolves `SdkPaths` from `SDK_ROOT` env var (or cwd), dispatches via the registry. Built-in `help` command lives in cli.py, not as a domain.

---

## 4. Command Primitives (`core/command.py`)

### Types

- **`HandlerFn`** = `Callable[[SdkPaths, list[str]], int | CommandResult]`
- **`CommandResult`** — dataclass: `data: Any`, `message: str`, `exit_code: int`. Has `render_text()` and `render_json()`.
- **`Arg`** — frozen dataclass: `name`, `description`, `required` (for help rendering only).

### CommandGroup

Flask Blueprint pattern. Domains create their own group, register subcommands via `@group.command()` decorator, export the group.

```python
group = CommandGroup("memory", "Manage agent memory",
    usage="sdk memory <subcommand> [args]",
    examples=["sdk memory list", "sdk memory compile"])

@group.command("write", description="Append a memory event",
    usage="sdk memory write <scope> <key> <value> [--tags=t1,t2]")
def write(paths: SdkPaths, args: list[str]) -> int:
    ...
```

Key methods:
- `dispatch(paths, args)` — route to subcommand by name
- `format_help(subcommand=None)` — render help text

### LeafCommand

Single handler, no subcommands. Same dispatch/help interface.

```python
command = LeafCommand("setup", handler=run, description="Run system setup")
```

### Registry

```python
registry = Registry()
registry.mount(group)           # mount a CommandGroup or LeafCommand
registry.dispatch(name, paths, args)  # returns exit code or None if not found
```

Dispatch wraps all calls with timing + NDJSON logging. Intercepts `--help`/`-h` before reaching handlers.

### registry.py (the manifest)

The only file in core/ that imports from domains/. Two lines per domain: import handler, mount it.

```python
from core.command import Registry
registry = Registry()

from domains.memory.handler import group as memory
from domains.setup.handler import command as setup
registry.mount(memory)
registry.mount(setup)
```

---

## 5. Models (`core/models.py`)

All Pydantic v2 models.

```python
class SdkPaths(BaseModel):
    """Injected into all handlers. Immutable."""
    model_config = ConfigDict(frozen=True)
    sdk_root: Path
    config_dir: Path       # sdk_root / "domains"
    setup_spec: Path       # domains/setup/setup.yml
    log_dir: Path          # sdk_root / "logs"
    out_dir: Path          # sdk_root / "out"

class SetupSpec(BaseModel):
    version: int = 1
    shell_rc: ShellRcSpec = Field(default_factory=ShellRcSpec)
    symlinks: list[SymlinkEntry] = Field(default_factory=list)

class ShellRcSpec(BaseModel):
    exports: dict[str, str] = Field(default_factory=dict)
    path_prepend: list[str] = Field(default_factory=list)

class SymlinkEntry(BaseModel):
    src: str    # relative to sdk_root
    dest: str   # absolute path (supports ~ and $PROJECTS expansion)

class DomainSpec(BaseModel):
    name: str
    description: str = ""
    installer: InstallerSpec | None = None

class InstallerSpec(BaseModel):
    topic: str = ""
    description: str = ""
    script: str = "install.sh"
    path_prepend: list[str] = Field(default_factory=list)
    exports: dict[str, str] = Field(default_factory=dict)
    shell_rc: str = ""
```

---

## 6. Memory Domain (`domains/memory/`)

Event-sourced agent memory. Three scopes: `personal`, `stacks/<name>`, `projects/<name>`.

### Event format (NDJSON)

```json
{"ts": "2026-04-02T07:58:29-0400", "scope": "personal", "key": "tone", "value": "Be concise", "tags": ["style"], "supersedes": null}
```

- `supersedes` names a key to replace. When writing a key that already exists, set `supersedes` to that key.
- `active_events()` filters out superseded records by tracking the latest index per key.

### File structure

```
domains/memory/
├── events/
│   ├── personal.ndjson
│   ├── stacks/
│   │   └── <name>.ndjson
│   └── projects/
│       └── <name>.ndjson
├── compiled/               # Generated markdown output
│   ├── personal.md
│   ├── stacks/<name>.md
│   └── projects/<name>.md
├── handler.py              # CommandGroup with 5 subcommands
├── events.py               # load_events(), active_events(), iter_scope_files()
├── compile.py              # compile_all() → per-scope markdown
└── domain.yml
```

### CLI interface

```
sdk memory write <scope> <key> <value> [--tags=t1,t2]
sdk memory list [scope]           # show active memories, optional scope filter
sdk memory query <keyword>        # search key/value/tags across all scopes
sdk memory compile                # regenerate compiled/ markdown from events/
sdk memory gc                     # report superseded event counts
```

### Compilation

`compile_all(memory_dir)` iterates all scope files, resolves active events, writes `compiled/<scope>.md`. Output format:

```markdown
# Memory: projects/myproject

- **key1**: value1 [tag1, tag2]
- **key2**: value2
```

### Key implementation details

- `load_events()` — reads NDJSON, skips malformed lines
- `active_events()` — tracks latest index per key, builds superseded set, returns non-superseded
- `iter_scope_files()` — enumerates `(scope_string, path)` pairs across personal/stacks/projects
- `write` subcommand auto-detects supersedes: if key already exists in active events, sets `supersedes` to that key
- Scope routing: `personal` → `events/personal.ndjson`, `stacks/foo` → `events/stacks/foo.ndjson`, `projects/bar` → `events/projects/bar.ndjson`

---

## 7. Setup Domain (`domains/setup/`)

System provisioning. Single command: `sdk setup`.

### setup.yml

```yaml
version: 1
shell_rc:
  exports:
    SDK_ROOT: "${SDK_ROOT}"
  path_prepend:
    - "$HOME/.local/bin"
symlinks:
  - src: sdk
    dest: ~/.local/bin/sdk
  - src: out/<hostname>/CLAUDE.md
    dest: ~/.claude/CLAUDE.md
  - src: out/<hostname>/context-index.md
    dest: ~/.claude/rules/context-index.md
```

### What `sdk setup` does

1. **Symlinks** — reads `setup.yml`, expands `~` and `$PROJECTS` in dest paths, creates parent dirs, atomically creates/replaces symlinks via `_link_safe()` (temp symlink + rename).
2. **Shell rc** — merges the `shell_rc` block into `~/.bashrc` between managed markers (`# --- asdk setup (shell_rc) ---` ... `# --- end asdk setup (shell_rc) ---`). Strips legacy markers on migration. Backs up original to `.bashrc.bak`. Uses atomic file replacement.

### Safety rules

- `_link_safe()` skips if dest exists and is NOT a symlink (won't overwrite regular files)
- Shell rc stripping validates marker pairs are well-formed before editing. Refuses to write if markers are nested, orphaned, or unclosed.
- All file writes use `replace_file_text_atomically()` — temp file in same dir + `os.replace()`

---

## 8. Context Delivery Architecture

### Three-tier model

| Tier | Mechanism | Budget | Per-turn cost |
|------|-----------|--------|---------------|
| Always-loaded | `~/.claude/CLAUDE.md`, alwaysApply rules | <1KB each | Every turn |
| Auto-loaded | Glob-matched rules (e.g., `*.py` triggers python.md) | <1KB each, <4KB aggregate | Only when matching files touched |
| Queryable | `sdk memory`, file reads, scripts | Unlimited | Only when explicitly pulled |

### Files

**`~/.claude/CLAUDE.md`** — behavioral bootloader. Symlink to `out/<hostname>/CLAUDE.md`.
- System identity (host, OS — 1 line)
- Behavioral kernel (prime directive, escalation rules, token discipline)
- Memory gate ("use sdk memory, not built-in memory") + compact command reference
- Pointer to context index
- Target: <1KB. Changes less than monthly.

**`~/.claude/rules/context-index.md`** — routing table. Symlink to `out/<hostname>/context-index.md`.
- `alwaysApply: true` rule (loaded every session)
- Pointers to: sdk memory commands, read-the-docs.sh script, skills directory, rules directory
- Points to mechanisms, not content. Agent lazy-loads actual content on demand.
- Target: <1KB.

### Host-keyed output (`out/<hostname>/`)

Artifacts are host-specific. Naming conventions:
- `CLAUDE.md` — behavioral bootloader (persistent, symlink target)
- `context-index.md` — context routing rule (persistent, symlink target)
- `<YYYYMMDD-HHMMSS>-<topic>.md` — timestamped reports/snapshots (adhoc, disposable)

Both CLAUDE.md and context-index.md are symlinked to `~/.claude/` by `sdk setup`.

---

## 9. Context Library (`domains/context-library/`)

Static configuration library. NOT a command domain (no handler.py).

```
context-library/
├── rules/                 # Claude Code rules with YAML frontmatter
│   ├── base_rules.md      # alwaysApply: true, globs: ["**"] — universal standards
│   ├── python.md          # globs: ["**/*.py"]
│   ├── typescript.md      # globs: ["**/*.ts", "**/*.tsx"]
│   ├── javascript.md
│   ├── security.md
│   └── testing.md
├── skills/                # One dir per skill, each with SKILL.md
│   ├── read-the-docs/     # SKILL.md + read-the-docs.sh (project snapshot script)
│   ├── simplify/          # SKILL.md + simplify.sh (git diff context script)
│   ├── critique/          # SKILL.md + critic.md (stance)
│   ├── plan-new/          # SKILL.md + architect.md (stance)
│   ├── plan-update/       # SKILL.md + builder.md (stance)
│   ├── plan-debug-diagnostics/  # SKILL.md + architect.md (stance)
│   └── ship/              # SKILL.md (git commit/push workflow)
├── stances/               # Behavioral mode templates (3-5 lines each)
│   ├── architect.md       # Design/diagnostic mode
│   ├── builder.md         # Implementation mode
│   └── critic.md          # Review/analysis mode
├── commands/              # CLI permission policies
│   ├── allow.txt          # Whitelisted commands
│   ├── deny.txt           # Blacklisted commands
│   └── prompt.txt         # Commands requiring confirmation
└── system_prompt.md       # Agent behavioral kernel
```

### Rule frontmatter format

```yaml
---
name: python
description: Python language rules and patterns
globs: ["**/*.py"]
alwaysApply: false
tags: [python]
---
```

### SKILL.md frontmatter format

```yaml
---
name: critique
description: Critical quality gate — find flaws, gaps, and risks in recent changes
type: analysis          # workflow | analysis | discovery
tags: [review, quality, security]
---
```

### Script-backed skills

Skills can include shell scripts alongside SKILL.md:

- **read-the-docs.sh** — takes a project path, generates a structured markdown snapshot (tree, git log, docs inventory, ADR index, config files, sdk memory query). Writes to `out/<hostname>/<ts>-read-the-docs-<project>.md`. Has `--stdout` flag for pipe mode.
- **simplify.sh** — takes a project path and optional commit range (default HEAD~3..HEAD), outputs git diff stats, changed files, recent log, working tree state, and relevant memories.

Both scripts resolve the SDK root from their own filesystem location (walk up from `skills/<name>/` to project root), locate the `sdk` executable, and query memories. Silent fail if sdk unavailable.

---

## 10. Utilities

### atomic_io.py

```python
def replace_file_text_atomically(path: Path, content: str, *, encoding: str = "utf-8") -> None:
```
Creates parent dirs, writes to a temp file in the same directory, then `os.replace()` for atomic swap.

### log.py

```python
def log_event(log_dir: Path, event: str, stack: str = "", exit_code: int | None = None,
              duration_ms: int | None = None, payload: dict | None = None) -> None:
```
Appends one JSON line to `logs/events.jsonl`. Never raises (silently swallows OSError). Called by `Registry.dispatch()`, not by handlers directly.

### shell_rc.py

Marker-delimited block editing for `.bashrc`:
- `try_strip_setup_shell_rc_blocks(lines)` — strips sdk setup region (current + legacy markers)
- `try_strip_install_block(lines, topic)` — strips per-topic install region
- Both return `(True, stripped_lines)` on success, `(False, original_lines)` if markers are malformed

### config.py

```python
def resolve_paths(sdk_root: Path) -> SdkPaths:
```
Builds `SdkPaths` from a root directory. Pure derivation, no I/O.

---

## 11. Testing

pytest suite in `tests/`. Mirrors core/ and domains/ structure. Key patterns:

- Tests use the `registry` singleton from `core.registry`
- `tmp_sdk_root` fixture — temp dir with `domains/` and `logs/` subdirs + minimal `setup.yml`
- `sdk_paths` fixture — `SdkPaths` pointing at `tmp_sdk_root`
- `memory_root` fixture — creates `events/` with scope subdirs inside temp root
- Pyright strict applies to test files

---

## 12. Bootstrap Sequence

To set up on a new machine:

```bash
# Clone or create the project
cd ~/projects && mkdir sdk && cd sdk

# Create and activate venv
python3 -m venv .venv && source .venv/bin/activate

# Install in dev mode
pip install -e ".[dev]"

# Create the host output directory
mkdir -p out/$(hostname)

# Write CLAUDE.md bootloader for this host
# Write context-index.md for this host
# Update setup.yml with this host's symlink paths

# Run setup
./sdk setup
source ~/.bashrc

# Verify
sdk help
sdk memory list
```

---

## 13. Key Design Decisions

1. **Event-sourced memory over database.** NDJSON files in git. Append-only writes, compile to readable markdown. Git history is the audit trail. No database dependency.

2. **Symlinks over copies for context delivery.** Single source of truth. Edit in sdk, consumers see immediately. `sdk setup` is the only management point.

3. **CLAUDE.md is a bootloader, not a store.** <1KB, behavioral kernel only. Everything else routes through the context index to lazy-loaded mechanisms.

4. **Content earns its injection.** Default tier is queryable (zero per-turn cost). Promotion to always-loaded requires demonstrated recurring value. All always-loaded content (CLAUDE.md, rules, skill descriptions) costs tokens on every single turn — there is no "load once" at the LLM layer.

5. **Host-keyed artifacts.** Different machines have different projects, hardware, and contexts. `out/<hostname>/` keeps host-specific artifacts isolated. `setup.yml` uses literal hostname paths — updated per host.

6. **Domains own commands, core owns infrastructure.** Adding a command: create `domains/<name>/handler.py` with a CommandGroup or LeafCommand, add two lines to `registry.py`. No cross-domain imports.

7. **Python-first, shell minimal.** Shell only for the `sdk` launcher (env setup before exec) and skill scripts (git/filesystem operations). Everything else is Python with strict typing.
