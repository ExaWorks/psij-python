#!/usr/bin/python
import datetime
import os
import secrets
import shutil
import subprocess
import sys
from contextlib import contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Dict, TextIO, List, Optional, Generator

import requests


STABLE_BRANCHES = ['main']
FAKE_BRANCHES = ['main', 'feature_1', 'feature_x']
GITHUB_API_ROOT = 'https://api.github.com'
MODE = 'plain'


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


def run(*args: str, cwd: Optional[str] = None) -> str:
    p = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False,
                       cwd=cwd, text=True)
    if p.returncode != 0:
        print(p.stdout)
        raise subprocess.CalledProcessError(p.returncode, args, output=p.stdout)
    return p.stdout


def get_conf(conf: Dict[str, str], name: str, default: Optional[str] = None) -> str:
    if name not in conf:
        if default is not None:
            return default
        else:
            raise KeyError('Missing configuration option "%s"' % name)
    return conf[name]


def get_core_pr_branches(conf: Dict[str, str]) -> List[str]:
    repo = get_conf(conf, 'repository')
    resp = requests.get('%s/repos/%s/pulls?state=open&per_page=100' % (GITHUB_API_ROOT, repo))
    resp.raise_for_status()
    branches = ['main']
    for pr in resp.json():
        if pr['head']['repo']['full_name'] == repo:
            branches.append(pr['head']['ref'])
    return branches


def do_clone(conf: Dict[str, str], dir: Path) -> None:
    repo = get_conf(conf, 'repository')
    run('git', 'clone', 'https://github.com/%s.git' % repo, 'code', cwd=str(dir))


def checkout(branch: str, dir: Path) -> None:
    run('git', 'checkout', branch, cwd=str(dir / 'code'))


def get_pip() -> str:
    if sys.executable[-1] == '3':
        return 'pip3'
    else:
        return 'pip'


def install_deps(branch: str, dir: Path) -> None:
    reqpath = dir / 'code' / 'requirements-tests.txt'
    if not reqpath.exists():
        return

    destpath = dir / 'code' / '.packages'
    # there have been cases when pip failed to leave a consistent
    # installation after a downgrade, so best to start clean
    if destpath.exists():
        shutil.rmtree(str(destpath))
    if MODE == 'plain':
        run(get_pip(), 'install', '--target', str(destpath), '--upgrade', '-r', str(reqpath))
    else:
        run(get_pip(), 'install', '--upgrade', '-r', str(reqpath))


def run_branch_tests(conf: Dict[str, str], dir: Path, run_id: str, clone: bool = True,
                     site_id: Optional[str] = None, fake_branch_name: Optional[str] = None) -> None:
    # it would be nice if this could be run through make; however, gnu make cannot preserve
    # spaces or quotes in arguments
    args = ['tests/branch_test_wrapper.sh', sys.executable, '-m', 'pytest', '-v',
            '--upload-results', '--run-id', run_id]
    if site_id:
        args.append('--id')
        args.append(site_id)
    else:
        args.append('--id')
        args.append(get_conf(conf, 'id'))
    if fake_branch_name:
        args.append('--branch-name-override')
        args.append(fake_branch_name)
    for opt in ['maintainer_email', 'executors', 'server_url', 'key', 'max_age',
                'custom_attributes']:
        try:
            val = get_conf(conf, opt)
            args.append('--' + opt.replace('_', '-'))
            args.append(val)
        except KeyError:
            # sometimes options get added; when they do, they could prevent
            # old test cycles from working, if their configs don't contain
            # the new options
            pass

    val = get_conf(conf, 'minimal_uploads', 'false')
    if val == 'true':
        args.append('--minimal-uploads')

    cwd = (dir / 'code') if clone else Path('.')
    env = dict(os.environ)
    env['PYTHONPATH'] = str(cwd.resolve() / '.packages') \
        + ':' + str(cwd.resolve() / 'src') \
        + (':' + env['PYTHONPATH'] if 'PYTHONPATH' in env else '')
    subprocess.run(args, cwd=cwd.resolve(), env=env)


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
                    install_deps(branch, tmpp)
                with info('Testing branch "%s"' % branch):
                    run_branch_tests(conf, tmpp, run_id, clone, site_id, branch)


OLD_REPO = 'ExaWorks/psi-j-python'
NEW_REPO = 'ExaWorks/psij-python'


def patch_file(file_name: str) -> None:
    if os.path.exists(file_name + '.is_patched'):
        return

    with info('Patching %s' % file_name):
        with open(file_name) as inf:
            with open(file_name + '._new_', 'w') as outf:
                for line in inf:
                    # strip new line
                    if line.find(OLD_REPO) != -1:
                        # we're adding one space so that the line has the same length;
                        # when invoking a subprocess, bash stores the location where
                        # it's supposed to continue parsing from, so it's a good idea
                        # to to not move things around
                        line = line.rstrip('\n').replace(OLD_REPO, NEW_REPO) + ' \n'
                    outf.write(line)
        os.chmod(file_name + '._new_', os.stat(file_name).st_mode)
        os.rename(file_name + '._new_', file_name)
        Path(file_name + '.is_patched').touch()


def patch_repo() -> None:
    patch_file('testing.conf')
    patch_file('psij-ci-run')


def update_origin() -> None:
    old_url = run('git', 'config', '--get', 'remote.origin.url')
    new_url = old_url.strip().replace(OLD_REPO, NEW_REPO)
    if new_url != old_url:
        with info('Updating git url to %s' % new_url):
            run('git', 'remote', 'set-url', 'origin', new_url)


@contextmanager
def info(msg: str) -> Generator[bool, None, None]:
    print(msg + '... ', end='')
    sys.stdout.flush()
    try:
        yield True
        print('OK')
    except Exception:
        print('FAILED')
        raise


if __name__ == '__main__':
    if len(sys.argv) > 1:
        MODE = sys.argv[1]
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

    patch_repo()
    update_origin()
    run_tests(conf, site_ids, branches, clone)
