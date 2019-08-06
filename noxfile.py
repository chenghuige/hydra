import os

import nox

BASE = os.path.abspath(os.path.dirname(__file__))

DEFAULT_PYTHON_VERSIONS = [
    '2.7',
    '3.5',
    '3.6',
    '3.7',
]

PYTHON_VERSIONS = os.environ.get("NOX_PYTHON_VERSIONS", ','.join(DEFAULT_PYTHON_VERSIONS)).split(',')

PLUGINS_INSTALL_COMMANDS = (
    ('pip', 'install', '.'),
    ('pip', 'install', '-e', '.'),
)


def plugin_names():
    return sorted(os.listdir(os.path.join(BASE, 'plugins')))


def get_all_plugins():
    return [(plugin, 'hydra_plugins.' + plugin) for plugin in plugin_names()]


@nox.session(python=PYTHON_VERSIONS)
def test_core(session):
    session.install('--upgrade', 'setuptools', 'pip')
    session.install('pytest')
    session.chdir(BASE)
    session.run('pip', 'install', '.', silent=True)
    session.run('pytest', silent=True)


def get_python_versions(session, setup_py):
    out = session.run('python', setup_py, '--classifiers', silent=True).split('\n')
    pythons = filter(lambda line: 'Programming Language :: Python' in line, out)
    return [p[len('Programming Language :: Python :: '):] for p in pythons]


@nox.session(python=PYTHON_VERSIONS)
@nox.parametrize('install_cmd', PLUGINS_INSTALL_COMMANDS, ids=[' '.join(x) for x in PLUGINS_INSTALL_COMMANDS])
@nox.parametrize('plugin_name', plugin_names(), ids=plugin_names())
def test_plugin(session, plugin_name, install_cmd):
    session.install('--upgrade', 'setuptools', 'pip')

    # Verify this plugin supports the python we are testing on, skip otherwise
    plugin_python_versions = get_python_versions(session, os.path.join(BASE, "plugins", plugin_name, 'setup.py'))
    if session.python not in plugin_python_versions:
        session.skip(
            "Not testing {} on Python {}, supports [{}]".format(
                plugin_name,
                session.python,
                ','.join(plugin_python_versions)
            )
        )
    # clean install hydra
    session.chdir(BASE)
    session.run('python', 'setup.py', 'clean', silent=True)
    session.run('pip', 'install', '.', silent=True)

    all_plugins = get_all_plugins()
    # Install all plugins in session
    for plugin in all_plugins:
        cmd = list(install_cmd) + [os.path.join('plugins', plugin[0])]
        session.run(*cmd, silent=True)

    # Test that we can import Hydra
    session.run('python', '-c', 'from hydra import Hydra', silent=True)
    # Test that we can import all installed plugins
    for plugin in all_plugins:
        session.run('python', '-c', 'import {}'.format(plugin[1]))

    # Run tests for current plugin
    session.chdir(os.path.join(BASE, "plugins", plugin_name))
    session.install('pytest')
    session.run('pytest', silent=True)


@nox.session
def coverage(session):
    session.install('--upgrade', 'setuptools', 'pip')
    """Coverage analysis."""
    session.install('coverage', 'pytest')
    session.run('python', 'setup.py', 'clean', silent=True)
    all_plugins = get_all_plugins()

    session.run('pip', 'install', '-e', '.', silent=True)
    # Install all plugins in session
    for plugin in all_plugins:
        session.run('pip', 'install', '-e', os.path.join('plugins', plugin[0]), silent=True)

    session.run("coverage", "erase")
    session.run('coverage', 'run', '--append', '-m', 'pytest', silent=True)
    for plugin in plugin_names():
        session.run('coverage', 'run', '--append', '-m', 'pytest', os.path.join('plugins', plugin), silent=True)

    # Increase the fail_under as coverage improves
    session.run('coverage', 'report', '--fail-under=80')

    session.run('coverage', 'erase')