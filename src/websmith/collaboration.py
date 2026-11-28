"""Guided Git sharing, using isolated snapshots rather than the user's Git index."""
from __future__ import annotations

from contextlib import contextmanager, redirect_stdout
from dataclasses import dataclass
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import tempfile
from types import SimpleNamespace
from urllib.parse import urlsplit
import uuid

import yaml

from .update import checked_path, write_plan

STATE = '.websmith/collaboration/state.json'
REPO = '.websmith/collaboration/repository.git'
MAX_FILE = 25_000_000
MAX_TOTAL = 250_000_000
ID = re.compile(r'[a-z0-9][a-z0-9-]*\Z')
SHA = re.compile(r'(?:[a-f0-9]{40}|[a-f0-9]{64})\Z')
ROOT_RULES = ('COMPOSITION_GUIDE.md', 'EDITORIAL_RULES.md', 'TONE_OF_VOICE.md')


class CollaborationError(ValueError):
    pass


class GitError(CollaborationError):
    def __init__(self, result):
        self.result = result
        detail = result.stderr.decode('utf-8', 'replace').lower()
        if any(word in detail for word in ('authentication', 'permission denied', 'could not read username', 'repository not found')):
            message = 'Accesso alla condivisione non riuscito. Verificare account, autorizzazioni e accesso Git sul computer.'
        elif 'rejected' in detail or 'non-fast-forward' in detail:
            message = 'La versione condivisa è cambiata durante l’invio. Il lavoro locale è conservato: ripetere la condivisione per integrare gli aggiornamenti.'
        else:
            message = 'Operazione Git non riuscita. Verificare la connessione e l’indirizzo della condivisione; il lavoro locale è conservato.'
        super().__init__(message)


def git(*args, repo=None, data=None, env=None, check=True):
    environment = {k: v for k, v in os.environ.items()
                   if not k.startswith(('GIT_DIR', 'GIT_WORK_TREE', 'GIT_INDEX', 'GIT_OBJECT', 'GIT_ALTERNATE', 'GIT_CONFIG'))}
    environment.update(GIT_TERMINAL_PROMPT='0', GIT_OPTIONAL_LOCKS='0')
    environment.update(env or {})
    command = ['git', '-c', 'core.hooksPath=' + os.devnull, '-c', 'core.fsmonitor=false',
               '-c', 'protocol.ext.allow=never']
    if repo is not None:
        command += ['--git-dir', str(repo)]
    try:
        result = subprocess.run([*command, *map(str, args)], input=data, capture_output=True,
                                env=environment, timeout=90)
    except FileNotFoundError:
        raise CollaborationError('Git non è disponibile sul computer. Completare la configurazione iniziale di Git prima di usare la condivisione.') from None
    except subprocess.TimeoutExpired:
        raise CollaborationError('La condivisione non risponde. Riprovare dopo aver verificato connessione e accesso Git.') from None
    if check and result.returncode:
        raise GitError(result)
    return result


def remote_address(value):
    if not isinstance(value, str) or not value or value.startswith('-') or any(ord(c) < 32 for c in value):
        raise CollaborationError('Indirizzo della condivisione non valido.')
    if '://' in value:
        parsed = urlsplit(value)
        if (parsed.scheme not in {'https', 'ssh', 'file'} or parsed.password or parsed.query
                or parsed.fragment or (parsed.scheme == 'https' and parsed.username)):
            raise CollaborationError('Usare un indirizzo HTTPS o SSH senza password o token; per le prove è ammesso un percorso locale.')
        if parsed.scheme in {'https', 'ssh'} and not parsed.hostname:
            raise CollaborationError('Indirizzo della condivisione incompleto.')
        if parsed.scheme == 'file' and parsed.netloc not in {'', 'localhost'}:
            raise CollaborationError('Il repository di prova deve essere locale.')
        return value
    if re.fullmatch(r'[\w.-]+@[\w.-]+:[\w./~-]+', value):
        return value
    path = Path(value).expanduser()
    if not path.is_absolute():
        raise CollaborationError('Usare un indirizzo HTTPS/SSH o un percorso locale assoluto.')
    return str(path)


def branch_name(value):
    if not isinstance(value, str) or value.startswith('-') or git('check-ref-format', '--branch', value, check=False).returncode:
        raise CollaborationError('Nome della versione condivisa non valido.')
    return value


def relative_name(value):
    if (not isinstance(value, str) or not value or '\\' in value or ':' in value
            or any(ord(c) < 32 for c in value)):
        raise CollaborationError('Percorso del sito non valido.')
    path = PurePosixPath(value)
    if path.is_absolute() or '..' in path.parts or '.' in value.split('/') or str(path) != value:
        raise CollaborationError('Un percorso del sito esce dalla cartella consentita.')
    return value


def private_path(name):
    parts = PurePosixPath(name).parts
    return (any(part.lower() in {'.git', '.websmith', '.venv', '.aws', '.ssh', '.codex', '__pycache__', 'node_modules'} for part in parts)
            or any(part.lower().startswith('.env') or 'recovery_codes' in part.lower() for part in parts)
            or Path(name).suffix.lower() in {'.pem', '.key', '.p12', '.pfx'})


def config_path(args):
    if args.config:
        return args.config.expanduser().absolute()
    return Path(os.environ.get('XDG_CONFIG_HOME', str(Path.home() / '.config'))) / 'websmith/collaboration.json'


def read_json(path):
    if path.is_symlink():
        raise CollaborationError('La configurazione non può essere un collegamento simbolico.')
    value = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(value, dict) or value.get('version') != 1:
        raise CollaborationError('Configurazione della collaborazione non valida.')
    return value


def settings(args):
    path = config_path(args)
    if not path.is_file():
        raise CollaborationError('La collaborazione non è ancora configurata. Chiedere il collegamento al catalogo e usare «collaboration configure».')
    config = read_json(path)
    remote_address(config.get('catalog'))
    branch_name(config.get('branch'))
    return config


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode()


def init_repo(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    git('init', '--bare', str(path))


def fetch(repo, remote, branch):
    remote_address(remote)
    branch_name(branch)
    ref = 'refs/heads/' + branch
    output = git('ls-remote', '--heads', remote, ref, repo=repo).stdout
    if not output.strip():
        return None
    git('fetch', '--no-tags', '--no-recurse-submodules', remote, ref, repo=repo)
    commit = git('rev-parse', '--verify', 'FETCH_HEAD^{commit}', repo=repo).stdout.decode().strip()
    if not SHA.fullmatch(commit):
        raise CollaborationError('La versione condivisa non è valida.')
    return commit


def blob(repo, commit, name, limit=MAX_FILE):
    size = int(git('cat-file', '-s', f'{commit}:{name}', repo=repo).stdout)
    if size > limit:
        raise CollaborationError(f'Il file {name} supera il limite di {limit} byte.')
    return git('show', f'{commit}:{name}', repo=repo).stdout


def site_directory(site_id, path=None):
    if not isinstance(site_id, str) or not ID.fullmatch(site_id):
        raise CollaborationError('Identificativo del sito non valido.')
    expected = 'sites/' + site_id
    if path is not None and path != expected:
        raise CollaborationError('La cartella condivisa deve corrispondere a sites/IDENTIFICATIVO del sito.')
    return expected


def has_blob(repo, commit, name):
    return bool(commit) and git('cat-file', '-e', f'{commit}:{name}', repo=repo, check=False).returncode == 0


def catalog_entries(repo, commit):
    value = (json.loads(blob(repo, commit, 'sites.json', 1_000_000))
             if has_blob(repo, commit, 'sites.json') else {'version': 1, 'sites': []})
    if not isinstance(value, dict) or value.get('version') != 1 or not isinstance(value.get('sites'), list):
        raise CollaborationError('Il catalogo dei siti non è valido.')
    sites = []
    known = set()
    for item in value['sites']:
        if (not isinstance(item, dict) or not isinstance(item.get('id'), str)
                or not ID.fullmatch(item['id']) or item['id'] in known
                or not isinstance(item.get('name'), str) or not item['name'].strip()
                or any(ord(c) < 32 for c in item['name'])):
            raise CollaborationError('Il catalogo contiene un sito non valido o duplicato.')
        known.add(item['id'])
        url = item.get('url', '')
        if not isinstance(url, str) or any(ord(c) < 32 for c in url) or (url and (urlsplit(url).scheme not in {'https', 'http'} or not urlsplit(url).hostname or urlsplit(url).username or urlsplit(url).password)):
            raise CollaborationError('Il catalogo contiene un indirizzo del sito non valido.')
        if 'remote' in item or 'branch' in item:
            raise CollaborationError('Il catalogo usa repository separati. Occorre trasferire i siti in sites/IDENTIFICATIVO e aggiornare il catalogo; nessuna migrazione è stata eseguita.')
        sites.append(dict(item, id=item['id'], name=item['name'],
                          path=site_directory(item['id'], item.get('path')), url=url))
    return sites


def catalog(args):
    config = settings(args)
    with tempfile.TemporaryDirectory(prefix='websmith-catalog-') as folder:
        repo = Path(folder) / 'catalog.git'
        init_repo(repo)
        return [dict(site, remote=config['catalog'], branch=config['branch'])
                for site in catalog_entries(repo, fetch(repo, config['catalog'], config['branch']))]


@dataclass
class Selection:
    directories: set
    files: set
    outputs: set

    def includes(self, name):
        relative_name(name)
        if private_path(name) or any(name == p or name.startswith(p + '/') for p in self.outputs):
            return False
        return name in self.files or any(name.startswith(p + '/') for p in self.directories)


def selection(manifests):
    directories, files, outputs = set(), {'websmith.yaml', 'AGENTS.md', 'CLAUDE.md'}, set()
    for name in ROOT_RULES:
        files.update((name, name.replace('.md', '.local.md')))
    for raw in manifests:
        if raw is None:
            continue
        data = yaml.safe_load(raw)
        if not isinstance(data, dict):
            raise CollaborationError('Manifest del sito non valido.')
        try:
            paths, assets = data['paths'], data['assets']
            outputs.add(relative_name(paths['output']))
            for key in ('contents', 'templates', 'components', 'css', 'media'):
                directories.add(relative_name(paths[key]))
            for source in [assets['shared_images']['source'], *assets['editorial_sources'], *assets['resolution_roots']]:
                directories.add(relative_name(source))
            for name in (paths['composition_guide'], paths['component_catalog'], data['root_redirect']['template'],
                         data['brand']['logo'], *data['styles']['publish']):
                files.add(relative_name(name))
            guide = relative_name(paths['composition_guide'])
            files.add(str(PurePosixPath(guide).with_suffix('.local.md')))
        except (KeyError, TypeError, ValueError):
            raise CollaborationError('Il manifest non dichiara tutti i percorsi necessari alla condivisione.') from None
    for name in directories | files | outputs:
        if private_path(name):
            raise CollaborationError('Il manifest include un percorso riservato; correggerlo prima di condividere.')
    return Selection(directories, files, outputs)


def remote_snapshot(repo, commit, choose, prefix=''):
    result, total = {}, 0
    if commit is None:
        return result
    scope = [prefix + '/'] if prefix else []
    entries = git('ls-tree', '-r', '-z', commit, '--', *scope, repo=repo).stdout.split(b'\0')
    for entry in entries:
        if not entry:
            continue
        info, raw_name = entry.split(b'\t', 1)
        name = relative_name(raw_name.decode('utf-8'))
        if prefix:
            if not name.startswith(prefix + '/'):
                raise CollaborationError('La versione condivisa include un percorso fuori dal sito scelto.')
            name = name[len(prefix) + 1:]
        if not choose.includes(name):
            continue
        if info.split()[0] not in {b'100644', b'100755'}:
            raise CollaborationError(f'Il file condiviso {name} è un collegamento o un elemento non supportato.')
        result[name] = blob(repo, commit, (prefix + '/' if prefix else '') + name)
        total += len(result[name])
        if total > MAX_TOTAL:
            raise CollaborationError('Il sito supera il limite di dimensione della sincronizzazione.')
    return result


def local_snapshot(root, choose):
    names = set(choose.files)
    for directory in choose.directories:
        parent = checked_path(root, directory + '/.websmith-path-check')
        folder = parent.parent
        if folder.exists():
            for path in folder.rglob('*'):
                name = path.relative_to(root).as_posix()
                if choose.includes(name):
                    if path.is_symlink():
                        raise CollaborationError(f'Il percorso {name} è un collegamento simbolico: occorre un file locale.')
                    if path.is_file():
                        names.add(name)
    result, total = {}, 0
    for name in sorted(names):
        if not choose.includes(name):
            continue
        path = checked_path(root, name)
        if path.is_file():
            if path.stat().st_size > MAX_FILE:
                raise CollaborationError(f'Il file {name} supera il limite di {MAX_FILE} byte.')
            result[name] = path.read_bytes()
            total += len(result[name])
            if total > MAX_TOTAL:
                raise CollaborationError('Il sito supera il limite di dimensione della sincronizzazione.')
    return result


def signature(value):
    return None if value is None else hashlib.sha256(value).hexdigest()


def combine(base, local, shared, resolutions):
    merged, conflicts = {}, {}
    for name in sorted(base.keys() | local.keys() | shared.keys()):
        b, l, r = base.get(name), local.get(name), shared.get(name)
        fingerprints = dict(base=signature(b), local=signature(l), shared=signature(r))
        choice = resolutions.get(name, {})
        if l == r or r == b:
            content = l
        elif l == b:
            content = r
        elif all(choice.get(key) == value for key, value in fingerprints.items()) and choice.get('use') in {'local', 'shared'}:
            content = l if choice['use'] == 'local' else r
        else:
            content = None
            if all(value is not None and b'\0' not in value for value in (b, l, r)):
                try:
                    for value in (b, l, r):
                        value.decode('utf-8')
                except UnicodeDecodeError:
                    pass
                else:
                    with tempfile.TemporaryDirectory(prefix='websmith-merge-') as folder:
                        paths = [Path(folder) / part for part in ('local', 'base', 'shared')]
                        for path, value in zip(paths, (l, b, r)):
                            path.write_bytes(value)
                        result = git('merge-file', '-p', *paths, check=False)
                        if result.returncode == 0:
                            content = result.stdout
            if content is None:
                conflicts[name] = fingerprints
                continue
        if content is not None:
            merged[name] = content
    return merged, conflicts


def validate_snapshot(files, site_id):
    from .engine import validate_site_manifest, command_validate_frontmatter, command_validate_pages
    with tempfile.TemporaryDirectory(prefix='websmith-check-') as folder:
        root = Path(folder).resolve()
        for name, content in files.items():
            path = checked_path(root, name)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
        data, errors = validate_site_manifest(str(root))
        if not errors and data['site']['id'] != site_id:
            errors.append('L’identificativo del sito non corrisponde alla condivisione scelta.')
        if not errors:
            for command, options in [(command_validate_frontmatter, {}), (command_validate_pages, {'lang': 'all'})]:
                output = io.StringIO()
                with redirect_stdout(output):
                    result = command(SimpleNamespace(site=str(root), **options))
                if result:
                    errors.append(output.getvalue())
        if errors:
            # Temp paths are implementation details, not helpful to the editor.
            readable = '\n'.join(str(error).replace(str(root) + '/', '') for error in errors[:20])
            raise CollaborationError('Il sito richiede alcune correzioni prima di procedere:\n' + readable)


def site_root(args):
    if args.site_root:
        root = args.site_root.resolve()
    else:
        root = next((p for p in (Path.cwd(), *Path.cwd().parents) if (p / 'websmith.yaml').is_file()), None)
    if root is None or not (root / 'websmith.yaml').is_file():
        raise CollaborationError('Aprire la cartella del sito oppure indicarla con --site-root prima del comando.')
    return root


@contextmanager
def operation(root):
    path = checked_path(root, '.websmith/collaboration/operation.lock')
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        raise CollaborationError('Un’altra sincronizzazione è già in corso. Attendere che termini; dopo un’interruzione chiedere di verificare il blocco locale.') from None
    os.close(fd)
    try:
        yield
    finally:
        path.unlink()


def repository_path(root):
    return checked_path(root, REPO + "/config").parent


def state_for(root):
    path = checked_path(root, STATE)
    if not path.is_file():
        raise CollaborationError('Questo sito non è collegato alla condivisione. Usare «collaboration connect» oppure aprirlo dal catalogo.')
    state = read_json(path)
    remote_address(state.get('remote'))
    branch_name(state.get('branch'))
    if not ID.fullmatch(str(state.get('site_id', ''))) or (state.get('base') is not None and not SHA.fullmatch(str(state['base']))):
        raise CollaborationError('Lo stato locale della collaborazione non è valido.')
    if 'path' not in state:
        raise CollaborationError('Il collegamento precedente usa un repository separato. Conservare la copia locale e riconfigurare la collaborazione per websmith-sites; nessun file è stato modificato.')
    site_directory(state['site_id'], state['path'])
    return state


def plan(root, state, use_resolutions=True):
    repo = repository_path(root)
    commit = fetch(repo, state['remote'], state['branch'])
    base = state['base']
    if base and (not commit or git('merge-base', '--is-ancestor', base, commit, repo=repo, check=False).returncode):
        raise CollaborationError('La cronologia condivisa è cambiata. Il lavoro locale è conservato: verificare il repository prima di ricollegare il sito.')
    local_manifest = checked_path(root, 'websmith.yaml').read_bytes()
    prefix = site_directory(state['site_id'], state['path'])
    manifest_path = prefix + '/websmith.yaml'
    if has_blob(repo, base, manifest_path) and not has_blob(repo, commit, manifest_path):
        raise CollaborationError('Il sito è stato rimosso dalla versione condivisa. La copia locale è conservata: verificare con il responsabile prima di procedere.')
    manifests = [local_manifest]
    for version in (base, commit):
        if has_blob(repo, version, manifest_path):
            manifests.append(blob(repo, version, manifest_path, 1_000_000))
    for raw in manifests:
        data = yaml.safe_load(raw)
        if not isinstance(data, dict) or not isinstance(data.get('site'), dict) or data['site'].get('id') != state['site_id']:
            raise CollaborationError('La versione locale o condivisa appartiene a un altro sito.')
    choose = selection(manifests)
    before = remote_snapshot(repo, base, choose, prefix)
    shared = remote_snapshot(repo, commit, choose, prefix)
    local = local_snapshot(root, choose)
    merged, conflicts = combine(before, local, shared, state.get('resolutions', {}) if use_resolutions else {})
    return commit, before, local, shared, merged, conflicts


def report_conflicts(root, base, local, shared, conflicts, save=True):
    print('Ci sono modifiche sovrapposte. I file di lavoro sono conservati; occorre scegliere come combinarli:')
    if save:
        writes = {}
        for name, fingerprints in conflicts.items():
            token = hashlib.sha256(encoded([name, fingerprints])).hexdigest()[:24]
            folder = f'.websmith/collaboration/conflicts/{token}'
            writes[folder + '/versions.json'] = encoded(dict(path=name, **fingerprints))
            for label, files in [('base', base), ('local', local), ('shared', shared)]:
                if name in files:
                    writes[folder + '/' + label] = files[name]
        write_plan(root, writes)
    for name in conflicts:
        print(f'  - {name}')
    print('Le copie da confrontare sono in .websmith/collaboration/conflicts/. Nessuna scelta precedente viene riusata se le versioni cambiano.')


def apply_snapshot(root, local, merged, state):
    """Back up changes and roll back source files and state together on failure."""
    changes = {name for name in local.keys() | merged.keys() if local.get(name) != merged.get(name)}
    for name in changes:
        path = checked_path(root, name)
        current = path.read_bytes() if path.exists() else None
        if current != local.get(name):
            raise CollaborationError('Un file è cambiato durante la sincronizzazione. Ripetere l’operazione per includere le nuove modifiche.')
    backup = f'.websmith/collaboration/backups/{uuid.uuid4().hex}'
    if changes:
        writes = {f'{backup}/files/{name}': local[name] for name in changes if name in local}
        writes[backup + '/changes.json'] = encoded({'version': 1, 'paths': sorted(changes),
                                                   'previously_absent': sorted(changes - local.keys())})
        write_plan(root, writes)
    previous_state = checked_path(root, STATE).read_bytes()
    writes = {name: merged[name] for name in changes if name in merged}
    writes[STATE] = encoded(state)
    try:
        write_plan(root, writes)
        for name in changes - merged.keys():
            checked_path(root, name).unlink()
    except (OSError, ValueError):
        restore = {name: local[name] for name in changes if name in local}
        restore[STATE] = previous_state
        write_plan(root, restore)
        for name in changes - local.keys():
            path = checked_path(root, name)
            if path.exists():
                path.unlink()
        raise
    return len(changes)


def commit_snapshot(repo, remote_commit, shared, merged, name, email, message, prefix=''):
    with tempfile.TemporaryDirectory(prefix='websmith-index-') as folder:
        environment = {'GIT_INDEX_FILE': str(Path(folder) / 'index'), 'GIT_AUTHOR_NAME': name,
                       'GIT_AUTHOR_EMAIL': email, 'GIT_COMMITTER_NAME': name, 'GIT_COMMITTER_EMAIL': email}
        git('read-tree', remote_commit if remote_commit else '--empty', repo=repo, env=environment)
        for path in sorted(shared.keys() | merged.keys()):
            if shared.get(path) == merged.get(path):
                continue
            source_path = path
            path = (relative_name(prefix) + '/' if prefix else '') + relative_name(path)
            if source_path not in merged:
                # --force-remove requires a working tree; mode 0 index records
                # remove paths from an isolated index in a bare repository.
                record = ('0 ' + '0' * len(remote_commit) + '\t' + path).encode() + b'\0'
                git('update-index', '-z', '--index-info', data=record, repo=repo, env=environment)
            else:
                oid = git('hash-object', '-w', '--stdin', data=merged[source_path], repo=repo).stdout.decode().strip()
                git('update-index', '--add', '--cacheinfo', '100644', oid, path, repo=repo, env=environment)
        tree = git('write-tree', repo=repo, env=environment).stdout.decode().strip()
        parents = ['-p', remote_commit] if remote_commit else []
        commit = git('commit-tree', tree, *parents, data=message.encode(), repo=repo, env=environment).stdout.decode().strip()
        # Keep a recovery ref even if upload or applying the local snapshot fails.
        git('update-ref', 'refs/websmith/prepared', commit, repo=repo)
        return commit


def identity(args):
    if not args.name or not args.email or any(c in args.name + args.email for c in '\r\n\0<>') or '@' not in args.email:
        raise CollaborationError('Indicare nome ed email dell’autore per riconoscere le modifiche condivise.')
    return dict(name=args.name, email=args.email)


def configure(args):
    config = dict(version=1, catalog=remote_address(args.catalog), branch=branch_name(args.branch), identity=identity(args))
    # Verify access before replacing a working configuration.
    with tempfile.TemporaryDirectory() as folder:
        repo = Path(folder) / 'catalog.git'
        init_repo(repo)
        catalog_entries(repo, fetch(repo, config['catalog'], config['branch']))
    path = config_path(args)
    path.parent.mkdir(parents=True, exist_ok=True)
    write_plan(path.parent, {path.name: encoded(config)})
    print('Collaborazione configurata. Ora puoi chiedere «Quali siti posso modificare?».')
    return 0


def connect(args):
    root = site_root(args)
    config = settings(args)
    with operation(root):
        if checked_path(root, STATE).exists():
            raise CollaborationError('Il sito è già collegato. Il collegamento esistente è stato conservato.')
        from .engine import validate_site_manifest
        data, errors = validate_site_manifest(str(root))
        if errors:
            raise CollaborationError('Correggere il manifest del sito prima di collegarlo alla condivisione.')
        repo = repository_path(root)
        if repo.exists():
            raise CollaborationError('Esiste già una preparazione locale della condivisione. Verificarla prima di riprovare.')
        init_repo(repo)
        try:
            remote = config['catalog']
            branch = config['branch']
            fetch(repo, remote, branch)
            state = dict(version=1, site_id=data['site']['id'], remote=remote, branch=branch,
                         path=site_directory(data['site']['id']), base=None, resolutions={},
                         identity=identity(SimpleNamespace(**config['identity'])))
            write_plan(root, {STATE: encoded(state)})
        except Exception:
            shutil.rmtree(repo)
            raise
    print('Sito collegato. Il lavoro locale è conservato. Usa «status» per confrontarlo o «share» per condividerlo.')
    return 0


def open_site(args):
    matches = [site for site in catalog(args)
               if site['id'] == args.site_id or (site['url'] and urlsplit(site['url']).hostname == args.site_id)]
    if not matches:
        raise CollaborationError('Il sito non è presente nel catalogo configurato.')
    if len(matches) != 1:
        raise CollaborationError('Più siti usano questo dominio. Scegliere l’identificativo esatto mostrato nel catalogo.')
    site = matches[0]
    destination = (args.destination or Path.cwd() / site['id']).absolute()
    if destination.exists() or destination.is_symlink():
        raise CollaborationError('La cartella scelta esiste già. Scegliere una nuova cartella; per un sito esistente usare «connect».')
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.websmith-open-', dir=destination.parent) as folder:
        root = Path(folder) / 'site'
        root.mkdir()
        repo = repository_path(root)
        init_repo(repo)
        commit = fetch(repo, site['remote'], site['branch'])
        if commit is None:
            raise CollaborationError('Il sito non ha ancora una versione condivisa. Chiedere al responsabile di condividere la prima versione.')
        prefix = site_directory(site['id'], site['path'])
        if not has_blob(repo, commit, prefix + '/websmith.yaml'):
            raise CollaborationError('Il sito non ha ancora una versione condivisa nella sua cartella. Chiedere al responsabile di condividere la prima versione.')
        raw = blob(repo, commit, prefix + '/websmith.yaml', 1_000_000)
        files = remote_snapshot(repo, commit, selection([raw]), prefix)
        validate_snapshot(files, site['id'])
        write_plan(root, files)
        # Reuse conservative initialization for machine-owned instruction metadata.
        from .initialize import command_init
        # The internal bare repo is not site initialization metadata.
        if command_init(SimpleNamespace(site_root=root, yes=True, agent=args.agent,
                                       offline=args.offline)) != 0:
            raise CollaborationError('Preparazione delle istruzioni non riuscita. La destinazione non è stata creata.')
        author = settings(args)['identity']
        state = dict(version=1, site_id=site['id'], remote=site['remote'], branch=site['branch'],
                     path=prefix, base=commit, resolutions={}, identity=identity(SimpleNamespace(**author)))
        write_plan(root, {STATE: encoded(state)})
        if destination.exists() or destination.is_symlink():
            raise CollaborationError('La destinazione è stata creata da un’altra operazione: nessun file è stato sostituito.')
        root.rename(destination)
    print(f'Sito «{site["name"]}» pronto in {destination}. Apri questa cartella nel tuo agente e lavora normalmente.')
    return 0


def list_sites(args):
    sites = catalog(args)
    if not sites:
        print('Nessun sito nel catalogo condiviso. Il responsabile può aggiungerlo con «register».')
    for site in sites:
        print(f'{site["id"]} — {site["name"]}' + (f' — {site["url"]}' if site['url'] else ''))
    print('Il catalogo indica i siti disponibili; l’accesso effettivo dipende dai permessi del tuo account.')
    return 0


def register(args):
    config = settings(args)
    root = site_root(args)
    with operation(root):
        state = state_for(root)
        if state['remote'] != config['catalog'] or state['branch'] != config['branch']:
            raise CollaborationError('Il sito e il catalogo devono usare lo stesso repository e la stessa versione condivisa.')
        from .engine import validate_site_manifest
        data, errors = validate_site_manifest(str(root))
        if errors or data['site']['id'] != state['site_id']:
            raise CollaborationError('Correggere il manifest prima di aggiungere il sito al catalogo.')
        with tempfile.TemporaryDirectory(prefix='websmith-register-') as folder:
            repo = Path(folder) / 'catalog.git'
            init_repo(repo)
            commit = fetch(repo, config['catalog'], config['branch'])
            sites = catalog_entries(repo, commit)
            item = dict(id=state['site_id'], name=data['site']['name'], url=data['site']['base_url'],
                        path=site_directory(state['site_id'], state['path']))
            if not has_blob(repo, commit, item['path'] + '/websmith.yaml'):
                raise CollaborationError('Condividere la prima versione del sito prima di aggiungerlo al catalogo.')
            previous = next((site for site in sites if site['id'] == item['id']), None)
            if previous:
                if previous != item:
                    raise CollaborationError('Esiste già un sito con questo identificativo e una configurazione diversa. Il catalogo è stato conservato.')
                print('Il sito è già presente nel catalogo.')
                return 0
            sites.append(item)
            old = ({'sites.json': blob(repo, commit, 'sites.json', 1_000_000)}
                   if has_blob(repo, commit, 'sites.json') else {})
            value = json.loads(old['sites.json']) if old else {'version': 1}
            value['sites'] = sorted(sites, key=lambda site: site['id'])
            new = {'sites.json': encoded(value)}
            author = identity(SimpleNamespace(**config['identity']))
            prepared = commit_snapshot(repo, commit, old, new, **author, message=f'Aggiunto sito {item["id"]}')
            git('push', config['catalog'], prepared + ':refs/heads/' + config['branch'], repo=repo)
    print('Sito aggiunto al catalogo. Gli altri collaboratori possono ora trovarlo; i permessi sono gestiti dal servizio Git.')
    return 0


def changes(left, right):
    return sorted(name for name in left.keys() | right.keys() if left.get(name) != right.get(name))


def status(args):
    root = site_root(args)
    with operation(root):
        state = state_for(root)
        commit, base, local, shared, merged, conflicts = plan(root, state)
        local_changes, remote_changes = changes(base, local), changes(base, shared)
        print(f'Sito: {state["site_id"]}')
        print(f'File modificati da te rispetto all’ultimo allineamento: {len(local_changes)}')
        for name in local_changes:
            print(f'  - {name}')
        print(f'File aggiornati nella versione condivisa: {len(remote_changes)}')
        for name in remote_changes:
            print(f'  - {name}')
        if conflicts:
            print('Occorre una scelta per: ' + ', '.join(conflicts))
        elif not local_changes and not remote_changes:
            print('La tua copia è allineata alla versione condivisa.')
        else:
            print('Le modifiche possono essere combinate. «sync» riceve gli aggiornamenti; «share» condivide il tuo lavoro.')
    return 0


def sync(args):
    root = site_root(args)
    with operation(root):
        state = state_for(root)
        commit, base, local, shared, merged, conflicts = plan(root, state)
        if conflicts:
            report_conflicts(root, base, local, shared, conflicts, save=not args.dry_run)
            return 1
        validate_snapshot(merged, state['site_id'])
        if args.dry_run:
            print(f'Anteprima: aggiornerei {len(changes(local, merged))} file. Nessun sorgente o scelta salvata è stato modificato.')
            return 0
        state.update(base=commit, resolutions={})
        count = apply_snapshot(root, local, merged, state)
        print(f'Aggiornamenti ricevuti: {count} file. Le tue modifiche sono conservate; nessun lavoro è stato inviato agli altri.')
    return 0


def share(args):
    root = site_root(args)
    with operation(root):
        state = state_for(root)
        commit, base, local, shared, merged, conflicts = plan(root, state)
        if conflicts:
            report_conflicts(root, base, local, shared, conflicts, save=not args.dry_run)
            return 1
        validate_snapshot(merged, state['site_id'])
        outgoing = changes(shared, merged)
        if args.dry_run:
            print(f'Anteprima: condividerei {len(outgoing)} file e integrerei {len(changes(local, merged))} aggiornamenti locali. Nessun invio eseguito.')
            for name in outgoing:
                print(f'  - {name}')
            return 0
        author = identity(SimpleNamespace(**state['identity']))
        message = args.message or f'Modifiche al sito {state["site_id"]}'
        if not message.strip() or '\0' in message:
            raise CollaborationError('Scrivere una breve descrizione delle modifiche.')
        if outgoing:
            prepared = commit_snapshot(repository_path(root), commit, shared, merged, **author,
                                       message=message, prefix=state['path'])
            git('push', state['remote'], prepared + ':refs/heads/' + state['branch'], repo=repository_path(root))
            commit = prepared
        state.update(base=commit, resolutions={})
        try:
            apply_snapshot(root, local, merged, state)
        except (OSError, ValueError):
            if outgoing:
                raise CollaborationError('Il lavoro è stato inviato alla condivisione, ma l’allineamento locale non è terminato. Le copie di recupero sono conservate: ripetere «sync».') from None
            raise
        print(f'Modifiche condivise: {len(outgoing)} file. Gli altri collaboratori possono riceverle con «sync».')
        print('Websmith non ha eseguito operazioni sull’hosting. Eventuali automazioni del repository seguono la configurazione del responsabile.')
    return 0


def resolve(args):
    root = site_root(args)
    name = relative_name(args.path)
    with operation(root):
        state = state_for(root)
        commit, base, local, shared, merged, conflicts = plan(root, state, use_resolutions=False)
        if name not in conflicts:
            raise CollaborationError('Il file non presenta attualmente una sovrapposizione da risolvere.')
        choices = state.setdefault('resolutions', {})
        choices[name] = dict(**conflicts[name], use=args.use)
        write_plan(root, {STATE: encoded(state)})
    print('Scelta registrata per queste versioni del file. Usa «sync» per applicarla o «share» per condividere il risultato.')
    return 0


def command_collaboration(args):
    actions = dict(configure=configure, list=list_sites, open=open_site, connect=connect,
                   register=register, status=status, sync=sync, share=share, resolve=resolve)
    try:
        return actions[args.collaboration_action](args)
    except (OSError, ValueError, yaml.YAMLError, KeyError, TypeError) as error:
        if isinstance(error, CollaborationError):
            print(str(error))
        elif isinstance(error, (json.JSONDecodeError, yaml.YAMLError, KeyError, TypeError)):
            print('Dati della collaborazione non validi. Verificare catalogo, manifest e configurazione locale; i file di lavoro sono conservati.')
        else:
            print('Operazione non completata. Verificare i percorsi e i permessi locali; i file di lavoro sono conservati.')
        return 2


def add_parser(subparsers):
    parser = subparsers.add_parser('collaboration', aliases=['collab'], help='Sceglie siti condivisi, riceve aggiornamenti e condivide il lavoro con il team')
    parser.add_argument('--config', type=Path, help='Configurazione personale alternativa (prima dell’azione)')
    actions = parser.add_subparsers(dest='collaboration_action', required=True)
    setup = actions.add_parser('configure', help='Configura il catalogo e la tua identità una volta per computer')
    setup.add_argument('--catalog', '--repository', dest='catalog', required=True, help='Indirizzo Git del repository comune websmith-sites')
    setup.add_argument('--branch', default='main')
    setup.add_argument('--name', required=True, help='Il tuo nome')
    setup.add_argument('--email', required=True, help='La tua email')
    actions.add_parser('list', help='Mostra i siti nel catalogo condiviso')
    opening = actions.add_parser('open', help='Prepara un sito del catalogo in una nuova cartella locale')
    opening.add_argument('site_id', help='Identificativo del sito o dominio')
    opening.add_argument('--destination', type=Path, help='Nuova cartella da creare; predefinita ./IDENTIFICATIVO')
    opening.add_argument('--agent', choices=['codex', 'claude', 'none'], default='codex')
    opening.add_argument('--offline', action='store_true', help='Usa le istruzioni Websmith già disponibili; il sito viene comunque scaricato da Git')
    connection = actions.add_parser('connect', help='Collega un sito locale esistente al suo repository condiviso')
    actions.add_parser('register', help='Aggiunge il sito collegato al catalogo condiviso')
    actions.add_parser('status', help='Mostra il lavoro locale e gli aggiornamenti degli altri')
    for name, description in [('sync', 'Riceve gli aggiornamenti conservando il tuo lavoro'), ('share', 'Condivide il lavoro e riceve gli aggiornamenti compatibili')]:
        action = actions.add_parser(name, help=description)
        action.add_argument('--dry-run', action='store_true', help='Mostra le differenze senza cambiare sorgenti o inviare modifiche; aggiorna solo la cache Git interna')
        if name == 'share':
            action.add_argument('--message', help='Breve descrizione delle modifiche')
    resolution = actions.add_parser('resolve', help='Registra una scelta per un file modificato da più persone')
    resolution.add_argument('path', help='Percorso del file rispetto alla radice del sito')
    resolution.add_argument('--use', choices=['local', 'shared'], required=True, help='Versione locale o condivisa; prima confrontare entrambe')
    parser.set_defaults(func=command_collaboration)
