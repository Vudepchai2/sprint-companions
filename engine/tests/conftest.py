import os
import subprocess
import sys
from pathlib import Path

import pytest

ENGINE = Path(__file__).resolve().parents[1]


def run_cli(*args, input=None):
    return subprocess.run([sys.executable, "-m", "companions", *map(str, args)], input=input,
                          capture_output=True, text=True, encoding="utf-8", env=os.environ, cwd=ENGINE)


@pytest.fixture
def home(tmp_path, monkeypatch):
    """A fresh companions folder: COMPANIONS_HOME points at tmp_path."""
    monkeypatch.setenv("COMPANIONS_HOME", str(tmp_path))
    return tmp_path
