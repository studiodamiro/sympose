"""
Security & utility helpers for Sympose.
"""

import os
import re
import logging
from dotenv import load_dotenv

# Suppress verbose LiteLLM and external logs
logging.getLogger("LiteLLM").setLevel(logging.ERROR)
logging.getLogger("litellm").setLevel(logging.ERROR)

# Load environment variables
load_dotenv()

# Prevent background Vertex ADC credential lookup timeouts
os.environ.pop("GOOGLE_APPLICATION_CREDENTIALS", None)

try:
    import litellm
    litellm.drop_params = True
    litellm.request_timeout = 10.0
except ImportError:
    pass


def is_safe_path(target_path: str, base_dir: str = ".") -> bool:
    """Prevents directory traversal attacks (e.g. ../../etc/passwd)."""
    resolved_target = os.path.abspath(target_path)
    resolved_base = os.path.abspath(base_dir)
    return resolved_target.startswith(resolved_base)


def convert_md_to_slack_mrkdwn(text: str) -> str:
    """Converts standard LLM Markdown into Slack-compatible mrkdwn."""
    text = re.sub(r"^#{1,6}\s+(.+)$", r"*\1*", text, flags=re.MULTILINE)
    text = re.sub(r"\*\*(.*?)\*\*", r"*\1*", text)
    text = re.sub(r"```[a-zA-Z]+\n", "```\n", text)
    return text
