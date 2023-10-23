#
# Auto generate the following:
#   - A .rst from api.tree
#   - executors.rst
#   - launchers.rst
#   - index.rst (index of classes, global functions)
import importlib
import inspect
import sys
from io import TextIOBase
from types import ModuleType
from typing import List, Type, Set, Tuple

import psij

HEADING_CHARS = ['-', '^', '~', '"', '*']

seen_names = set()


def is_module(name: str) -> bool:
    return name in sys.modules


def split_class_name(name: str) -> Tuple[str, str]:
    dot_ix = name.rindex('.')

    return name[0:dot_ix], name[dot_ix + 1:]


def get_object(name: str) -> object:
    if '.' not in name:
        return None
    module_name, class_name = split_class_name(name)

    if not is_module(module_name):
        return None

    try:
        return getattr(sys.modules[module_name], class_name)
    except AttributeError:
        return None


def is_class(name: str) -> bool:
    return inspect.isclass(get_object(name))


def is_function(name: str) -> bool:
    return inspect.isfunction(get_object(name))


def get_module_classes(name: str) -> List[str]:
    try:
        classes = set()
        mod = importlib.import_module(name)
        _dir(sys.modules[name], set(), classes, classes)
        #return [cls.__name__ for cls in classes if cls.__module__ == name and ]
        return [cls.__name__ for cls in classes if cls.__module__ == name]
    except Exception as ex:
        print(ex)
        return []


def write_heading(out: TextIOBase, name: str, level: int) -> None:
    out.write(name)
    out.write('\n')
    out.write(HEADING_CHARS[level] * len(name))
    out.write('\n\n')


def generate_tree() -> None:
    with open('api.tree', 'r') as f:
        with open('.generated/tree.rst', 'w') as out:
            for line in f:
                line = line.rstrip()
                name = line.lstrip()
                # 4 spaces per indent level
                indent_level = (len(line) - len(name)) // 4
                if name.startswith('#'):
                    continue
                if name.startswith('~'):
                    nofqn = True
                    name = name[1:]
                else:
                    nofqn = False

                if name == '':
                    out.write('\n')
                elif name.startswith('"'):
                    out.write(name[1:-1])
                    out.write('\n')
                elif name.startswith('..'):
                    out.write(name)
                    out.write('\n')
                elif name == '+executors':
                    generate_executors(out)
                elif name == '+launchers':
                    generate_launchers(out)
                elif name.endswith('.rst'):
                    out.write('.. toctree::\n    %s\n\n' % name[:-4])
                elif is_module(name):
                    print('Module: %s' % name)
                    write_heading(out, name + ' module', indent_level)
                    out.write('.. automodule:: %s\n    :members:\n\n' % name)
                    print('%s -> %s' % (name, get_module_classes(name)))
                    seen_names.update(get_module_classes(name))
                elif is_function(name):
                    print('Function: %s' % name)
                    mod_name, fn_name = split_class_name(name)
                    write_heading(out, fn_name if nofqn else name, indent_level)
                    out.write('.. automodule:: %s\n    :members: %s\n' % (mod_name, fn_name))
                    if name in seen_names or cls.__name__ in seen_names:
                        out.write('    :noindex:\n')
                    out.write('\n')
                    seen_names.add(name)
                elif is_class(name):
                    print('Class: %s' % name)
                    cls = get_object(name)
                    write_heading(out, cls.__name__, indent_level)
                    out.write('.. autoclass:: %s\n    :members:\n' % name)
                    if name in seen_names or cls.__name__ in seen_names:
                        out.write('    :noindex:\n')
                    out.write('\n')
                    seen_names.add(name)
                else:
                    print('Heading: %s' % name)
                    write_heading(out, name, indent_level)


def generate_executors(out: TextIOBase) -> None:
    from psij import JobExecutor

    for name in sorted(JobExecutor.get_executor_names()):
        versions = JobExecutor._executors[name.lower()]
        assert len(versions) == 1
        qname = versions[0].desc.cls
        write_heading(out, versions[0].desc.nice_name, 1)
        out.write('.. autoclass:: %s\n\n' % qname)
        seen_names.add(qname)

        module_name, class_name = split_class_name(qname)
        classes = get_module_classes(module_name)
        for cls in classes:
            if cls != class_name:
                write_heading(out, cls, 2)
                qname = module_name + '.' + cls
                out.write('.. autoclass:: %s\n\n' % qname)
                seen_names.add(cls)


def generate_launchers(out: TextIOBase) -> None:
    from psij import Launcher

    for name in sorted(Launcher.get_launcher_names()):
        versions = Launcher._launchers[name.lower()]
        assert len(versions) == 1
        qname = versions[0].desc.cls
        write_heading(out, versions[0].desc.nice_name, 1)
        out.write('.. autoclass:: %s\n\n' % qname)
        seen_names.add(qname)


def _dir(obj: object, modules: Set[object], classes: Set[object], functions: Set[object]):
    if inspect.ismodule(obj):
        if obj.__name__.startswith('psij') and obj not in modules:
            modules.add(obj)
            for child in dir(obj):
                _dir(getattr(obj, child), modules, classes, functions)
    elif inspect.isclass(obj):
        if obj not in classes:
            if not obj.__name__.startswith('_') and obj.__module__.startswith('psij.'):
                classes.add(obj)
    elif inspect.isfunction(obj):
        if obj not in functions:
            if not obj.__name__.startswith('_') and obj.__module__.startswith('psij.'):
                functions.add(obj)


def _sorted_names(set: Set[object]) -> List[Tuple[str, object]]:
    names = []
    map = {}
    for obj in set:
        name = obj.__name__
        map[name] = obj
        names.append(name)

    return [(name, map[name]) for name in sorted(names)]


def generate_index() -> None:
    modules = set()
    classes = set()
    functions = set()

    _dir(psij, modules, classes, functions)
    with open('.generated/index.rst', 'w') as out:
        write_heading(out, 'Index', 0)
        write_heading(out, 'Classes', 1)
        for name, val in _sorted_names(classes):
            write_heading(out, name, 2)
            qname = val.__module__ + '.' + name
            out.write('.. autoclass:: %s\n' % qname)
            if qname in seen_names or name in seen_names:
                out.write('    :noindex:\n')
            out.write('\n\n')

        write_heading(out, 'Functions', 1)
        for name, val in _sorted_names(functions):
            write_heading(out, name, 2)
            qname = val.__module__ + '.' + name
            out.write('.. autofunction:: %s\n    :noindex:\n\n' % qname)


if __name__ == '__main__':
    generate_tree()
    generate_index()
