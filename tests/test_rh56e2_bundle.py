import importlib.util
import subprocess
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_bundle_fails_closed_when_required_resource_missing(tmp_path):
    spec = importlib.util.spec_from_file_location('bundle', ROOT / 'scripts/setup/package_rh56e2.py')
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    import pytest
    with pytest.raises(FileNotFoundError, match='track_g1.onnx'):
        module.build_bundle(tmp_path, tmp_path / 'out.tar.gz')


def test_bundle_includes_explicit_assets_not_secrets_or_recordings(tmp_path):
    spec = importlib.util.spec_from_file_location('bundle', ROOT / 'scripts/setup/package_rh56e2.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    subprocess.run(['git', 'init', '-q', str(tmp_path)], check=True)
    (tmp_path / 'README.md').write_text('source')
    subprocess.run(['git', '-C', str(tmp_path), 'add', 'README.md'], check=True)
    subprocess.run(['git', '-C', str(tmp_path), '-c', 'user.name=Test', '-c', 'user.email=test@example.invalid', 'commit', '-qm', 'fixture'], check=True)
    for name in ['ckpt/track_g1.onnx', 'assets/robots/unitree_g1/g1_29dof.xml',
                 'teleopit/retargeting/gmr/assets/unitree_g1/g1.xml',
                 'third_party/g1_bridge_sdk/thirdparty/unitree_sdk2/CMakeLists.txt',
                 '.ssh/id_ed25519', 'recordings/private.h5', '.env']:
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('fixture')
    sdk = tmp_path / 'third_party/g1_bridge_sdk/thirdparty/unitree_sdk2'
    (sdk / 'libddsc.so.0').write_text('library')
    (sdk / 'libddsc.so').symlink_to('libddsc.so.0')
    subprocess.run(['git', 'init', '-q', str(sdk)], check=True)
    subprocess.run(['git', '-C', str(sdk), 'add', 'CMakeLists.txt', 'libddsc.so.0', 'libddsc.so'], check=True)
    subprocess.run(['git', '-C', str(sdk), '-c', 'user.name=Test', '-c', 'user.email=test@example.invalid', 'commit', '-qm', 'fixture'], check=True)
    output = tmp_path / 'bundle.tar.gz'
    module.build_bundle(tmp_path, output)
    with tarfile.open(output) as archive:
        names = archive.getnames()
    assert 'Teleopit-rh56e2/README.md' in names
    assert 'Teleopit-rh56e2/ckpt/track_g1.onnx' in names
    assert 'Teleopit-rh56e2/third_party/g1_bridge_sdk/thirdparty/unitree_sdk2/libddsc.so' in names
    assert not any('id_ed25519' in n or 'recordings' in n or '.env' in n or '/.git/' in n for n in names)
