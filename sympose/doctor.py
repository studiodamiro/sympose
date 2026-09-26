"""`sympose doctor` (docs/decisions/029): looks at an installation, says plainly what is wrong, and with `--fix`
corrects only what belongs to Sympose (persona folders, the settings file), never the notes.

Each check is a function returning findings; a later check is one more entry in `CHECKS`."""

import json
import os
import sys
from dataclasses import dataclass
from functools import partial
from typing import Callable, TextIO

import yaml

from sympose import profile, settings_store
from sympose.persona_files import PERSONA_FILENAME, persona_dir, profiles_dir


@dataclass(frozen=True)
class Finding:
    problem: str
    fix: str | None = None  # what `--fix` does; None: it needs the person
    apply: Callable[[], object] | None = None


def _taken(src: str, dst: str) -> bool:
    """`dst` is a different folder than `src` (on a filesystem that ignores case, `Grace` and `grace` are one)."""
    if not os.path.lexists(dst):
        return False
    try:
        return not os.path.samefile(src, dst)
    except OSError:  # a link to nowhere is in the way all the same
        return True


def _case(base: str, name: str) -> list[Finding]:
    lower = name.lower()
    if name == lower:
        return []
    src, dst = os.path.join(base, name), os.path.join(base, lower)
    problem = f"the persona folder {name!r} is not lower case (on a filesystem that keeps case, the persona is missing)"
    if _taken(src, dst):
        return [Finding(f"{problem}, and a different folder {lower!r} exists: rename or remove one of them")]
    return [Finding(problem, f"rename it to {lower!r}", lambda: os.rename(src, dst))]


def _reason(error: Exception) -> str:
    """One line for why a file failed: YAML's own message repeats the path and spans several lines."""
    problem, mark = getattr(error, "problem", None), getattr(error, "problem_mark", None)
    if not problem:
        return " ".join(str(error).split())
    return f"{problem} (line {mark.line + 1})" if mark else problem


def _unreadable(base: str, name: str) -> list[Finding]:
    path = os.path.join(base, name, PERSONA_FILENAME)
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except (OSError, UnicodeDecodeError, yaml.YAMLError) as e:
        return [Finding(f"{path} cannot be read, so the persona is missing: {_reason(e)}")]
    if not isinstance(data, dict):
        return [Finding(f"{path} is not a set of `key: value` lines, so the persona is missing")]
    return []


def check_persona_folders() -> list[Finding]:
    base = profiles_dir()
    if not os.path.isdir(base):
        return []  # no profiles/ at all: Samantha over the whole vault, nothing to check
    findings: list[Finding] = []
    for name in sorted(os.listdir(base)):
        if os.path.isfile(os.path.join(base, name, PERSONA_FILENAME)):  # a persona is a folder with a persona.yaml
            findings += _case(base, name) + _unreadable(base, name)
    return findings


def _has_persona_file(handle: str) -> bool:
    """The persona's `persona.yaml` is there, readable or not: an unreadable one is its own finding."""
    try:
        return os.path.isfile(os.path.join(persona_dir(handle), PERSONA_FILENAME))
    except ValueError:
        return False


def _remove_setting(key: str) -> None:
    if not settings_store.remove(key):
        raise OSError(f"could not write {settings_store.settings_path()}")


def check_settings() -> list[Finding]:
    path = settings_store.settings_path()
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError) as e:
        return [Finding(f"{path} cannot be read, so every setting is at its default: {e}")]
    if not isinstance(data, dict):
        return [Finding(f"{path} is not a JSON object, so every setting is at its default")]
    findings = []
    for key in ("chat_model", "default_persona"):
        if key in data and not settings_store.is_name(data[key]):
            findings.append(
                Finding(
                    f"the {key} setting is {json.dumps(data[key])}, not a name",
                    f"remove {key}, so the default applies",
                    partial(_remove_setting, key),
                )
            )
    chosen = data.get("default_persona")
    if settings_store.is_name(chosen) and os.path.isdir(profiles_dir()):
        # the shipped default answers without a folder of its own (`resolve_profile`'s safety net)
        if chosen.lower() != profile.FACTORY_DEFAULT_PERSONA and not _has_persona_file(chosen):
            findings.append(
                Finding(
                    f"the default_persona setting {chosen!r} names no persona",
                    "remove default_persona, so Samantha is the default",
                    partial(_remove_setting, "default_persona"),
                )
            )
    return findings


# settings after folders: a renamed folder can make a default_persona valid again
CHECKS: list[Callable[[], list[Finding]]] = [check_persona_folders, check_settings]


def run(fix: bool = False, out: TextIO | None = None) -> int:
    """Prints the findings (and, with `fix`, applies what can be) and returns 0 when nothing is left wrong, else 1."""
    out = out or sys.stdout
    found = left = 0
    for check in CHECKS:
        for finding in check():
            found += 1
            print(f"- {finding.problem}", file=out)
            if finding.apply is None:
                left += 1
                print("    needs you: nothing here can be fixed automatically", file=out)
            elif not fix:
                left += 1
                print(f"    --fix would: {finding.fix}", file=out)
            else:
                try:
                    finding.apply()
                    print(f"    fixed: {finding.fix}", file=out)
                except OSError as e:
                    left += 1
                    print(f"    could not fix it: {e}", file=out)
    if not found:
        print("Everything looks healthy.", file=out)
    elif left:
        fixable = "" if fix else " (`sympose doctor --fix` corrects the ones marked --fix)"
        print(f"\n{left} of {found} problem(s) left{fixable}.", file=out)
    else:
        print(f"\nFixed {found} problem(s).", file=out)
    return 1 if left else 0
