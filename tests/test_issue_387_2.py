import os
import subprocess
import sys

import pytest


@pytest.mark.timeout(5)
def test_issue_387_2() -> None:
    subprocess.run([sys.executable, os.path.abspath(__file__)[:-2] + '.run'],
                   shell=True, check=True, capture_output=True)
