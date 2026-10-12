from __future__ import annotations

import re
import subprocess
import sys
import os
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def find_skill_dir() -> Path:
    """Locate skill resources in a checkout or a regular wheel installation."""
    candidates = [
        REPO_ROOT / "skills" / "evidence-grounded-paper-deep-read",
        REPO_ROOT / "share" / "paperdeepread" / "skill",  # pip --target
        Path(sys.prefix) / "share" / "paperdeepread" / "skill",
    ]
    for candidate in candidates:
        if (candidate / "SKILL.md").is_file():
            return candidate
    raise RuntimeError("Bundled paper-reading skill is missing; reinstall paperdeepread.")


SKILL_DIR = find_skill_dir()


def slugify(value: str) -> str:
    value = value.lower()
    value = re.sub(r"[^\w]+", "-", value, flags=re.UNICODE).replace("_", "-")
    return value.strip("-") or "paper"


def read_text(path: Path, limit: int | None = None) -> str:
    text = path.read_text(encoding="utf-8-sig", errors="replace")
    if limit is not None and len(text) > limit:
        return text[:limit] + "\n\n[TRUNCATED BY CLI INPUT LIMIT]\n"
    return text


def run_python_script(script: Path, args: list[str], cwd: Path = REPO_ROOT) -> subprocess.CompletedProcess[str]:
    command = [sys.executable, str(script), *args]
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return subprocess.run(
        command,
        cwd=cwd,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )


def require_success(result: subprocess.CompletedProcess[str], stage: str) -> None:
    if result.returncode != 0:
        raise RuntimeError(f"{stage} failed with exit code {result.returncode}\n{result.stdout}")
