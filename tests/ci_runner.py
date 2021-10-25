#!/usr/bin/python
import datetime
import os
import secrets
import subprocess
import sys
from contextlib import contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import IO, Dict, TextIO, List, Optional, Generator

import requests


STABLE_BRANCHES = ['main']
FAKE_BRANCHES = ['main', 'feature_1', 'feature_x']
GITHUB_API_ROOT = 'https://api.github.com'


def read_line(f: TextIO) -> Optional[str]:
    line = f.readline()
    if line:
        line = line.strip()
        if len(line) > 0 and line[-1] == '\\':
            next_line = read_line(f)
            if not next_line:
                raise ValueError('Premature end of file')
            line = line[:-1] + next_line
        return line
    else:
        return None


def read_conf(fname: str) -> Dict[str, str]:
    conf = {}
    with open(fname, 'r') as f:
        line = read_line(f)
        while line is not None:
            if len(line) == 0:
                pass
            elif line[0] == '#':
                pass
            else:
                kv = line.split('=', 2)
                if len(kv) != 2:
                    raise ValueError('Invalid line in configuration file: "%s"' % line)
                conf[kv[0].strip()] = kv[1].strip()
            line = read_line(f)
    return conf


def get_conf(conf: Dict[str, str], name: str) -> str:
    if name not in conf:
        raise KeyError('Missing configuration option "%s"' % name)
    return conf[name]


def get_core_pr_branches(conf: Dict[str, str]) -> List[str]:
    repo = get_conf(conf, 'repository')
    resp = requests.get('%s/repos/%s/pulls?state=open&per_page=100' % (GITHUB_API_ROOT, repo))
    resp.raise_for_status()
    branches = []
    for pr in resp.json():
        if pr['head']['repo']['full_name'] == repo:
            branches.append(pr['head']['ref'])
    return branches


def do_clone(conf: Dict[str, str], dir: Path) -> None:
    repo = get_conf(conf, 'repository')
    subprocess.run(['git', 'clone', 'https://github.com/%s.git' % repo, 'code'], check=True,
                   cwd=str(dir))


def checkout(branch: str, dir: Path) -> None:
    subprocess.run(['git', 'checkout', branch], check=True, cwd=str(dir / 'code'))


def run_branch_tests(conf: Dict[str, str], dir: Path, run_id: str, clone: bool = True,
                     site_id: Optional[str] = None, fake_branch_name: Optional[str] = None) -> None:
    # it would be nice if this could be run through make; however, gnu make cannot preserve
    # spaces or quotes in arguments
    args = [sys.executable, '-m', 'pytest', '-v', '--upload-results', '--run-id', run_id]
    if site_id:
        args.append('--id')
        args.append(site_id)
    else:
        args.append('--id')
        args.append(get_conf(conf, 'id'))
    if fake_branch_name:
        args.append('--branch-name-override')
        args.append(fake_branch_name)
    for opt in ['maintainer_email', 'executors', 'server_url', 'key', 'max_age']:
        args.append('--' + opt.replace('_', '-'))
        args.append(get_conf(conf, opt))
    cwd = (dir / 'code') if clone else Path('.')
    env = dict(os.environ)
    env['PYTHONPATH'] = str(cwd.absolute() / 'src') + \
                        (':' + env['PYTHONPATH'] if 'PYTHONPATH' in env else '')
    subprocess.run([sys.executable, 'setup.py', 'launcher_scripts'], cwd=cwd.absolute(), check=True)
    subprocess.run(args, cwd=cwd.absolute(), env=env)


def get_run_id() -> str:
    now = datetime.datetime.now()
    return '%04d%02d%02d%02d-%s' % (now.year, now.month, now.day, now.hour, secrets.token_hex())


def run_tests(conf: Dict[str, str], site_ids: List[str], branches: List[str], clone: bool) -> None:
    run_id = get_run_id()
    with TemporaryDirectory() as tmp:
        tmpp = Path(tmp)
        if clone:
            with info('Cloning repository'):
                do_clone(conf, tmpp)
        for site_id in site_ids:
            for branch in branches:
                if clone:
                    checkout(branch, tmpp)
                with info('Testing branch "%s"' % branch):
                    run_branch_tests(conf, tmpp, run_id, clone, site_id, branch)


@contextmanager
def info(msg: str) -> Generator[bool, None, None]:
    print(msg + '... ', end='')
    sys.stdout.flush()
    try:
        yield True
        print('OK')
    except:
        print('FAILED')
        raise

if __name__ == '__main__':
    with info('Reading configuration'):
        conf = read_conf('testing.conf')
    scope = get_conf(conf, 'scope')
    clone = True
    site_ids = [get_conf(conf, 'id')]
    if scope == 'stable':
        branches = STABLE_BRANCHES
    elif scope == 'core':
        branches = get_core_pr_branches(conf)
    elif scope == 'fake':
        site_ids = ['"mira.alcf.anl.gov"', '"bw.ncsa.illinois.edu"', '"frontera.tacc.utexas.edu"']
        branches = FAKE_BRANCHES
        clone = False
    elif scope == 'local':
        branches = ['main']
        clone = False
    elif scope == 'tagged':
        raise NotImplementedError('Tagged scope not implemented yet.')
    else:
        raise ValueError('Unrecognized value for scope: "%s"' % scope)

    run_tests(conf, site_ids, branches, clone)
