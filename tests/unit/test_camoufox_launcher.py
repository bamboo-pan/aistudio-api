import subprocess
import sys
from pathlib import Path


def test_camoufox_launcher_file_execution_can_import_project_package():
    launcher = (
        Path(__file__).resolve().parents[2]
        / "src"
        / "aistudio_api"
        / "infrastructure"
        / "browser"
        / "camoufox_launcher.py"
    )

    result = subprocess.run(
        [sys.executable, str(launcher), "--help"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr or result.stdout
    assert "Launch Camoufox server with sanitized config" in result.stdout