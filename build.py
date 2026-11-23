"""Build with a Python environment containing PyInstaller."""
from pathlib import Path
import subprocess
import sys
import tempfile


if __name__ == "__main__":
    project = Path(__file__).resolve().parent
    with tempfile.TemporaryDirectory() as temp:
        subprocess.run([sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean",
                        "--onefile", "--windowed", "--name", "PingProf",
                        "--distpath", str(project/"dist"), "--workpath", temp,
                        "--specpath", temp, str(project/"pingprof.py")],check=True)
