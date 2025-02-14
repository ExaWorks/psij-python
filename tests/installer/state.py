import asyncio
import functools
import json
import os
import pathlib
import types

import requests
from collections import namedtuple
from typing import List, Dict, Optional, Callable, Awaitable, Tuple, cast, Union

from .install_methods import InstallMethod
from .log import log


KEY_PATH = pathlib.Path('~/.psij/key').expanduser()


Attr = namedtuple('Attr', ['filter', 'name', 'value'])


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


class State:
    def __init__(self, conftest: types.ModuleType, ci_runner: types.ModuleType):
        self.conf = ci_runner.read_conf('testing.conf')
        self.env = conftest._discover_environment(ConfWrapper(self.conf))
        log.write('Conf: ' + str(self.conf) + '\n')
        log.write(str(self.env) + '\n')
        self.disable_install = False
        self.install_method: Optional[InstallMethod] = None
        self.active_panel: Optional[int] = None
        self.scheduler: Optional[str] = None
        self.attrs = self._parse_attributes()
        self.run_test_job = True
        self.has_key = KEY_PATH.exists()
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
        with open('testing.conf', 'r') as old:
            with open('testing.conf.new', 'w') as new:
                for line in old:
                    sline = line.strip()
                    if sline == '' or sline.startswith('#'):
                        new.write(line)
                    elif sline.startswith(name) and sline[nlen] in [' ', '\t', '=']:
                        new.write(f'{name} = {value}\n')
                    else:
                        new.write(line)
        os.rename('testing.conf.new', 'testing.conf')

    def update_conf(self, name: str, value: str) -> None:
        if name == 'id':
            self._write_conf_value('id', f'"{value}"')
        else:
            self._write_conf_value(name, value)

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

    def get_executor(self) -> Tuple[str, str]:
        if self.env['has_slurm']:
            return ('Slurm', 'slurm')
        if self.env['has_pbs']:
            return ('PBS', 'pbs')
        if self.env['has_lsf']:
            return ('LSF', 'lsf')
        if self.env['has_cobalt']:
            return ('Cobalt', 'cobalt')

        return ('None', 'none')
