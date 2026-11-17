"""Fetch verified GitHub release binaries; never pull or alter a site's Git tree."""
from __future__ import annotations

import hashlib
import io
import json
import os
from pathlib import Path
import platform
import re
import ssl
import subprocess
import sys
import tempfile
from urllib.parse import urlparse
from urllib.request import Request, urlopen
import zipfile

import certifi

from . import __version__

REPOSITORY = 'techreloaded-ar/websmith-cli'
RELEASES_URL = f'https://api.github.com/repos/{REPOSITORY}/releases?per_page=100'
MAX_ARCHIVE = 250_000_000


def version_key(value: str) -> tuple:
    if not isinstance(value, str):
        raise ValueError('Numero di versione non valido.')
    match = re.fullmatch(r'v?(\d+)\.(\d+)\.(\d+)(?:(a|b|rc)(\d+))?', value)
    if not match:
        raise ValueError(f'Versione non riconosciuta: {value}')
    major, minor, patch, stage, number = match.groups()
    return (int(major), int(minor), int(patch), {'a': 0, 'b': 1, 'rc': 2, None: 3}[stage], int(number or 0))


def download(url: str, limit: int) -> bytes:
    parsed = urlparse(url)
    if parsed.scheme != 'https' or parsed.hostname not in {'api.github.com', 'github.com'}:
        raise ValueError('URL release non ammesso.')
    request = Request(url, headers={'User-Agent': f'websmith/{__version__}', 'Accept': 'application/vnd.github+json' if parsed.hostname == 'api.github.com' else 'application/octet-stream'})
    context = ssl.create_default_context(cafile=os.environ.get('SSL_CERT_FILE') or certifi.where())
    with urlopen(request, timeout=30, context=context) as response:
        data = response.read(limit + 1)
    if len(data) > limit:
        raise ValueError('Download oltre il limite consentito.')
    return data


def latest_release() -> dict:
    data = json.loads(download(RELEASES_URL, 5_000_000))
    if not isinstance(data, list):
        raise ValueError('Risposta GitHub releases non valida.')
    releases = []
    for release in data:
        if not isinstance(release, dict) or release.get('draft'):
            continue
        try:
            key = version_key(release.get('tag_name', ''))
        except (ValueError, TypeError):
            continue
        releases.append((key, release))
    if not releases:
        raise ValueError('Nessuna release Websmith pubblicata disponibile.')
    # Include alpha/beta tags: GitHub /latest alone excludes prereleases.
    return max(releases, key=lambda item: item[0])[1]


def platform_asset() -> tuple[str, str]:
    os_name = {'Darwin': 'darwin', 'Linux': 'linux', 'Windows': 'win32'}.get(platform.system())
    cpu = {'arm64': 'arm64', 'aarch64': 'arm64', 'AMD64': 'x64', 'x86_64': 'x64'}.get(platform.machine())
    if f'{os_name}-{cpu}' not in {'darwin-arm64', 'darwin-x64', 'linux-x64', 'win32-x64'}:
        raise ValueError('Piattaforma non supportata dalle release Websmith.')
    return f'websmith-{os_name}-{cpu}.zip', 'websmith.exe' if os_name == 'win32' else 'websmith'


def release_asset_url(release: dict, name: str) -> str:
    assets = [a for a in release.get('assets', []) if isinstance(a, dict) and a.get('name') == name]
    if len(assets) != 1:
        raise ValueError(f'Asset assente o ambiguo nella release: {name}')
    url = assets[0].get('browser_download_url', '')
    expected = f'https://github.com/{REPOSITORY}/releases/download/{release["tag_name"]}/'
    if not url.startswith(expected) or urlparse(url).query or urlparse(url).fragment:
        raise ValueError(f'URL non valido per {name}')
    return url


def verified_binary(release: dict) -> bytes:
    name, binary_name = platform_asset()
    asset_names = {a.get('name') for a in release.get('assets', []) if isinstance(a, dict)}
    checksum_name = 'SHA256SUMS' if 'SHA256SUMS' in asset_names else name.removesuffix('.zip') + '.sha256'
    checksums = download(release_asset_url(release, checksum_name), 100_000).decode('utf-8')
    matches = []
    for line in checksums.splitlines():
        fields = line.split()
        if len(fields) == 2 and fields[1].lstrip('*') == name and re.fullmatch('[a-fA-F0-9]{64}', fields[0]):
            matches.append(fields[0].lower())
    if len(matches) != 1:
        raise ValueError(f'Checksum assente o ambiguo per {name}')
    data = download(release_asset_url(release, name), MAX_ARCHIVE)
    if hashlib.sha256(data).hexdigest() != matches[0]:
        raise ValueError('Checksum non valido: il programma installato non viene sostituito.')
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        items = [entry for entry in archive.infolist() if entry.filename == binary_name]
        if len(items) != 1 or items[0].file_size > MAX_ARCHIVE:
            raise ValueError('Archivio release non valido.')
        # Read only the expected executable; never extract arbitrary paths.
        return archive.read(items[0])


def child_env() -> dict:
    env = os.environ.copy()
    env['PYINSTALLER_RESET_ENVIRONMENT'] = '1'
    return env


def binary_version(path: Path) -> str:
    result = subprocess.run([str(path), '--version'], env=child_env(), capture_output=True, text=True, timeout=60)
    output = result.stdout.strip()
    if result.returncode or not output.startswith('websmith '):
        raise ValueError('Il nuovo eseguibile non supera la verifica di avvio.')
    version = output.removeprefix('websmith ')
    version_key(version)
    return version


def install_binary(target: Path, data: bytes, expected_version: str) -> None:
    """Verify before atomic replacement; preserve the old executable on failure."""
    original = target.read_bytes()
    with tempfile.TemporaryDirectory(prefix='.websmith-update-', dir=target.parent) as folder:
        candidate = Path(folder) / target.name
        candidate.write_bytes(data)
        candidate.chmod(0o755)
        if version_key(binary_version(candidate)) != version_key(expected_version):
            raise ValueError('Versione del download diversa da quella della release.')
        if target.read_bytes() != original:
            raise ValueError('Il programma è stato modificato da un altro aggiornamento: riprovare.')
        previous = Path(folder) / ('previous-' + target.name)
        previous.write_bytes(original)
        previous.chmod(target.stat().st_mode & 0o777)
        os.replace(candidate, target)
        try:
            if version_key(binary_version(target)) != version_key(expected_version):
                raise ValueError('Verifica del programma installato fallita.')
        except (OSError, ValueError, subprocess.SubprocessError):
            os.replace(previous, target)
            raise


def update_program(args, root: Path | None) -> int | None:
    """Return None to continue locally, or the new program's exit status."""
    release = latest_release()
    remote = release['tag_name']
    local_key, remote_key = version_key(__version__), version_key(remote)
    print(f'Versione locale: {__version__}; release disponibile: {remote}.', flush=True)
    if remote_key <= local_key:
        print('Il programma locale è già aggiornato o più recente: nessuna sostituzione.', flush=True)
        return None
    if args.dry_run:
        name, _ = platform_asset()
        release_asset_url(release, name)
        print('Anteprima: aggiornerei il programma alla nuova release, poi le regole del sito '
              'con i suoi modelli. Nessun eseguibile scaricato o file modificato.', flush=True)
        return 0
    if not getattr(sys, 'frozen', False):
        raise ValueError('Autoaggiornamento disponibile per l’eseguibile autonomo. '
                         'Questa esecuzione usa Python: installare una release autonoma o usare --offline per le regole locali.')
    if os.name == 'nt':
        raise ValueError('La sostituzione dell’eseguibile in uso su Windows non è ancora supportata. '
                         'Installare l’archivio della release e rieseguire update.')
    target = Path(sys.executable).resolve()
    print(f'Scaricamento e verifica della release {remote}...', flush=True)
    install_binary(target, verified_binary(release), remote)
    print(f'Programma aggiornato a {remote}. Aggiornamento delle istruzioni...', flush=True)
    if root is None:
        print('Nessun sito selezionato: programma aggiornato. Eseguire update nella cartella del sito per le regole.')
        return 0
    result = subprocess.run([str(target), '--site-root', str(root), 'update', '--offline'], env=child_env())
    if result.returncode:
        print('Programma aggiornato; aggiornamento delle regole non completato. Correggere l’errore indicato e ripetere update.')
    return result.returncode
