#!/usr/bin/python3
import json
import logging
import os
import tempfile
from datetime import timedelta, datetime
from pathlib import Path
from typing import Dict, Optional, cast

from filelock import FileLock


uid = os.getuid()
tmp = tempfile.gettempdir()
lock_file = Path(tmp) / 'qlist-%s.lock' % uid
state_file = Path(tmp) / 'qlist-%s' % uid
log_file = Path(tmp) / 'qlist-%s.log' % uid
my_dir = Path(__file__).parent


logging.basicConfig(filename=str(log_file), level=logging.DEBUG,
                    format='%(asctime)s %(name)s %(levelname)s %(message)s')
logger = logging.getLogger(__name__)


def write_state(state: Dict[str, object]) -> None:
    """Writes queue state to file."""
    logger.debug('writing state %s', state)
    with open(state_file, 'w') as f:
        json.dump(state, f)


def read_state() -> Dict[str, object]:
    """Reads queue state from file."""
    with open(state_file, 'r') as f:
        state = json.load(f)
        logger.debug('read state %s', state)
        return cast(Dict[str, object], state)


def update_job(job_id: str, js: str, error: Optional[str], check: bool = False) -> None:
    """Updates state for a job and commits it to the state file."""
    if error is None:
        error = ''
    logger.debug('updating job %s: state = %s, err = %s', job_id, js, error)
    with FileLock(str(lock_file.absolute())):
        state = read_state()
        assert isinstance(state['jobs'], Dict)
        if check and job_id not in state['jobs']:
            raise ValueError('No such job: %s' % job_id)
        state['jobs'][job_id] = {
            'state': js,
            'error': error,
            'delete_at': (datetime.now() + timedelta(seconds=30)).timestamp() if
            js in ['X', 'C', 'F'] else (datetime.now() + timedelta(minutes=60)).timestamp()
        }

        now = datetime.now().timestamp()
        delete = []
        for job_id, job_info in state['jobs'].items():
            if 'delete_at' in job_info and job_info['delete_at'] and now > job_info['delete_at']:
                delete.append(job_id)
        for job_id in delete:
            logger.debug('purging job %s', job_id)
            del state['jobs'][job_id]
        write_state(state)


def get_next_id() -> str:
    """Gets the next id from the state file and updates the state file."""
    with FileLock(str(lock_file.absolute())):
        try:
            state = read_state()
        except Exception as ex:
            logger.warning('Failed to read state file: %s', ex)
            state = {'crt_id': 1000000, 'jobs': {}}
            logger.debug('creating state')
        job_id = str(state['crt_id'])
        assert isinstance(state['crt_id'], int)
        state['crt_id'] += 1
        write_state(state)
        return job_id
