import os
import subprocess
import sys


def test_user_guide_attach() -> None:
    my_dir = os.dirname(os.realpath(__file__))
    p = subprocess.run([sys.executable, os.path.join(my_dir, 'submit.py')], check=True,
                       capture_output=True)
    subprocess.run([sys.executable, os.path.join(my_dir, '/attach.py')], input=p.stdout,
                   check=True)
