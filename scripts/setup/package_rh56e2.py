#!/usr/bin/env python3
"""Package committed fork source plus explicit runtime assets; never an environment."""
from __future__ import annotations

import argparse
import io
import posixpath
import subprocess
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PREFIX = 'Teleopit-rh56e2/'


def build_bundle(root: Path, output: Path) -> None:
    """Export Git HEAD and selected data; untracked private files are excluded."""
    policy = root / 'ckpt/track_g1.onnx'
    if not policy.is_file():
        raise FileNotFoundError(f'Missing {policy}; prepare model assets first')
    resources = [root / 'assets/robots/unitree_g1', root / 'teleopit/retargeting/gmr/assets/unitree_g1']
    sdk = root / 'third_party/g1_bridge_sdk/thirdparty/unitree_sdk2'
    for path in [*resources, sdk]:
        if not path.is_dir():
            raise FileNotFoundError(f'Missing {path}; see docs/zh/deployment.md')
    archives = []
    for directory, prefix in [(root, PREFIX), (sdk, PREFIX + sdk.relative_to(root).as_posix() + '/')]:
        top = subprocess.check_output(['git', '-C', str(directory), 'rev-parse', '--show-toplevel'], text=True).strip()
        if Path(top).resolve() != directory.resolve():
            raise ValueError(f'Expected an independent Git checkout at {directory}')
        archives.append(subprocess.check_output(['git', '-C', str(directory), 'archive', '--format=tar', '--prefix=' + prefix, 'HEAD']))
    seen = set()
    with tarfile.open(output, 'x:gz') as target:
        for data in archives:
            with tarfile.open(fileobj=io.BytesIO(data)) as source:
                for member in source:
                    if member.issym() or member.islnk():
                        current, visited = member, set()
                        while current.issym() or current.islnk():
                            if current.name in visited:
                                raise ValueError(f'Link cycle: {member.name}')
                            visited.add(current.name)
                            linked = posixpath.normpath(posixpath.join(posixpath.dirname(current.name), current.linkname)) if current.issym() else current.linkname
                            if not linked.startswith(PREFIX) or linked not in source.getnames():
                                raise ValueError(f'External archive link: {member.name}')
                            current = source.getmember(linked)
                        if not current.isfile():
                            raise ValueError(f'Non-file link: {member.name}')
                    target.addfile(member, source.extractfile(member) if member.isfile() else None)
                    seen.add(member.name)
        candidates = [policy]
        for folder in resources:
            candidates.extend(p for p in folder.rglob('*') if p.suffix.lower() in {'.xml', '.stl', '.obj', '.png', '.jpg'})
        for path in candidates:
            if path.is_symlink() or not path.resolve().is_relative_to(root.resolve()):
                raise ValueError(f'Refusing external asset: {path}')
            name = PREFIX + path.relative_to(root).as_posix()
            if name not in seen and path.is_file():
                target.add(path, arcname=name, recursive=False)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    try:
        build_bundle(ROOT, args.output)
    except (OSError, ValueError, subprocess.CalledProcessError) as exc:
        parser.exit(1, f'Bundle failed: {exc}\n')
    print(f'Created {args.output}; code comes from Git HEAD, not uncommitted edits. Transfer wheelhouse separately.')


if __name__ == '__main__':
    main()
