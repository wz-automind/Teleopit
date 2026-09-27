import json
import os
import subprocess
import sys
import tempfile
import venv
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def run(name, *args, **env):
    with tempfile.TemporaryDirectory() as cwd:
        return subprocess.run(['bash', str(ROOT / 'scripts' / name), *args], cwd=cwd,
                              env={**os.environ, 'TELEOPIT_PYTHON': sys.executable,
                                   'TELEOPIT_DIR': '/nonexistent/old-project',
                                   'ENABLE_G1_REAL': '', 'ENABLE_RH56E2_WRITES': '', **env},
                              capture_output=True, text=True, timeout=30)


def test_sim_launcher_uses_fork_and_preserves_arguments():
    result = run('run/run_sim_rh56e2.sh', '--cfg', 'job', 'num_steps=7', 'viewers=none')
    assert result.returncode == 0, result.stderr
    assert 'num_steps: 7' in result.stdout
    assert 'g1_29dof_rh56e2.xml' in result.stdout
    assert 'teleopit-rh56e2-repro' not in result.stdout


def test_real_launcher_requires_g1_interlock_and_defaults_to_hand_read_only():
    denied = run('run/run_sim2real_rh56e2.sh', '--cfg', 'job')
    assert denied.returncode != 0
    assert 'ENABLE_G1_REAL' in denied.stderr
    result = run('run/run_sim2real_rh56e2.sh', '--cfg', 'job',
                 ENABLE_G1_REAL='YES', LEFT_HAND_IP='192.0.2.1', RIGHT_HAND_IP='192.0.2.2', NETWORK_INTERFACE='testnic')
    assert result.returncode == 0, result.stderr
    assert 'write_enabled: false' in result.stdout
    assert 'network_interface: testnic' in result.stdout


def test_unitree_wrapper_preserves_advertise_address():
    result = run('run/run_unitree_g1_rh56e2.sh', '--cfg', 'job', ENABLE_G1_REAL='YES', PICO_ADVERTISE_IP='192.0.2.3')
    assert result.returncode == 0, result.stderr
    assert 'bridge_advertise_ip: 192.0.2.3' in result.stdout
    assert 'write_enabled: false' in result.stdout


@pytest.mark.parametrize('launcher', ['run_sim2real_rh56e2.sh', 'run_unitree_g1_rh56e2.sh'])
@pytest.mark.parametrize('address,override,expected', [
    ('192.0.2.3', None, '192.0.2.3'),
    ('', None, 'null'),
    ('192.0.2.3', '192.0.2.4', '192.0.2.4'),
])
def test_launchers_resolve_advertise_address(launcher, address, override, expected):
    args = ['--cfg', 'job']
    if override:
        args.insert(0, 'input.bridge_advertise_ip=' + override)
    result = run('run/' + launcher, *args, ENABLE_G1_REAL='YES',
                 LEFT_HAND_IP='192.0.2.1', RIGHT_HAND_IP='192.0.2.2',
                 NETWORK_INTERFACE='testnic', PICO_ADVERTISE_IP=address)
    assert result.returncode == 0, result.stderr
    assert 'bridge_advertise_ip: ' + expected in result.stdout
    assert 'write_enabled: false' in result.stdout


def installer_commands(tmp_path, *, fail_bootstrap=False):
    # Substitute only the external Python/pip boundary: the real Bash installer runs.
    wheelhouse = tmp_path / 'wheelhouse'
    wheelhouse.mkdir()
    (wheelhouse / 'rh56e2_sdk-0.1.0-py3-none-any.whl').touch()
    log = tmp_path / 'calls.jsonl'
    interpreter = tmp_path / 'python-spy'
    interpreter.write_text(
        '#!' + sys.executable + '\n'
        'import json, sys\n'
        f'with open({str(log)!r}, "a") as stream: stream.write(json.dumps(sys.argv[1:]) + "\\n")\n'
        f'if {fail_bootstrap!r} and "setuptools>=61.0" in sys.argv: sys.exit(17)\n'
    )
    interpreter.chmod(0o755)
    result = run('setup/install_rh56e2.sh', '--wheelhouse', str(wheelhouse),
                 TELEOPIT_PYTHON=str(interpreter))
    calls = [json.loads(line) for line in log.read_text().splitlines()]
    return result, [args for args in calls if args[:3] == ['-m', 'pip', 'install']]


def test_offline_installer_bootstraps_and_replaces_only_sdk(tmp_path):
    result, installs = installer_commands(tmp_path)
    assert result.returncode == 0, result.stderr
    assert 'setuptools>=61.0' in installs[0]
    assert 'wheel' in installs[0]
    sdk_install = next(args for args in installs if any(arg.endswith('.whl') for arg in args))
    assert '--force-reinstall' in sdk_install
    assert '--no-deps' in sdk_install
    assert not any(arg.startswith(('somehand', 'pico-bridge')) for arg in sdk_install)
    assert any('somehand==0.3.0' in args and 'pico-bridge==0.2.1' in args for args in installs)
    assert '-e' in installs[-1]
    for args in installs:
        assert '--no-index' in args
        assert '--find-links' in args


def test_offline_installer_stops_on_missing_build_tools(tmp_path):
    result, installs = installer_commands(tmp_path, fail_bootstrap=True)
    assert result.returncode == 17
    assert len(installs) == 1


def test_invalid_sim_option_is_not_ignored():
    result = run('run/run_sim_rh56e2.sh', '--invalid-option')
    assert result.returncode != 0


def test_missing_offline_sdk_wheel_names_missing_package():
    with tempfile.TemporaryDirectory() as wheelhouse:
        result = run('setup/install_rh56e2.sh', '--wheelhouse', wheelhouse)
    assert result.returncode != 0
    assert 'rh56e2_sdk-0.1.0-py3-none-any.whl' in result.stderr


def test_clean_offline_sdk_install_and_missing_build_dependency(tmp_path):
    wheelhouse = ROOT / 'dist/wheelhouse'
    assert (wheelhouse / 'rh56e2_sdk-0.1.0-py3-none-any.whl').is_file(), 'Place the SDK wheel in dist/wheelhouse before distribution tests'
    venv.EnvBuilder(with_pip=True).create(tmp_path / 'env')
    python = str(tmp_path / 'env/bin/python')
    result = subprocess.run([python, '-m', 'pip', 'install', '--no-index', '--find-links', str(wheelhouse), 'rh56e2-sdk==0.1.0'], cwd=tmp_path, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    result = subprocess.run([python, '-c', "from rh56e2_sdk import RH56E2Hand; assert not RH56E2Hand('test').write_enabled"], cwd=tmp_path, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    result = run('setup/install_rh56e2.sh', '--wheelhouse', str(wheelhouse), TELEOPIT_PYTHON=python)
    assert result.returncode != 0
    assert 'wheel' in result.stderr or 'setuptools' in result.stderr
