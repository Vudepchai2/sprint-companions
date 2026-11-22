import os
import subprocess
import sys
from pathlib import Path

ENGINE = Path(__file__).resolve().parents[1]


def run_cli(*args, input=None):
    return subprocess.run([sys.executable, "-m", "companions", *map(str, args)], input=input,
                          capture_output=True, text=True, encoding="utf-8", env=os.environ, cwd=ENGINE)
