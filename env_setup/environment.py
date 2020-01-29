# Copyright 2020 The Pigweed Authors
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may not
# use this file except in compliance with the License. You may obtain a copy of
# the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations under
# the License.
"""Stores the environment changes necessary for Pigweed."""

import contextlib
import os
import re


class BadNameType(TypeError):
    pass


class BadValueType(TypeError):
    pass


class EmptyValue(ValueError):
    pass


class NewlineInValue(TypeError):
    pass


class BadVariableName(ValueError):
    pass


class UnexpectedAction(ValueError):
    pass


class _Action(object):  # pylint: disable=useless-object-inheritance
    # pylint: disable=redefined-builtin,too-few-public-methods
    def __init__(self, name, value, *args, **kwargs):
        super(_Action, self).__init__(*args, **kwargs)
        self.name = name
        self.value = value

        self._check()

    def _check(self):
        if not isinstance(self.name, str):
            raise BadNameType('variable name {!r} not of type str'.format(
                self.name))
        if not isinstance(self.value, str):
            raise BadValueType('{!r} value {!r} not of type str'.format(
                self.name, self.value))

        # Empty strings as environment variable values have different behavior
        # on different operating systems. Just don't allow them.
        if self.value == '':
            raise EmptyValue('{!r} value {!r} is the empty string'.format(
                self.name, self.value))

        # Many tools have issues with newlines in environment variable values.
        # Just don't allow them.
        if '\n' in self.value:
            raise NewlineInValue('{!r} value {!r} contains a newline'.format(
                self.name, self.value))

        if not re.match(r'^[A-Z_][A-Z0-9_]*$', self.name, re.IGNORECASE):
            raise BadVariableName('bad variable name {!r}'.format(self.name))


class _Set(_Action):
    def write(self, outs, windows=(os.name == 'nt')):
        if windows:
            outs.write('set {name}={value}\n'.format(**vars(self)))
        else:
            outs.write(
                '{name}="{value}"\nexport {name}\n'.format(**vars(self)))

    def apply(self, env):
        env[self.name] = self.value


class _Clear(_Action):
    def __init__(self, *args, **kwargs):
        kwargs['value'] = 'unused non-empty string to make _check() simpler'
        super(_Clear, self).__init__(*args, **kwargs)

    def write(self, outs, windows=(os.name == 'nt')):
        if windows:
            outs.write('set {name}=\n'.format(**vars(self)))
        else:
            outs.write('unset {name}\n'.format(**vars(self)))

    def apply(self, env):
        if self.name in env:
            del env[self.name]


class _Prepend(_Action):
    def __init__(self, name, value, join, *args, **kwargs):
        super(_Prepend, self).__init__(name, value, *args, **kwargs)
        self._join = join

    def write(self, outs, windows=(os.name == 'nt')):
        if windows:
            outs.write(
                'set {name}={value}{pathsep}%{name}%\n'.format(**vars(self)))
        else:
            outs.write('{name}="{value}"\nexport {name}\n'.format(
                name=self.name, value=self._join(self.value, '$' + self.name)))

    def apply(self, env):
        env[self.name] = self._join(self.value, env.get(self.name, ''))


class _Append(_Action):
    def __init__(self, name, value, join, *args, **kwargs):
        super(_Append, self).__init__(name, value, *args, **kwargs)
        self._join = join

    def write(self, outs, windows=(os.name == 'nt')):
        if windows:
            outs.write(
                'set {name}=%{name}%{pathsep}{value}\n'.format(**vars(self)))
        else:
            outs.write('{name}="{value}"\nexport {name}\n'.format(
                name=self.name, value=self._join('$' + self.name, self.value)))

    def apply(self, env):
        env[self.name] = self._join(env.get(self.name, ''), self.value)


class BadEchoValue(ValueError):
    pass


class _Echo(_Action):
    def __init__(self, value, *args, **kwargs):
        name = 'unused_non_empty_string_to_make_check_simpler'
        # These values act funny on Windows.
        if value.lower() in ('off', 'on'):
            raise BadEchoValue(value)
        super(_Echo, self).__init__(name, value, *args, **kwargs)

    def write(self, outs, windows=(os.name == 'nt')):
        # POSIX shells parse arguments and pass to echo, but Windows seems to
        # pass the command line as is without parsing, so quoting is wrong.
        if windows:
            outs.write('echo {}\n'.format(self.value))
        else:
            # TODO(mohrr) use shlex.quote().
            outs.write('if [ -z "${PW_ENVSETUP_QUIET:-}" ]; then\n')
            outs.write('  echo "{}"\n'.format(self.value))
            outs.write('fi\n')

    def apply(self, env):  # pylint: disable=no-self-use
        del env  # Unused.


# TODO(mohrr) remove disable=useless-object-inheritance once in Python 3.
# pylint: disable=useless-object-inheritance
class Environment(object):
    """Stores the environment changes necessary for Pigweed.

    These changes can be accessed by writing them to a file for bash-like
    shells to source or by using this as a context manager.
    """
    def __init__(self, *args, **kwargs):
        pathsep = kwargs.pop('pathsep', os.pathsep)
        windows = kwargs.pop('windows', os.name == 'nt')
        super(Environment, self).__init__(*args, **kwargs)
        self._actions = []
        self._pathsep = pathsep
        self._windows = windows

    def _join(self, *args):
        if len(args) == 1 and isinstance(args[0], (list, tuple)):
            args = args[0]
        return self._pathsep.join(args)

    def set(self, name, value):
        self._actions.append(_Set(name, value))

    def clear(self, name):
        self._actions.append(_Clear(name))

    def append(self, name, value):
        """Add a value to the end of a variable. Rarely used, see prepend()."""

        if self.get(name, None):
            self._actions.append(_Append(name, value, self._join))
        else:
            self._actions.append(_Set(name, value))

    def prepend(self, name, value):
        """Add a value to the beginning of a variable."""

        if self.get(name, None):
            self._actions.append(_Prepend(name, value, self._join))
        else:
            self._actions.append(_Set(name, value))

    def echo(self, value):
        self._actions.append(_Echo(value))

    def write(self, outs):
        """Writes a shell init script to outs."""
        if self._windows:
            outs.write('@echo off\n')

        for action in self._actions:
            action.write(outs, windows=self._windows)

        if not self._windows:
            outs.write(
                '# This should detect bash and zsh, which have a hash \n'
                '# command that must be called to get it to forget past \n'
                '# commands. Without forgetting past commands the $PATH \n'
                '# changes we made may not be respected.\n'
                'if [ -n "${BASH:-}" -o -n "${ZSH_VERSION:-}" ] ; then\n'
                '    hash -r\n'
                'fi\n')

        outs.write('if [ -z "${PW_ENVSETUP_QUIET:-}" ]; then\n'
                   '  pw --loglevel info doctor\n'
                   'else\n'
                   '  pw --loglevel warn doctor\n'
                   'fi\n')

    @contextlib.contextmanager
    def __call__(self, export=True):
        """Set environment as if this was written to a file and sourced.

        Within this context os.environ is updated with the environment
        defined by this object. If export is False, os.environ is not updated,
        but in both cases the updated environment is yielded.

        On exit, previous environment is restored. See contextlib documentation
        for details on how this function is structured.

        Args:
          export(bool): modify the environment of the running process (and
            thus, its subprocesses)

        Yields the new environment object.
        """
        try:
            if export:
                orig_env = os.environ.copy()
                env = os.environ
            else:
                env = os.environ.copy()

            for action in self._actions:
                action.apply(env)

            yield env

        finally:
            if export:
                for action in self._actions:
                    if action.name in orig_env:
                        os.environ[action.name] = orig_env[action.name]
                    else:
                        os.environ.pop(action.name, None)

    def get(self, key, default=None):
        """Get the value of a variable within context of this object."""
        with self(export=False) as env:
            return env.get(key, default)

    def __getitem__(self, key):
        """Get the value of a variable within context of this object."""
        with self(export=False) as env:
            return env[key]