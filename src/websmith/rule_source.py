"""External skill and instruction distribution, pinned to one GitHub commit."""
from __future__ import annotations

import hashlib
import io
import json
import os
from pathlib import Path
import re
import tempfile
import zipfile

from .self_update import REPOSITORY, download
from .instruction_bundle import SOURCE_PATHS

FILES = tuple(SOURCE_PATHS)


def local_files(root: Path) -> dict[str, str]:
    """Read a repository or portable bundle, accepting the old dev env path."""
    # Previous CI/dev configurations point at src/websmith/resources.
    if root.parts[-3:] == ('src', 'websmith', 'resources') and (root.parents[2] / 'skills').is_dir():
        root = root.parents[2]
    files = {}
    for name, source in SOURCE_PATHS.items():
        path = root / source
        if not path.is_file():
            # A portable external bundle uses the logical distribution paths.
            path = root / name
        files[name] = path.read_text(encoding='utf-8')
    return validate(files)


def cache_root() -> Path:
    return Path(os.environ.get('XDG_CACHE_HOME', str(Path.home() / '.cache'))) / 'websmith' / 'instructions'


def validate(files: dict) -> dict[str, str]:
    if set(files) != set(FILES):
        raise ValueError('Distribuzione delle istruzioni incompleta o incompatibile; eseguire update con la rete attiva per scaricare anche le skill.')
    if any(not isinstance(text, str) or not text.strip() or len(text.encode('utf-8')) > 1_000_000 for text in files.values()):
        raise ValueError('File delle istruzioni vuoto o troppo grande.')
    return files


def load(*, offline: bool = False, persist: bool = True) -> tuple[dict[str, str], str]:
    if offline:
        # Explicit external directory is useful for development and native smoke tests.
        external = os.environ.get('WEBSMITH_RESOURCE_DIR')
        if external:
            root = Path(external)
        elif (cache_root() / 'current.json').is_file():
            snapshot = json.loads((cache_root() / 'current.json').read_text(encoding='utf-8'))
            if not isinstance(snapshot, dict) or not isinstance(snapshot.get('revision'), str) or not isinstance(snapshot.get('files'), dict):
                raise ValueError('Cache delle istruzioni non valida: eseguire update con la rete attiva.')
            return validate(snapshot['files']), snapshot['revision']
        else:
            root = Path(__file__).resolve().parents[2]
        try:
            files = local_files(root)
        except OSError as exc:
            raise ValueError('Nessuna copia esterna delle istruzioni disponibile. Eseguire prima init o update con la connessione attiva.') from exc
        files = validate(files)
        revision = 'local-' + hashlib.sha256(json.dumps(files, sort_keys=True).encode()).hexdigest()
        return files, revision

    commit = json.loads(download(f'https://api.github.com/repos/{REPOSITORY}/commits/main', 2_000_000))
    revision = commit.get('sha', '')
    if not re.fullmatch('[a-f0-9]{40}', revision):
        raise ValueError('Revisione GitHub non valida.')
    payload = download(f'https://github.com/{REPOSITORY}/archive/{revision}.zip', 25_000_000)
    prefix = f'websmith-cli-{revision}/'
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        files = {}
        for name, source in SOURCE_PATHS.items():
            matches = [entry for entry in archive.infolist() if entry.filename == prefix + source]
            if len(matches) != 1 or matches[0].file_size > 1_000_000:
                raise ValueError(f'File delle istruzioni mancante o non valido: {name}')
            files[name] = archive.read(matches[0]).decode('utf-8')
    validate(files)
    if persist:
        root = cache_root()
        root.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=root, delete=False) as stream:
            temporary = Path(stream.name)
            json.dump({'revision': revision, 'files': files}, stream, ensure_ascii=False)
        try:
            os.replace(temporary, root / 'current.json')
        finally:
            temporary.unlink(missing_ok=True)
    return files, revision
