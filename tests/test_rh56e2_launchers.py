import os
import subprocess
import sys
import tempfile
import venv
from pathlib import Path

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


def test_invalid_sim_option_is_not_ignored():
    result = run('run/run_sim_rh56e2.sh', '--invalid-option')
    assert result.returncode != 0


def test_missing_offline_sdk_wheel_names_missing_package():
    with tempfile.TemporaryDirectory() as wheelhouse:
        result = run('setup/install_rh56e2.sh', '--wheelhouse', wheelhouse)
    assert result.returncode != 0
    assert 'rh56e2_sdk-0.1.0-py3-none-any.whl' in result.stderr


def test_clean_offline_sdk_install_and_missing_runtime_dependency(tmp_path):
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
    assert 'somehand' in result.stderr
