"""Refresh managed rule bases; leave optional site-local overrides untouched."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import zipfile
from pathlib import Path
import tempfile

from . import __version__
from .initialize import BASE_GUIDES, agent_files


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def checked_path(root: Path, name: str) -> Path:
    """Only allow ordinary files/directories inside the selected site."""
    relative = Path(name)
    if relative.is_absolute() or '..' in relative.parts:
        raise ValueError(f'Percorso non valido: {name}')
    target = root / relative
    for node in (target, *target.parents):
        if node == root:
            break
        if node.is_symlink():
            raise ValueError(f'Collegamento simbolico non ammesso: {node.relative_to(root)}')
        if node.exists() and (not node.is_file() if node == target else not node.is_dir()):
            raise ValueError(f'Percorso incompatibile: {node.relative_to(root)}')
    return target


def read_object(path: Path) -> dict:
    value = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(value, dict):
        raise ValueError(f'Metadati non validi: {path.name}')
    return value


def write_plan(root: Path, writes: dict[str, bytes]) -> None:
    """Preflight and stage all data; restore existing bytes if a write fails."""
    originals = {}
    for name in writes:
        target = checked_path(root, name)
        originals[name] = target.read_bytes() if target.exists() else None
    created_dirs = []
    applied = []
    with tempfile.TemporaryDirectory(prefix='websmith-update-') as folder:
        stage = Path(folder)
        for index, data in enumerate(writes.values()):
            (stage / str(index)).write_bytes(data)
        try:
            for index, name in enumerate(writes):
                target = checked_path(root, name)
                current = target.read_bytes() if target.exists() else None
                if current != originals[name]:
                    raise ValueError(f'File cambiato durante update: {name}')
                missing = []
                parent = target.parent
                while parent != root and not parent.exists():
                    missing.append(parent)
                    parent = parent.parent
                for parent in reversed(missing):
                    parent.mkdir()
                    created_dirs.append(parent)
                # Temporary file on the same filesystem allows atomic replacement.
                with tempfile.NamedTemporaryFile(dir=target.parent, delete=False) as stream:
                    replacement = Path(stream.name)
                    stream.write((stage / str(index)).read_bytes())
                try:
                    if target.exists():
                        replacement.chmod(target.stat().st_mode & 0o777)
                    os.replace(replacement, target)
                finally:
                    replacement.unlink(missing_ok=True)
                applied.append(name)
        except (OSError, ValueError):
            for name in reversed(applied):
                target = root / name
                if originals[name] is None:
                    target.unlink()
                else:
                    target.write_bytes(originals[name])
            for parent in reversed(created_dirs):
                parent.rmdir()
            raise


def command_update(args) -> int:
    from .engine import validate_site_manifest
    from .self_update import update_program, version_key

    try:
        if args.site_root:
            root = args.site_root.resolve()
        else:
            cwd = Path.cwd().resolve()
            root = next((p for p in (cwd, *cwd.parents) if (p / 'websmith.yaml').is_file()), None)
        if root is None:
            if args.offline:
                raise ValueError('Nessun sito trovato: eseguire update nella cartella del sito o usare --site-root.')
            result = update_program(args, None)
            if result is None:
                print('Nessun sito selezionato; nessuna regola aggiornata.')
                return 0
            return result
        marker_path = checked_path(root, '.websmith/project.json')
        inventory_path = checked_path(root, '.websmith/installed-files.json')
        checked_path(root, 'websmith.yaml')
        if not marker_path.is_file() or not inventory_path.is_file():
            raise ValueError('Sito non inizializzato: eseguire prima websmith init.')
        marker = read_object(marker_path)
        inventory = read_object(inventory_path)
        if marker.get('format_version') != 1 or marker.get('agent') not in {'codex', 'claude', 'none'}:
            raise ValueError('Metadati di inizializzazione non supportati.')
        if any(not isinstance(v, str) or len(v) != 64 or any(c not in '0123456789abcdef' for c in v) for v in inventory.values()):
            raise ValueError('Impronte dei file installati non valide.')
        _, errors = validate_site_manifest(str(root))
        if errors:
            raise ValueError('Manifest incompatibile:\n' + '\n'.join(errors))

        if not args.offline:
            result = update_program(args, root)
            if result is not None:
                return result
        instructions_version = marker.get('instructions_version')
        if instructions_version and version_key(instructions_version) > version_key(__version__):
            raise ValueError('Il sito contiene istruzioni di una versione più recente: nessuna regola sostituita.')

        writes = {}
        messages = []
        proposals = []
        for name, text in agent_files(marker['agent']).items():
            desired = text.encode('utf-8')
            target = checked_path(root, name)
            current = target.read_bytes() if target.exists() else None
            expected = inventory.get(name)
            if current == desired:
                inventory[name] = digest(desired)
                messages.append(f'Già aggiornato: {name}')
            elif name in BASE_GUIDES or current is None or (expected is not None and digest(current) == expected):
                if name in BASE_GUIDES and current is not None:
                    # Preserve previous bytes for recovery; these are not active overrides.
                    backup = f'.websmith/update-backups/{__version__}/{digest(current)}/{name}'
                    backup_path = checked_path(root, backup)
                    if backup_path.exists() and backup_path.read_bytes() != current:
                        raise ValueError(f'Copia di recupero già modificata: {backup}')
                    if not backup_path.exists():
                        writes[backup] = current
                    messages.append(f'Base precedente conservata in: {backup}')
                writes[name] = desired
                inventory[name] = digest(desired)
                messages.append(f'{"Aggiunta" if current is None else "Aggiornamento"}: {name}')
            else:
                proposal = f'.websmith/update-proposals/{__version__}/{name}'
                proposed_path = checked_path(root, proposal)
                if proposed_path.exists():
                    if proposed_path.read_bytes() != desired:
                        raise ValueError(f'Proposta già modificata: {proposal}. Conservarla altrove prima di riprovare.')
                else:
                    writes[proposal] = desired
                proposals.append(name)
                messages.append(f'Personalizzazione conservata: {name}; proposta: {proposal}')
                # Do not adopt the new hash until the proposal is actually installed.

        for name in BASE_GUIDES:
            local = root / name.replace('.md', '.local.md')
            if local.exists() or local.is_symlink():
                messages.append(f'Personalizzazioni locali conservate: {local.name}')
        marker['instructions_version'] = __version__
        marker['instruction_overrides'] = 'optional-local-files'
        marker['pending_instruction_updates'] = proposals
        marker_bytes = (json.dumps(marker, indent=2) + '\n').encode('utf-8')
        inventory['.websmith/project.json'] = digest(marker_bytes)
        inventory_bytes = (json.dumps(inventory, indent=2) + '\n').encode('utf-8')
        for name, data in (('.websmith/project.json', marker_bytes), ('.websmith/installed-files.json', inventory_bytes)):
            if (root / name).read_bytes() != data:
                writes[name] = data
        for message in messages:
            print(message)
        if args.dry_run:
            print(f'Anteprima: {len(writes)} file da scrivere. Nessun file modificato.')
        else:
            write_plan(root, writes)
            print(f'Istruzioni verificate con Websmith {__version__}: {len(writes)} file scritti.')
        if proposals:
            print('Integrazione manuale necessaria per i file personalizzati elencati. '
                  'Le proposte non sono attive; confrontarle con i file locali, poi ripetere update.')
        for legacy in ('.websmith/rules.md', 'EDITORIAL_GUIDE.md'):
            if (root / legacy).exists():
                print(f'File precedente conservato: {legacy}. Verificare eventuali rimandi o regole in conflitto.')
        print('Aggiornamento completato. Contenuti, template, CSS, output e file .local.md conservati.')
        return 0
    except (OSError, ValueError, zipfile.BadZipFile, subprocess.SubprocessError) as exc:
        print(f'Aggiornamento interrotto: {exc}')
        return 2
