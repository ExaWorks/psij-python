import os
import site
import subprocess
import sys
from pathlib import Path


def test_a_batch_executor_starts_in_a_home_without_psij_directory(tmp_path: Path) -> None:
    p = subprocess.run([sys.executable, '-c',
                        'from psij import JobExecutor; JobExecutor.get_instance("slurm")'],
                       env={**os.environ, 'HOME': str(tmp_path),
                            'PYTHONUSERBASE': site.getuserbase()},
                       capture_output=True, text=True)

    assert p.returncode == 0, p.stderr
    assert (tmp_path / '.psij').is_dir()
