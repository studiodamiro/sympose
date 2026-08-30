"""
Shared pytest fixtures for the Sympose test suite.

Every test that imports from sympose.* will trigger ConfigManager at import
time.  We patch the config_path to a temp file so tests never depend on the
real config.yaml on disk.
"""

import os
import json
import tempfile
import textwrap
import pytest


# ---------------------------------------------------------------------------
# Minimal config YAML written to a temp file so ConfigManager finds it.
# ---------------------------------------------------------------------------
MINIMAL_CONFIG_YAML = textwrap.dedent("""\
    performance:
      request_timeout: 5.0
      max_context_turns: 5
      max_worker_tool_turns: 3
      drop_unsupported_params: true
      stream: false
    session:
      exit_behavior:
        auto_save: false
        default_target: memory
        obsidian_subfolder: Sessions
        summarization_model: gemini/gemini-2.0-flash
    memory:
      user_profile_file: profiles/user_profile.md
      shared_memory_file: profiles/_shared_memory.md
      auto_compact: false
      compaction_threshold: 25
      extraction_timeout: 8.0
    runtime:
      default_persona: samantha
      profiles_dir: profiles
    vault:
      daily_notes_folder: Daily
      search_mode: direct
      ignore_folders:
        - .obsidian
        - .git
        - Attachments
""")


@pytest.fixture(scope="session", autouse=True)
def patch_env_for_tests(tmp_path_factory):
    """
    Session-scoped: write a minimal config.yaml to a temp dir and point
    SYMPOSE_CONFIG at it so that any module-level ConfigManager() instantiation
    uses safe, hermetic defaults.
    """
    cfg_dir = tmp_path_factory.mktemp("cfg")
    cfg_path = cfg_dir / "config.yaml"
    cfg_path.write_text(MINIMAL_CONFIG_YAML)

    # Prevent real vault / Slack / LiteLLM calls
    env_overrides = {
        "SYMPOSE_CONFIG": str(cfg_path),
        "MASTER_VAULT_PATH": "",
        "SLACK_BOT_TOKEN": "xoxb-test-token",
        "SLACK_APP_TOKEN": "xapp-test-token",
        "GEMINI_API_KEY": "test-key",
    }
    original = {k: os.environ.get(k) for k in env_overrides}
    os.environ.update(env_overrides)
    yield cfg_path
    # Restore
    for k, v in original.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v


@pytest.fixture()
def tmp_sessions_dir(tmp_path):
    """Returns a fresh temporary directory to be used as the sessions store."""
    d = tmp_path / "sessions"
    d.mkdir()
    return d


@pytest.fixture()
def tmp_vault_dir(tmp_path):
    """Returns a fresh temporary directory to be used as a mock Obsidian vault."""
    vault = tmp_path / "vault"
    vault.mkdir()
    return vault


@pytest.fixture()
def sample_session_jsonl():
    """
    Creates a minimal single-turn JSONL session file in the active sessions dir
    and returns (fpath, session_id) so tests can manipulate it directly.
    """
    import datetime, uuid
    # Import here so monkeypatch has already applied resolve_workspace_dir
    from sympose.sessions import SessionManager
    session_id = f"samantha_20240101_120000_{uuid.uuid4().hex[:6]}"
    sessions_dir = SessionManager.get_sessions_dir()
    fpath = os.path.join(sessions_dir, f"{session_id}.jsonl")
    now = datetime.datetime.now().isoformat()
    meta = {
        "type": "meta",
        "session_id": session_id,
        "handle": "samantha",
        "title": "Hello World",
        "created_at": now,
        "updated_at": now,
        "turns_count": 1,
    }
    turn = {
        "type": "turn",
        "timestamp": now,
        "user": "Hello",
        "assistant": "Hi there!",
    }
    with open(fpath, "w", encoding="utf-8") as f:
        f.write(json.dumps(meta) + "\n")
        f.write(json.dumps(turn) + "\n")
    return fpath, session_id

