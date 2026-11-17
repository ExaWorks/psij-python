import os
import subprocess
import sys
from pathlib import Path


def test_a_batch_executor_starts_in_a_home_without_psij_directory(tmp_path: Path) -> None:
    subprocess.run([sys.executable, '-c',
                    'from psij import JobExecutor; JobExecutor.get_instance("slurm")'],
                   env={**os.environ, 'HOME': str(tmp_path)}, check=True, capture_output=True)

    assert (tmp_path / '.psij').is_dir()
