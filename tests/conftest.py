#!/usr/bin/python3
# type: ignore
import datetime
import io
import json
import logging
import os
import re
import secrets
import shutil
import signal
import socket
import subprocess
import sys
import threading
import time
import traceback
from functools import partial
from pathlib import Path
from typing import Dict, List, Optional

import requests
from _pytest._io import TerminalWriter
from ci_runner import get_run_id
from filelock import FileLock

from executor_test_params import ExecutorTestParams

import pytest


logger = logging.getLogger(__name__)


LOG_FORMATTER = logging.Formatter(fmt='%(asctime)s %(levelname)s %(message)s\n',
                                  datefmt='%Y-%m-%d %H:%M:%S')
LOG_FORMATTER.converter = time.gmtime
SETTINGS_DIR = Path.home() / '.psij'
KEY_FILE = SETTINGS_DIR / '.key'
NEW_KEY_FILE = SETTINGS_DIR / 'key'
ID_FILE = SETTINGS_DIR / '.id'
RESULTS_ROOT = Path('tests') / 'results'


def pytest_addoption(parser):
    parser.addoption('--executors', action='store', default='auto',
                     help='A set of executors (or executor:launcher pairs) to run the tests on. '
                          'The special value "auto" means all executors that can be determined to '
                          'be accessible.')
    parser.addoption('--save-results', action='store_true', default=False,
                     help='If specified, save test results in a way that allows them to be '
                          'uplaoded to a results server later.')
    parser.addoption('--upload-results', action='store_true', default=False,
                     help='If specified, upload results to a test result server specified in'
                          'the testing.conf file.')
    parser.addoption('--max-age', action='store', default='48',
                     help='Maximum age, in hours, of tests to keep saved.')
    parser.addoption('--id', action='store', default='hostname',
                     help='An identifier for this site to attach to tests when aggregated.')
    parser.addoption('--server-url', action='store', default='https://testing.exaworks.org',
                     help='The base URL of the test aggregation server.')
    parser.addoption('--key', action='store', default='random',
                     help='A secret to use when communicating to the aggregation server.')
    parser.addoption('--maintainer-email', action='store', default=None,
                     help='An optional email for the test maintainer.')
    parser.addoption('--run-id', action='store', default=None,
                     help='Externally supplied run ID.')
    parser.addoption('--branch-name-override', action='store', default=None,
                     help='Pretend that the current git branch is this value.')
    parser.addoption('--queue-name', action='store', default=None,
                     help='A queue to run the batch jobs in.')
    parser.addoption('--project-name', action='store', default=None,
                     help='A project/account name to associate the batch jobs with.')
    parser.addoption('--custom-attributes', action='store', default=None,
                     help='A set of custom attributes to pass to jobs.')
    parser.addoption('--minimal-uploads', action='store_true', default=False,
                     help='Enables minimal uploads mode, which restricts the information that '
                          'is uploaded to the test aggregation server. ')


def debug(sig, frame):
    print('Dumping thread info')
    with open('/tmp/python-dump.txt', 'w') as f:
        try:
            for thr in threading.enumerate():
                f.write(str(thr))
                f.write('\n')
                traceback.print_stack(sys._current_frames()[thr.ident], file=f)
                f.write('\n\n')
        except Exception as ex:
            logger.exception('Failed to dump thread info')
            f.write(str(ex))


signal.signal(signal.SIGUSR1, debug)
print('SIGUSR1 handler installed.')


def _get_executors(config: Dict[str, str]) -> List[str]:
    execs_str = config.getoption('executors')
    execs = execs_str.split(',')
    processed = []
    for exec_str in execs:
        exec_str = exec_str.strip()
        comps = re.split(':', exec_str, maxsplit=2)
        execs_t = _translate_executor(config, comps[0])
        if len(execs_t) > 0:
            if len(comps) == 1:
                # executor(s) only; this allows for "auto" which means all local and auto_q:auto_l
                processed.extend(execs_t)
            elif len(comps) in [2, 3]:
                # executor and launcher
                assert len(execs_t) == 1
                executor = execs_t[0]
                launcher = _translate_launcher(config, executor, comps[1])
                if len(comps) == 2:
                    processed.append(executor + ':' + launcher)
                else:
                    processed.append(executor + ':' + launcher + ':' + comps[2])

    return processed


def _translate_executor(config: Dict[str, str], executor: str) -> List[str]:
    if executor == 'auto':
        execs = ['local:single', 'local:multiple', 'batch-test:single', 'batch-test:multiple',
                 'batch-test:batch-test']
        queue_execs = _translate_executor(config, 'auto_q')
        assert len(queue_execs) in [0, 1]
        queue_exec = None
        if len(queue_execs) == 1:
            queue_exec = queue_execs[0]
            queue_launcher = _translate_launcher(config, queue_exec, 'auto_l')
        if config.option.environment.get('has_mpirun'):
            execs.extend(['local:mpirun', 'batch-test:mpirun'])
        if queue_exec:
            execs.extend([queue_exec + ':single', queue_exec + ':multiple'])
            if queue_launcher:
                execs.append(queue_exec + ':' + queue_launcher)
            else:
                execs.append(queue_exec)
        return execs
    if executor == 'auto_q':
        if config.option.environment.get('has_slurm'):
            return ['slurm']
        elif config.option.environment.get('has_pbs'):
            return ['pbs']
        elif config.option.environment.get('has_lsf'):
            return ['lsf']
        elif config.option.environment.get('has_cobalt'):
            return ['cobalt']
        elif config.option.environment.get('has_flux'):
            return ['flux']
        else:
            # nothing yet
            return []
    return [executor]


def _translate_launcher(config: Dict[str, str], exec: str, launcher: str) -> str:
    if launcher == 'auto_l':
        if exec == 'slurm':
            return 'srun'
        else:
            raise ValueError('Don\'t know how to get launcher for executor "' + exec + '"')
    else:
        return launcher


def pytest_generate_tests(metafunc):
    if 'execparams' in metafunc.fixturenames:

        etps = []
        for x in _get_executors((metafunc.config)):
            etp = ExecutorTestParams(x, queue_name=metafunc.config.option.queue_name,
                                     project_name=metafunc.config.option.project_name,
                                     custom_attributes_raw=metafunc.config.option.custom_attributes)
            etps.append(etp)

        metafunc.parametrize('execparams', etps, ids=lambda x: str(x))


def _set_root_logger(logger):
    logging.root = logger
    logging.Logger.root = logger


_capture_lock = threading.RLock()


def _capture_log(fn):
    # need to serialize this since there's only one root logger
    with _capture_lock:
        orig_logger = logging.getLogger()
        logger = logging.getLogger('capture')
        logger.setLevel(logging.DEBUG)
        logger.propagate = True
        buffer = io.StringIO()
        logger.addHandler(logging.StreamHandler(buffer))
        _set_root_logger(logger)
        try:
            result = fn()
        finally:
            _set_root_logger(orig_logger)
            log = buffer.getvalue()
            buffer.close()

        return result, log


def _purge_old_results(config):
    pass


def pytest_configure(config):
    logging.basicConfig(format='%(asctime)s %(levelname)s %(message)s',
                        datefmt='%Y-%m-%d %H:%M:%S', level=logging.DEBUG)
    logging.root.setLevel(logging.DEBUG)

    _purge_old_results(config)
    start_time = _now()
    (env, key), log = _capture_log(partial(_discover_environment, config))
    save = config.getoption('save_results')
    upload = config.getoption('upload_results')
    config.option.key = key
    end_time = _now()
    data = {}
    if save or upload:
        data.update({
            'module': '_conftest',
            'cls': None,
            'function': '_discover_environment',
            'test_name': '_discover_environment',
            'log': log,
            'results': {},
            'extras': env,
            'test_start_time': start_time,
            'test_end_time': end_time,
            'run_id': env['run_id'],
            'branch': env['git_branch']
        })
        _save_or_upload(config, data)


def _get_config_env(config, name):
    if hasattr(config.option, 'environment'):
        return config.option.environment[name]
    else:
        return None


def pytest_unconfigure(config):
    save = config.getoption('save_results')
    upload = config.getoption('upload_results')
    if save or upload:
        data = {
            'module': '_conftest',
            'cls': None,
            'function': '_end',
            'test_name': '_end',
            'results': {},
            'extras': None,
            'test_start_time': _now(),
            'test_end_time': _now(),
            'run_id': _get_config_env(config, 'run_id'),
            'branch': _get_config_env(config, 'git_branch')
        }
        if hasattr(config.option, 'environment'):
            # only upload if we were able to get a basic environment
            _save_or_upload(config, data)


def _cache(file_path, fn):
    lock = FileLock(file_path.with_suffix('.lock'))
    with lock:
        if not os.path.exists(file_path):
            value = fn()
            with open(file_path, 'w') as f:
                f.write(value)
        else:
            with open(file_path, 'r') as f:
                value = f.read().strip()
    return value


def _get_key(config):
    if Path(NEW_KEY_FILE).exists():
        with open(NEW_KEY_FILE) as f:
            return f.read().strip()
    else:
        # use legacy if needed
        key = config.getoption('key')
        logger.warning('Legacy keys are deprecated. Please go to https://testing.psij.io/auth.html '
                       'to obtain an authentication key.')
        if key == 'random':
            return _cache(KEY_FILE, secrets.token_hex)
        elif key[0] == '"' and key[-1] == '"':
            return key[1:-1]
        else:
            raise ValueError('Invalid value for --key argument: "%s"' % key)


def _get_id(config):
    id = config.getoption('id')
    if id == 'hostname':
        return socket.getfqdn()
    elif id == 'random':
        return _cache(ID_FILE, secrets.token_hex)
    elif id[0] == '"' and id[-1] == '"':
        return id[1:-1]
    else:
        raise ValueError('Invalid value for --id argument: "%s"' % id)


def _run(*args) -> str:
    process = subprocess.run(args, check=False, text=True,
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if process.returncode != 0:
        raise Exception('Command %s failed with exit code %s. Output: %s, %s' %
                        (args, process.returncode, process.stdout, process.stderr))
    return process.stdout.strip()


def _get_git_branch(config) -> str:
    conf_branch = config.getoption('branch_name_override')
    if conf_branch:
        return conf_branch
    else:
        return _run('git', 'rev-parse', '--abbrev-ref', 'HEAD')


def _get_last_commit() -> str:
    return _run('git', 'log', '-n', '1', '--pretty=format:"%H"')


def _get_commit_diff():
    result = _run('git', 'rev-list', '--left-right', '--count', 'origin...HEAD')
    lr = result.split()
    assert len(lr) == 2
    return int(lr[0]), int(lr[1])


def _get_git_diff_stat():
    return _run('git', 'diff', '--stat')


def _get_run_id(config):
    run_id = config.getoption('run_id')
    if run_id is None:
        run_id = get_run_id()
    return run_id


def _has_flux():
    try:
        import flux
        flux.Flux()
    except Exception:
        return False
    return True


def _try_run_command(args, timeout=None):
    try:
        process = subprocess.run(args, timeout=timeout, text=True,
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        logger.debug('Output from {}: {} {}'.format(args, process.stdout, process.stderr))
        return process.returncode == 0
    except subprocess.TimeoutExpired:
        return False


def _get_env(name: str) -> str:
    if name in os.environ:
        return os.environ[name]
    else:
        return ''


def _parse_custom_attributes(s: Optional[str]) -> Dict[str, object]:
    if s is None:
        return None
    else:
        attrspec = json.loads('[' + s + ']')
        d = {}
        for item in attrspec:
            if item['filter'] not in d:
                d[item['filter']] = {}
            d[item['filter']].update(item['value'])
        return d


def _strip_home(path: List[str]) -> List[str]:
    # remove explicit references to home directories and replace with "~/"
    home = os.path.realpath(os.path.expanduser('~'))
    if home[-1] == '/':
        home = home[:-1]
    r = []
    for p in path:
        p = os.path.realpath(p)
        if p.startswith(home):
            p = '~' + p[len(home):]
        r.append(p)
    return r


def _discover_environment(config):
    SETTINGS_DIR.mkdir(parents=True, exist_ok=True)
    RESULTS_ROOT.mkdir(parents=True, exist_ok=True)
    env = {}
    conf = {}
    env['config'] = conf
    conf['id'] = _get_id(config)
    conf['pythonpath'] = _strip_home(sys.path)
    conf['executors'] = config.getoption('executors')
    conf['maintainer_email'] = config.getoption('maintainer_email')
    key = _get_key(config)
    env['start_time'] = _now()
    env['run_id'] = _get_run_id(config)
    env['in_conda'] = _get_env('CONDA_SHLVL') != '' and _get_env('CONDA_SHLVL') != '0'
    env['in_venv'] = _get_env('VIRTUAL_ENV') != ''
    config.option.custom_attributes = _parse_custom_attributes(
        config.getoption('custom_attributes'))

    try:
        env['git_branch'] = _get_git_branch(config)
        env['git_last_commit'] = _get_last_commit()
        ahead, behind = _get_commit_diff()
        env['git_ahead_remote_commit_count'] = ahead
        env['git_behind_remote_commit_count'] = behind
        env['git_local_change_summary'] = _get_git_diff_stat()
        env['git_has_local_changes'] = (env['git_local_change_summary'] != '')
    except Exception as ex:
        logger.exception(ex)
        save = config.getoption('save_results')
        upload = config.getoption('upload_results')
        if save or upload:
            raise Exception('Cannot get required repository information.')
        else:
            logger.warning('Cannot get git repository information.')
    try:
        env['has_slurm'] = shutil.which('sbatch') is not None
        if 'has_slurm' not in env:
            env['has_pbs'] = shutil.which('qsub') is not None
        env['has_lsf'] = shutil.which('bsub') is not None
        env['has_cobalt'] = shutil.which('cqsub') is not None
        env['has_mpirun'] = shutil.which('mpirun') is not None
        env['has_flux'] = _has_flux()
        env['can_ssh_to_localhost'] = _try_run_command(['ssh', '-oBatchMode=yes',
                                                        '-oStrictHostKeyChecking=no', 'localhost',
                                                        'true'], timeout=5)
    except Exception as ex:
        env['error'] = str(ex)
    config.option.environment = env
    env['computed_executors'] = _get_executors(config)
    return env, key


def _now():
    return datetime.datetime.now(tz=datetime.timezone.utc).isoformat(' ')


def _process_custom_attributes(item):
    if not hasattr(item, 'callspec'):
        return
    if 'execparams' not in item.callspec.params:
        return
    ep: Optional[List[Dict[str, Dict[str, object]]]] = item.callspec.params['execparams']
    if ep.custom_attributes_raw is None:
        return
    if ep is None:
        return
    test_name = item.name
    for filter, attrs in ep.custom_attributes_raw.items():
        if re.match(filter, test_name):
            ep.custom_attributes.update(attrs)


def _set_attrs(execparams, attrs):
    for k, v in attrs.items():
        execparams.customattributes[k] = v


@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item, call):
    _process_custom_attributes(item)

    outcome = yield
    report = outcome.get_result()

    if hasattr(item, 'result'):
        d = getattr(item, 'result')
    else:
        d = {}
        setattr(item, 'result', d)
    buf = io.StringIO()

    buf.isatty = lambda: True
    tw = TerminalWriter(file=buf)
    report.toterminal(tw)
    report_text = buf.getvalue()
    d[report.when] = {'status': report.outcome, 'exception': outcome.excinfo, 'report': report_text}


@pytest.fixture(autouse=True)
def report(capsys, caplog, request, pytestconfig):
    save = pytestconfig.getoption('save_results')
    upload = pytestconfig.getoption('upload_results')
    if save or upload:
        caplog.set_level(logging.DEBUG)
        start = _now()
        yield
        captured = capsys.readouterr()
        log = ''
        for step in ['setup', 'call', 'teardown']:
            if step in request.node.result:
                records = caplog.get_records(step)
                for record in records:
                    log += LOG_FORMATTER.format(record)
        data = {
            'stdout': captured.out,
            'stderr': captured.err,
            'log': log,
            'module': request.module.__name__,
            'cls': request.cls.__name__ if request.cls else None,
            'function': request.function.__name__,
            'test_name': request.node.name if request.node.name else request.function.__name__,
            'test_start_time': start,
            'test_end_time': _now(),
            'run_id': pytestconfig.option.environment['run_id'],
            'branch': pytestconfig.option.environment['git_branch'],
            'results': {},
            'extras': None
        }
        for step in ['setup', 'call', 'teardown']:
            if step in request.node.result:
                data['results'][step] = {'passed': request.node.result[step]['status'] == 'passed',
                                         'status': request.node.result[step]['status'],
                                         'exception': request.node.result[step]['exception'],
                                         'report': request.node.result[step]['report']}

        _save_or_upload(pytestconfig, data)
    else:
        yield


def _mk_test_fname(data):
    cls = data['cls']
    return '%s-%s-%s.json' % (data['module'], cls if cls is not None else '_', data['function'])


def _save_or_upload(config, data):
    minimal = config.getoption('minimal_uploads')
    save = config.getoption('save_results')
    upload = config.getoption('upload_results')
    if upload and minimal:
        save = True
    if save:
        _save_report(config, data)
    if upload:
        _upload_report(config, data)


def _save_report(config, data):
    env = config.option.environment
    path = RESULTS_ROOT / env['run_id'] / env['git_branch'] / _mk_test_fname(data)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'w') as f:
        json.dump(data, f, indent=4)


_SAFE_KEYS = ['module', 'cls', 'function', 'test_name', 'test_start_time', 'test_end_time',
              'run_id', 'branch', 'results.setup.passed', 'results.setup.status',
              'results.call.passed', 'results.call.status', 'results.teardown.passed',
              'results.teardown.status', 'extras.start_time', 'extras.run_id', 'extras.git_branch',
              'extras.git_last_commit', 'extras.git_ahead_remote_commit_count',
              'extras.git_behind_remote_commit_count', 'extras.git_has_local_changes',
              'extras.config.id', 'extras.config.executors', 'extras.config.maintainer_email']
_SAFE_KEYS_PROCESSED = {}


def _add_key(d: Dict[str, object], parts: List[str]) -> None:
    key = parts[0]
    if len(parts) == 1:
        d[key] = True
    else:
        if key not in d:
            d[key] = {}
        if isinstance(d[key], dict):
            _add_key(d[key], parts[1:])
        else:
            raise ValueError('Unexpected value in keys dict: %s' % d[key])


def _process_safe_keys() -> None:
    for key in _SAFE_KEYS:
        parts = key.split('.')
        _add_key(_SAFE_KEYS_PROCESSED, parts)


def _do_sanitize(data: Dict[str, object], result: Dict[str, object],
                 safe: Dict[str, object]) -> None:
    for k, v in data.items():
        if isinstance(v, bool):
            # booleans are allowed automatically
            result[k] = v
            continue
        if k not in safe:
            continue
        s = safe[k]
        if s is True:
            if isinstance(v, dict):
                # value expected, but got dict instead
                raise ValueError('Unexpected dict in data: %s' % v)
            result[k] = v
        else:
            # only dicts and True are in safe, so this must be a dict (or None)
            if isinstance(v, dict):
                rd = {}
                result[k] = rd
                _do_sanitize(v, rd, s)
            elif v is None:
                result[k] = None
            else:
                raise ValueError('Unexpected value (%s) in data for key %s' % (v, k))


def _sanitize(data: Dict[str, object]) -> Dict[str, object]:
    if len(_SAFE_KEYS_PROCESSED) == 0:
        _process_safe_keys()
    result = {}
    _do_sanitize(data, result, _SAFE_KEYS_PROCESSED)
    return result


def _upload_report(config, data):
    env = config.option.environment

    url = config.getoption('server_url')
    if not url:
        return
    minimal = config.getoption('minimal_uploads')
    if minimal:
        data = _sanitize(data)
    resp = requests.post('%s/result' % url, json={'id': env['config']['id'],
                                                  'key': config.option.key, 'data': data})
    resp.raise_for_status()
