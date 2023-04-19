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
from typing import Dict, TextIO, List, Optional, Generator, Callable

import requests


STABLE_BRANCHES = ['main']
FAKE_BRANCHES = ['main', 'feature_1', 'feature_x']
GITHUB_API_ROOT = 'https://api.github.com'
MODE = 'plain'
TARGET_PATCH_LEVEL = 2


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
# Patching routines


def write_patch_level(level: int) -> None:
    with open('.ci.patchlevel', 'w') as f:
        f.write(str(level))


def current_patch_level() -> int:
    try:
        with open('.ci.patchlevel') as f:
            return int(f.read().strip())
    except OSError:
        for fn in ['testing.conf', 'psij-ci-run']:
            if not Path(fn + '.is_patched').exists():
                return 0
        write_patch_level(1)
        return 1


def deploy_patch(level: int) -> None:
    if level == 1:
        l1_patch_repo()
        l1_update_origin()
    elif level == 2:
        l2_remove_patch_flag_files()
        l2_update_upload_url()
    else:
        raise Exception('Nothing to do for patch level %s' % level)
    write_patch_level(level)


def try_patch(level: int) -> None:
    if level <= current_patch_level():
        return
    else:
        deploy_patch(level)


def deploy_patches() -> None:
    for level in range(1, TARGET_PATCH_LEVEL + 1):
        try_patch(level)


def line_patcher(file_name: str, matcher: Callable[[str], bool],
                 mutator: Callable[[str], str]) -> None:
    with info('Patching %s' % file_name):
        with open(file_name) as inf:
            with open(file_name + '._new_', 'w') as outf:
                for line in inf:
                    # strip new line
                    if matcher(line):
                        # we're adding one space so that the line has the same length;
                        # when invoking a subprocess, bash stores the location where
                        # it's supposed to continue parsing from, so it's a good idea
                        # to to not move things around
                        line = mutator(line)
                    outf.write(line)
        os.chmod(file_name + '._new_', os.stat(file_name).st_mode)
        os.rename(file_name + '._new_', file_name)


# Patch 1
# Updates repositories in testing.conf and psij-ci-run. It also
# updates the git origin to point to the new repo. This is done to
# account for the fact that we renamed the repo from psi-j-python
# to psij-python.

OLD_REPO = 'ExaWorks/psi-j-python'
NEW_REPO = 'ExaWorks/psij-python'


def l1_patch_file(file_name: str) -> None:
    if os.path.exists(file_name + '.is_patched'):
        return
    line_patcher(file_name,
                 lambda line: line.find(OLD_REPO) != -1,
                 # The extra space before the newline is to not shift the content
                 # of psij-ci-run that follows this line. Bash continues reading
                 # the file after a command completes, but, if the content has
                 # shifted, it might end up reading a partial line.
                 lambda line: line.rstrip('\n').replace(OLD_REPO, NEW_REPO) + ' \n')


def l1_patch_repo() -> None:
    l1_patch_file('testing.conf')
    l1_patch_file('psij-ci-run')


def l1_update_origin() -> None:
    old_url = run('git', 'config', '--get', 'remote.origin.url')
    new_url = old_url.strip().replace(OLD_REPO, NEW_REPO)
    if new_url != old_url:
        with info('Updating git url to %s' % new_url):
            run('git', 'remote', 'set-url', 'origin', new_url)


# Patch 2
# Updates the test upload url from either testing.exaworks.org or
# psij.testing.exaworks.org to testing.psij.io

OLD_UPLOAD_URLS = ['https://psij.testing.exaworks.org', 'https://testing.exaworks.org']
NEW_UPLOAD_URL = 'https://testing.psij.io'


def l2_remove_patch_flag_files() -> None:
    # we're using a single patch level file now
    for fn in ['testing.conf', 'psij-ci-run']:
        f = Path(fn + '.is_patched')
        if f.exists():
            f.unlink()


def l2_update_upload_url() -> None:
    for old_url in OLD_UPLOAD_URLS:
        line_patcher('testing.conf',
                     lambda line: line.find('server_url') != -1
                                  and line.find(old_url) != -1,  # noqa: E127
                     lambda line: line.rstrip('\n').replace(old_url, NEW_UPLOAD_URL) + '\n')

# End of patches


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

    deploy_patches()
    run_tests(conf, site_ids, branches, clone)
