import subprocess
import sys


def test_user_guide_attach() -> None:
    p = subprocess.run([sys.executable, './submit.py'], check=True, capture_output=True)
    subprocess.run([sys.executable, './attach.py'], input=p.stdout, check=True)
