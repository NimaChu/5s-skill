"""Build portable and WorkBuddy skill ZIPs from one instruction source (stdlib only)."""
from pathlib import Path
import argparse
import hashlib
import json
import re
import zipfile


CORE_FILES = (
    'SKILL.md',
    'references/helper-usage.md',
    'references/layout-decisions.md',
    'scripts/workspace_5s.py',
    'scripts/check_workspace_5s.py',
)


def build(root, output, version):
    if not re.fullmatch(r'\d+\.\d+\.\d+', version):
        raise ValueError('Version must use major.minor.patch.')
    skill = (root / 'SKILL.md').read_text(encoding='utf-8-sig')
    match = re.match(r'\A---\n(.*?)\n---\n(.*)\Z', skill, re.S)
    if not match or not re.search(r'^name: 5s$', match[1], re.M):
        raise ValueError('Expected the portable 5s skill frontmatter.')
    fields = {
        'display_name': '5S 项目整理',
        'display_name_en': '5S Workspace Housekeeping',
        'description_zh': '盘点项目、安全清理可重建缓存、核验归档并修正入口。',
        'description_en': 'Inventory projects, safely clean rebuildable caches, verify archives and repair entry points.',
        'version': version,
        'author': 'NimaChu',
        'examples_zh': ['做下5S', '用5S技能整理当前项目，归档历史并验证入口。'],
        'examples_en': ['Use the 5S skill to organize this project and verify its entry points.'],
    }
    # JSON strings/lists are valid YAML values; keep portable fields and body intact.
    extra = '\n'.join(key + ': ' + json.dumps(value, ensure_ascii=False)
                      for key, value in fields.items())
    workbuddy = '---\n' + match[1] + '\n' + extra + '\n---\n' + match[2]
    payloads = {name: (root / name).read_bytes() for name in CORE_FILES}
    variants = {
        'portable': {**payloads, 'agents/openai.yaml': (root / 'agents/openai.yaml').read_bytes()},
        'workbuddy': {**payloads, 'SKILL.md': workbuddy.encode('utf-8')},
    }
    output.mkdir(parents=True, exist_ok=True)
    results = []
    for variant, files in variants.items():
        target = output / f'5s-{variant}-{version}.zip'
        with zipfile.ZipFile(target, 'x', compression=zipfile.ZIP_DEFLATED) as bundle:
            for name, data in sorted(files.items()):
                info = zipfile.ZipInfo('5s/' + name, date_time=(2026, 1, 1, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = 0o100644 << 16
                bundle.writestr(info, data)
        with zipfile.ZipFile(target) as bundle:
            assert bundle.testzip() is None
            assert set(bundle.namelist()) == {'5s/' + name for name in files}
            for name, data in files.items():
                assert bundle.read('5s/' + name) == data
        results.append({'file': target.name, 'bytes': target.stat().st_size,
                        'sha256': hashlib.sha256(target.read_bytes()).hexdigest()})
    manifest = output / f'5s-{version}-manifest.json'
    with manifest.open('x', encoding='utf-8') as stream:
        json.dump({'version': version, 'packages': results}, stream, ensure_ascii=False, indent=2)
        stream.write('\n')
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--version', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(build(Path(__file__).resolve().parent.parent,
                           args.output.resolve(), args.version), ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
