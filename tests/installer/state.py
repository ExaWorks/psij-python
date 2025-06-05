import asyncio
import functools
import json
import os
import pathlib
import shutil
import types

import requests
from collections import namedtuple
from typing import List, Dict, Optional, Callable, Awaitable, Tuple, cast, Union

from .install_methods import InstallMethod
from .log import log


KEY_PATH = pathlib.Path('~/.psij/key').expanduser()


Attr = namedtuple('Attr', ['filter', 'name', 'value'])


_EXECUTOR_LABELS = {'slurm': 'Slurm', 'pbs': 'PBS', 'cobalt': 'Cobalt', 'lsf': 'LSF',
                    'none': 'None'}


async def _to_thread(func, /, *args, **kwargs):  # type: ignore
    loop = asyncio.get_running_loop()
    func_call = functools.partial(func, *args, **kwargs)
    return await loop.run_in_executor(None, func_call)


class _Options:
    def __init__(self) -> None:
        self.custom_attributes = None


class ConfWrapper:
    def __init__(self, dict: Dict[str, Union[str, int, bool, None]]):
        self.dict = dict
        self.option = _Options()
        dict['run_id'] = 'x'
        dict['save_results'] = False
        dict['upload_results'] = True
        dict['branch_name_override'] = None

    def getoption(self, name: str) -> Union[str, int, bool, None]:
        return self.dict[name]


class Exec:
    def __init__(self, pair: str) -> None:
        array = pair.split(':')
        assert len(array) > 0 and len(array) <= 3
        self.name = array[0]
        self.launcher = ''
        self.url = ''
        if len(array) > 1:
            self.launcher = array[1]
        if len(array) > 2:
            self.url = array[2]

    def __str__(self) -> str:
        if self.launcher == '':
            return self.name
        else:
            return f'{self.name}:{self.launcher}'

    def __repr__(self) -> str:
        return str(self)


class State:
    def __init__(self, conftest: types.ModuleType, ci_runner: types.ModuleType):
        self.conf = ci_runner.read_conf('testing.conf')
        self.env = conftest._discover_environment(ConfWrapper(self.conf))
        self.translate_launcher = conftest._translate_launcher
        log.write('Conf: ' + str(self.conf) + '\n')
        log.write(str(self.env) + '\n')
        self.disable_install = False
        self.install_method: Optional[InstallMethod] = None
        self.active_panel: Optional[int] = None
        self.scheduler: Optional[str] = None
        self.attrs = self._parse_attributes()
        self.run_test_job = True
        self.has_key = KEY_PATH.exists()
        self.conf_backed_up = False
        self.execs, self.batch_exec = self._parse_executors()
        log.write(f'execs: {self.execs}, bexec: {self.batch_exec}\n')
        if self.has_key:
            with open(KEY_PATH, 'r') as f:
                self.key = f.read().strip()
        self.key_is_valid: Optional[bool] = None
        log.write(f'has key: {self.has_key}\n')

    def _parse_attributes(self) -> List[Attr]:
        attrspec = json.loads('[' + self.conf['custom_attributes'] + ']')
        attrs = []
        for filter_entry in attrspec:
            filter = filter_entry['filter']
            for name, value in filter_entry['value'].items():
                ns = name.split('.', 2)
                if len(ns) != 2:
                    continue
                attrs.append(Attr(filter, ns[1], value))
        return attrs

    def _write_conf_value(self, name: str, value: str) -> None:
        self.conf[name] = value
        nlen = len(name)
        found = False
        with open('testing.conf', 'r') as old:
            with open('testing.conf.new', 'w') as new:
                for line in old:
                    sline = line.strip()
                    if sline == '' or sline.startswith('#'):
                        new.write(line)
                    elif sline.startswith(name) and sline[nlen] in [' ', '\t', '=']:
                        new.write(f'{name} = {value}\n')
                        found = True
                    else:
                        new.write(line)
                if not found:
                    new.write(line)
        os.rename('testing.conf.new', 'testing.conf')

    def update_conf(self, name: str, value: str) -> None:
        if name == 'id':
            self._write_conf_value('id', f'"{value}"')
        else:
            self._write_conf_value(name, value)

    def backup_conf(self) -> None:
        shutil.copyfile('testing.conf', 'testing.conf.bk')
        self.conf_backed_up = True

    async def request(self, query: str, data: Dict[str, object], title: str,
                      error_cb: Callable[[str, str], Awaitable[Optional[Dict[str, object]]]]) \
            -> Optional[Dict[str, object]]:
        baseUrl = self.conf['server_url']
        response = await _to_thread(requests.post, baseUrl + query, data=data)  # type: ignore
        return await self._check_error(response, title, error_cb)

    async def _check_error(self, response: requests.Response, title: str,
                           error_cb: Callable[[str, str], Awaitable[Optional[Dict[str, object]]]]) \
            -> Optional[Dict[str, object]]:
        log.write(f'Response: {response.text}\n')
        if response.status_code != 200:
            msg = self._extract_response_message(response.text)
            if msg:
                error = f'Server responded with an error: {msg}'
            else:
                error = response.text
        else:
            data = response.json()
            if 'success' in data:
                return cast(Dict[str, object], data)
            else:
                error = 'Unknown error'
        log.write(f'Error: {error}\n')
        if error is not None:
            await error_cb(title + ' failed', error)
        return None

    def _extract_response_message(self, html: str) -> Optional[str]:
        # standard cherrypy error page
        ix = html.find('<p>')
        if ix != -1:
            return html[ix + 3:html.find('</p>', ix)]
        else:
            return None

    def set_custom_attrs(self, attrs: List[Attr]) -> None:
        self.attrs = attrs
        self._write_custom_attrs(attrs)

    def _write_custom_attrs(self, attrs: List[Attr]) -> None:
        # this one is weird to set, so we need a custom solution
        sched = self.scheduler
        name = 'custom_attributes'
        nlen = len(name)
        continued = False
        purge = False
        with open('testing.conf', 'r') as old, open('testing.conf.new', 'w') as new:
            for line in old:
                sline = line.strip()
                if sline == '' or sline.startswith('#'):
                    new.write(line)
                elif sline.startswith(name) and sline[nlen] in [' ', '\t', '=', '[']:
                    if not purge:
                        for attr in attrs:
                            if attr.filter == '.*' or attr.filter == '':
                                new.write(f'custom_attributes = '
                                          f'"{sched}.{attr.name}": "{attr.value}"\n')
                            else:
                                new.write(f'custom_attributes[{attr.filter}] = '
                                          f'"{sched}.{attr.name}": "{attr.value}"\n')
                        purge = True
                    if sline.endswith('\\'):
                        continued = True
                elif continued:
                    # just consume the line
                    continued = sline.endswith('\\')
                else:
                    new.write(line)
        os.rename('testing.conf.new', 'testing.conf')

    def _executor_label(self, name: Optional[str]) -> Optional[str]:
        if name in _EXECUTOR_LABELS:
            return _EXECUTOR_LABELS[name]
        else:
            return name

    def get_auto_executor(self) -> Optional[str]:
        if self.env['has_slurm']:
            return 'slurm'
        if self.env['has_pbs']:
            return 'pbs'
        if self.env['has_lsf']:
            return 'lsf'
        if self.env['has_cobalt']:
            return 'cobalt'

        return 'none'

    def get_batch_executor(self) -> Tuple[Optional[str], Optional[str]]:
        return self._executor_label(self.batch_exec), self.batch_exec

    def _parse_executors(self) -> Tuple[List[Exec], Optional[str]]:
        conf_exec = self.conf.get('executors', '')
        execs = []
        for exec in conf_exec.split(','):
            exec = exec.strip()
            if exec != '':
                execs.append(Exec(exec))
        if len(execs) == 0:
            execs = [Exec('auto')]
        batch = None
        for exec in execs:
            if exec.name == 'auto' or exec.name == 'auto_q':
                batch = self.get_auto_executor()
            elif exec.name not in ['local', 'batch-test']:
                batch = exec.name

        return execs, batch

    def _executors_str(self) -> str:
        return ', '.join([str(x) for x in self.execs])

    def set_batch_executor(self, scheduler: str) -> None:
        auto_exec = self.get_auto_executor()
        if auto_exec == scheduler or scheduler == 'none':
            self.execs = [Exec('auto')]
        elif scheduler == 'local' and auto_exec == 'none':
            self.execs = [Exec('auto')]
        else:
            existing = None
            for exec in self.execs:
                if exec.name not in ['auto', 'auto_q', 'local', 'batch-test']:
                    exec.name = scheduler
                    exec.launcher = 'auto_l'
            if not existing:
                self.execs.append(Exec(scheduler))

        log.write(f'set_be({scheduler}): execs: {self.execs}, str: {self._executors_str()}\n')

        self._write_conf_value('executors', self._executors_str())
