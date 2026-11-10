"""Bounded project inventory and manifest-verified archive/restore; stdlib only."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath, PureWindowsPath
import shutil
import stat
import tempfile
import zipfile

MANIFEST = '_5S_MANIFEST.json'


class FiveSError(ValueError):
    pass


def is_link(path):
    info = path.lstat()
    return stat.S_ISLNK(info.st_mode) or bool(getattr(info, 'st_file_attributes', 0) & 0x400)


def project_root(value):
    path = Path(value).expanduser().absolute()
    if not path.is_dir() or is_link(path):
        raise FiveSError('Choose an existing project directory, not a link.')
    path = path.resolve()
    if path.parent == path or path == Path.home().resolve():
        raise FiveSError('Filesystem roots and the entire user home are not project targets.')
    return path


def inside(root, value, *, allow_root=False):
    candidate = Path(value)
    candidate = Path(os.path.abspath(candidate if candidate.is_absolute() else root / candidate))
    if not candidate.is_relative_to(root) or (candidate == root and not allow_root):
        raise FiveSError('Path is not a descendant of the project: ' + str(value))
    cursor = root
    for part in candidate.relative_to(root).parts:
        cursor /= part
        try:
            if is_link(cursor):
                raise FiveSError('Linked path is not allowed: ' + str(cursor))
        except FileNotFoundError:
            continue
    return candidate


def member_path(name):
    if not isinstance(name, str) or not name or '\\' in name or '\0' in name or ':' in name:
        raise FiveSError('Invalid archive member path.')
    path = PurePosixPath(name)
    if path.is_absolute() or PureWindowsPath(name).drive or any(p in ('', '.', '..') for p in name.split('/')):
        raise FiveSError('Unsafe archive member: ' + name)
    return Path(*path.parts)


def digest_stream(stream):
    h = hashlib.sha256()
    size = 0
    for block in iter(lambda: stream.read(1024 * 1024), b''):
        h.update(block)
        size += len(block)
    return h.hexdigest(), size


def digest_file(path):
    with path.open('rb') as stream:
        return digest_stream(stream)


def tree(root, source):
    files, directories = [], []

    def visit(path):
        inside(root, path)
        info = path.lstat()
        member_path(path.relative_to(root).as_posix())
        if stat.S_ISDIR(info.st_mode):
            directories.append(path)
            for child in sorted(path.iterdir()):
                visit(child)
        elif stat.S_ISREG(info.st_mode):
            files.append(path)
        else:
            raise FiveSError('Not an ordinary file or directory: ' + str(path))

    visit(source)
    return files, directories


def snapshot(root, source):
    files, directories = tree(root, source)
    records = {}
    for path in files:
        h, size = digest_file(path)
        records[path.relative_to(root).as_posix()] = {
            'sha256': h, 'bytes': size, 'mode': stat.S_IMODE(path.stat().st_mode) & 0o777,
        }
    return {'schema_version': 1, 'source': source.relative_to(root).as_posix(),
            'files': records, 'directories': [p.relative_to(root).as_posix() for p in directories]}


def verified_manifest(bundle):
    names = bundle.namelist()
    if len(names) != len(set(names)) or MANIFEST not in names:
        raise FiveSError('Duplicate members or missing 5S manifest.')
    if bundle.getinfo(MANIFEST).file_size > 64 * 1024 * 1024:
        raise FiveSError('Manifest is too large to inspect safely.')
    try:
        manifest = json.loads(bundle.read(MANIFEST))
    except (ValueError, UnicodeError) as error:
        raise FiveSError('Unreadable manifest.') from error
    if not isinstance(manifest, dict) or manifest.get('schema_version') != 1:
        raise FiveSError('Unsupported manifest format; use the original project archive tool.')
    records, directories = manifest.get('files'), manifest.get('directories')
    if not isinstance(records, dict) or not isinstance(directories, list) or len(directories) != len(set(directories)):
        raise FiveSError('Invalid file or directory records.')
    source = member_path(manifest.get('source'))
    expected = {MANIFEST, *records, *(d + '/' for d in directories)}
    if set(names) != expected or set(records).intersection(directories):
        raise FiveSError('Archive members differ from the manifest.')
    aliases = set()
    for name in [*records, *directories]:
        path = member_path(name)
        if path != source and not path.is_relative_to(source):
            raise FiveSError('Member is outside the recorded source.')
        key = os.path.normcase(str(path))
        if key in aliases:
            raise FiveSError('Archive names collide on this platform.')
        aliases.add(key)
    for name, record in records.items():
        info = bundle.getinfo(name)
        if stat.S_ISLNK(info.external_attr >> 16) or info.is_dir() or not isinstance(record, dict):
            raise FiveSError('Invalid file record: ' + name)
        if type(record.get('bytes')) is not int or record['bytes'] < 0 or info.file_size != record['bytes']:
            raise FiveSError('Incorrect archived size: ' + name)
        if not isinstance(record.get('sha256'), str) or not isinstance(record.get('mode'), int):
            raise FiveSError('Invalid hash or mode: ' + name)
        with bundle.open(name) as stream:
            h, size = digest_stream(stream)
        if h != record['sha256'] or size != record['bytes']:
            raise FiveSError('Archive content hash mismatch: ' + name)
    for name in directories:
        info = bundle.getinfo(name + '/')
        if not info.is_dir() or stat.S_ISLNK(info.external_attr >> 16):
            raise FiveSError('Invalid directory member: ' + name)
    return manifest


def archive_project(root, source, destination, *, apply=False, remove_source=False):
    root = project_root(root)
    source, destination = inside(root, source), inside(root, destination)
    if not source.exists() or destination == source or destination.is_relative_to(source):
        raise FiveSError('Source is missing or archive would be inside the source.')
    if destination.exists():
        raise FiveSError('Archive destination exists; it will not be replaced.')
    files, directories = tree(root, source)
    result = {'operation': 'archive', 'applied': False, 'source': source.relative_to(root).as_posix(),
              'archive': destination.relative_to(root).as_posix(), 'files': len(files),
              'bytes': sum(p.stat().st_size for p in files), 'remove_source': remove_source}
    if not apply:
        return result
    manifest = snapshot(root, source)
    if MANIFEST in manifest['files']:
        raise FiveSError('The source filename conflicts with the archive manifest.')
    destination.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix='.5s-', suffix='.zip', dir=destination.parent)
    os.close(descriptor)
    temporary = Path(temporary)
    created_destination = False
    try:
        with zipfile.ZipFile(temporary, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as bundle:
            for name in manifest['directories']:
                bundle.write(root / name, name + '/')
            for name in manifest['files']:
                bundle.write(root / name, name)
            bundle.writestr(MANIFEST, json.dumps(manifest, ensure_ascii=False, indent=2))
        with zipfile.ZipFile(temporary) as bundle:
            verified_manifest(bundle)
        # Exclusive destination creation never replaces another archive.
        with destination.open('xb') as output:
            created_destination = True
            with temporary.open('rb') as stream:
                shutil.copyfileobj(stream, output)
            output.flush()
            os.fsync(output.fileno())
        with zipfile.ZipFile(destination) as bundle:
            verified_manifest(bundle)
    except BaseException:
        if created_destination:
            destination.unlink(missing_ok=True)
        raise
    finally:
        temporary.unlink(missing_ok=True)
    result.update(applied=True, archive_sha256=digest_file(destination)[0], archive_bytes=destination.stat().st_size,
                  source_removed=False)
    if remove_source:
        if snapshot(root, source) != manifest:
            raise FiveSError('Source changed after capture; archive retained and source NOT removed.')
        inside(root, source)
        if source.is_dir():
            shutil.rmtree(source)
        else:
            source.unlink()
        result['source_removed'] = True
    return result


def restore_project(root, archive, *, apply=False):
    root = project_root(root)
    archive = inside(root, archive)
    with zipfile.ZipFile(archive) as bundle:
        manifest = verified_manifest(bundle)
        targets = {}
        required_directories = set()
        for name, record in manifest['files'].items():
            target = inside(root, member_path(name))
            if target.exists() and (not target.is_file() or digest_file(target) != (record['sha256'], record['bytes'])):
                raise FiveSError('Existing different content; nothing overwritten: ' + name)
            targets[name] = target
            required_directories.update(p for p in target.parents if p != root and p.is_relative_to(root))
        for name in manifest['directories']:
            required_directories.add(inside(root, member_path(name)))
        for directory in required_directories:
            inside(root, directory)
            if directory.exists() and not directory.is_dir():
                raise FiveSError('File blocks a required directory; nothing restored: ' + str(directory))
        if apply:
            for directory in sorted(required_directories, key=lambda p: len(p.parts)):
                inside(root, directory).mkdir(parents=True, exist_ok=True)
            for name, target in targets.items():
                inside(root, target)
                if target.exists():
                    record = manifest['files'][name]
                    if not target.is_file() or digest_file(target) != (record['sha256'], record['bytes']):
                        raise FiveSError('Target changed after preflight; nothing overwritten: ' + name)
                    continue
                with target.open('xb') as output, bundle.open(name) as stream:
                    shutil.copyfileobj(stream, output)
                record = manifest['files'][name]
                if digest_file(target) != (record['sha256'], record['bytes']):
                    raise FiveSError('Restored content verification failed: ' + name)
                if os.name != 'nt':
                    target.chmod(record['mode'] & 0o777)
    return {'operation': 'restore', 'applied': apply, 'archive': archive.relative_to(root).as_posix(),
            'verified_files': len(targets), 'directories': len(manifest['directories']), 'overwritten': False}


def inventory(root, *, skip=(), root_allow=None, allow_dotfiles=False, output=None):
    root = project_root(root)
    skipped = {inside(root, p) for p in skip}
    output = Path(output).absolute() if output else None
    errors, links, rows, root_files = [], [], [], []

    def measure(path):
        if path == output or any(path == p or path.is_relative_to(p) for p in skipped):
            return 0, 0
        try:
            if is_link(path):
                links.append(path.relative_to(root).as_posix())
                return 0, 0
            info = path.lstat()
            if stat.S_ISREG(info.st_mode):
                return 1, info.st_size
            if stat.S_ISDIR(info.st_mode):
                values = [measure(p) for p in path.iterdir()]
                return sum(v[0] for v in values), sum(v[1] for v in values)
            errors.append({'path':path.relative_to(root).as_posix(),'error':'special_file'})
        except OSError as error:
            errors.append({'path':path.relative_to(root).as_posix(),'error':type(error).__name__})
        return 0, 0

    for path in sorted(root.iterdir()):
        count, size = measure(path)
        rows.append({'path':path.name,'files':count,'bytes':size})
        try:
            if is_link(path) or not stat.S_ISDIR(path.lstat().st_mode):
                root_files.append(path.name)
        except OSError:
            root_files.append(path.name)
    violations = [] if root_allow is None else [n for n in root_files if n not in root_allow and not (allow_dotfiles and n.startswith('.'))]
    return {'operation':'inventory','root':str(root),'at_utc':datetime.now(timezone.utc).isoformat(),
            'complete':not errors,'total_files':sum(v['files'] for v in rows),'total_bytes':sum(v['bytes'] for v in rows),
            'entries':rows,'root_files':root_files,'root_policy_checked':root_allow is not None,
            'root_policy_violations':violations,'skipped_links':links,
            'skipped_directories':[str(p.relative_to(root)) for p in sorted(skipped)],'errors':errors}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    for command in ('inventory','archive','restore'):
        p = sub.add_parser(command)
        p.add_argument('root', type=Path)
        if command == 'inventory':
            p.add_argument('--output', type=Path)
            p.add_argument('--skip',action='append',default=[])
            p.add_argument('--root-allow',nargs='*',default=None)
            p.add_argument('--allow-dotfiles',action='store_true')
        else:
            p.add_argument('source',type=Path)
            if command == 'archive':
                p.add_argument('destination',type=Path)
                p.add_argument('--remove-source',action='store_true')
            p.add_argument('--apply',action='store_true')
    args = parser.parse_args()
    try:
        output = getattr(args, 'output', None)
        if output:
            output = inside(project_root(args.root), output)
            if output.exists():
                raise FiveSError('Report already exists; use a new run path.')
        if args.command == 'inventory':
            result = inventory(args.root,skip=args.skip,root_allow=args.root_allow,allow_dotfiles=args.allow_dotfiles,output=output)
        elif args.command == 'archive':
            result = archive_project(args.root,args.source,args.destination,apply=args.apply,remove_source=args.remove_source)
        else:
            result = restore_project(args.root,args.source,apply=args.apply)
        text = json.dumps(result,ensure_ascii=False,indent=2) + '\n'
        if output:
            output.parent.mkdir(parents=True,exist_ok=True)
            with output.open('x',encoding='utf8') as stream:
                stream.write(text)
        print(text,end='')
    except (FiveSError,OSError,zipfile.BadZipFile,KeyError,TypeError) as error:
        parser.exit(2,str(error)+'\n')


if __name__ == '__main__':
    main()
