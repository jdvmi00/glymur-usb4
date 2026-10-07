#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Verify imported inputs, reconstruct review source, and run extracted C tests."""
import argparse
import hashlib
import json
from pathlib import Path
import resource
import shutil
import subprocess
import sys
import tarfile

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / 'build-output'
WORK = OUTPUT / 'reconstructed'
TREE = WORK / 'linux-7.3-rc2'
UPSTREAM_SHA256 = '6b97fb9397172e95ed95b56a78524a184bf186858bea7a271b9ebe81a0e57417'
CANDIDATE = ROOT / 'reproduce'
FINGERPRINTS = 98


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def series():
    names = (ROOT / 'patches/series').read_text().splitlines()
    require(names and len(names) == len(set(names)), 'empty or duplicate patch series')
    require(all(Path(name).name == name and name.endswith('.patch') for name in names),
            'invalid patch series entry')
    return [ROOT / 'patches' / name for name in names]


def check():
    manifest = json.loads((ROOT / 'IMPORT-MANIFEST.json').read_text())
    seen = set()
    for entry in manifest['files'] + manifest['derived_files']:
        name = entry['path']
        path = ROOT / name
        require(not Path(name).is_absolute() and '..' not in Path(name).parts,
                f'invalid imported path: {name}')
        require(name not in seen, f'duplicate import: {name}')
        seen.add(name)
        require(path.resolve().is_relative_to(ROOT) and not path.is_symlink(),
                f'import escapes checkout or is a symlink: {name}')
        require(path.is_file() and digest(path) == entry['sha256'],
                f'import changed or missing: {name}')
    ordered = [str(path.relative_to(ROOT)) for path in series()]
    recorded = [entry['path'] for entry in manifest['derived_files']
                if entry['path'].endswith('.patch')]
    require(ordered == recorded, 'patch order differs from the derivation manifest')
    print(f'PASS: {len(seen)} source inputs match recorded hashes', flush=True)


def run(command, cwd=ROOT, log=None):
    subprocess.run([str(item) for item in command], cwd=cwd, check=True,
                   stdout=log, stderr=subprocess.STDOUT if log else None)


def verify_tree():
    count = 0
    for line in (CANDIDATE / 'expected-source.sha256').read_text().splitlines():
        expected, name = line.split(maxsplit=1)
        require(digest(TREE / name) == expected, f'source fingerprint mismatch: {name}')
        count += 1
    require(count == FINGERPRINTS, f'unexpected source fingerprint count: {count}')
    require((TREE / '.config').read_bytes() ==
            (CANDIDATE / 'kernel.config').read_bytes(),
            'configuration mismatch')
    print(f'PASS: {count} source fingerprints and checkpoint configuration', flush=True)


def reconstruct(archive):
    check()
    require(digest(archive) == UPSTREAM_SHA256, 'upstream archive checksum mismatch')
    require(not WORK.exists(), 'reconstruction destination already exists; retain or move it first')
    OUTPUT.mkdir(exist_ok=True)
    WORK.mkdir()
    recipe = CANDIDATE / 'baseline'
    with (WORK / 'reconstruction.log').open('w') as log:
        print('Extracting checksum-verified upstream archive...', flush=True)
        with tarfile.open(archive, 'r:gz') as tar:
            require(all(Path(member.name).parts and
                        Path(member.name).parts[0] == 'linux-7.3-rc2'
                        for member in tar.getmembers()), 'unexpected archive root')
            tar.extractall(WORK, filter='data')
        # Prevent git apply from discovering a containing workspace repository
        # whose ignore rules would silently skip paths in this build directory.
        run(['git', 'init', '--quiet', TREE], log=log)
        # The order is preserved from the recorded 1.89 PKGBUILD prepare(): the
        # Surface 1.17 prerequisites. Candidates from 1.113 on no longer apply
        # 0010; the review baseline keeps it (docs/PROVENANCE.md).
        # Use git apply for baseline patches just as the recipe does. No
        # PKGBUILD evaluation, make, packaging, installation or device access.
        numbers = list(range(1, 13)) + list(range(14, 20)) + [13] + list(range(20, 40))
        for number in numbers:
            if number == 13:
                shutil.copy2(recipe / 'glymur-microsoft-surface-laptop8.dts',
                             TREE / 'arch/arm64/boot/dts/qcom/')
            patches = list(recipe.glob(f'{number:04d}-*.patch'))
            require(len(patches) == 1, f'expected one patch numbered {number}')
            run(['git', 'apply', patches[0]], cwd=TREE, log=log)
        with (TREE / 'arch/arm64/boot/dts/qcom/Makefile').open('a') as stream:
            stream.write('dtb-$(CONFIG_ARCH_QCOM) += glymur-microsoft-surface-laptop8.dtb\n')
        for patch in series():
            print(f'Applying {patch.name}...', flush=True)
            run(['git', 'apply', patch], cwd=TREE, log=log)
        shutil.copy2(CANDIDATE / 'kernel.config', TREE / '.config')
        (TREE / 'localversion.10-pkgrel').write_text('-1.151\n')
        (TREE / 'localversion.20-pkgname').write_text('-aarch64\n')
    verify_tree()
    print('Source ready under build-output/reconstructed/linux-7.3-rc2/')


def test():
    check()
    verify_tree()
    # Limit ordinary core files as a fallback. RLIMIT_CORE does not suppress
    # piped crash handlers; tests/harness.h converts assertion aborts to exit 134.
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    scripts = ROOT / 'tests'
    ctrl = TREE / 'drivers/gpu/drm/msm/dp/dp_ctrl.c'
    dpu = TREE / 'drivers/gpu/drm/msm/disp/dpu1'
    cases = [
        ('test-usb4-fec-integration.py', ['--provider', TREE / 'drivers/thunderbolt/qcom-usb4-dp.c', '--ctrl', ctrl]),
        ('test-usb4-route-restore.py', ['--source-dir', dpu]),
        ('test-dpu-plane-split-reset.py', [dpu / 'dpu_plane.c']),
        ('test-usb4-idle-status.py', ['--source', ctrl]),
        ('test-usb4-link-irq.py', ['--source', ctrl]),
        ('test-usb4-port-ownership.py', ['--source', TREE / 'drivers/thunderbolt/qcom-usb4-host.c']),
        ('test-usb4-phy-typec-mode.py', ['--source', TREE / 'drivers/phy/qualcomm/phy-qcom-qmp-combo.c']),
        ('test-msm-dp-hpd-deferral.py', ['--source', TREE / 'drivers/gpu/drm/msm/dp/dp_display.c']),
    ]
    results = OUTPUT / 'test-results'
    results.mkdir(exist_ok=True)
    for name, args in cases:
        print(f'Running {name}...', flush=True)
        with (results / (name + '.log')).open('w') as log:
            run([sys.executable, '-B', scripts / name, *args], log=log)
        print((results / (name + '.log')).read_text(), end='')
    print('PASS: eight extracted-code test suites; no hardware validation')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('check')
    rebuild = commands.add_parser('reconstruct')
    rebuild.add_argument('--archive', type=Path, required=True)
    commands.add_parser('test')
    args = parser.parse_args()
    try:
        if args.command == 'check':
            check()
        elif args.command == 'reconstruct':
            reconstruct(args.archive.resolve())
        else:
            test()
    except (ValueError, OSError, subprocess.CalledProcessError, tarfile.TarError) as error:
        print(f'FAIL: {error}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
