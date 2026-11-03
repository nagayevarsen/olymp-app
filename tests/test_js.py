"""Запускает проверку логики браузера (dates.js и filters.js) через Node.js."""

import shutil
import subprocess
from pathlib import Path

import pytest


@pytest.mark.skipif(shutil.which("node") is None, reason="Node.js не установлен")
def test_browser_logic_matches_cases():
    script = Path(__file__).parent / "check_js.js"
    result = subprocess.run(
        ["node", str(script)], capture_output=True, text=True, encoding="utf-8"
    )
    assert result.returncode == 0, result.stdout + result.stderr
