"""Conservative initialization using externally distributed instructions."""
from __future__ import annotations

import hashlib
import json
import re
import sys
import tempfile
import unicodedata
import zipfile
from pathlib import Path
from urllib.parse import urlparse

import yaml

from . import __version__
from .instruction_bundle import GUIDE_SOURCES, SKILL_FILES, SKILL_NAMES

BASE_GUIDES = ('COMPOSITION_GUIDE.md', 'TONE_OF_VOICE.md', 'EDITORIAL_RULES.md')
MANAGED_GUIDES = (*BASE_GUIDES, *GUIDE_SOURCES.values())


def slug(value: str) -> str:
    ascii_name = unicodedata.normalize('NFKD', value).encode('ascii', 'ignore').decode()
    return re.sub(r'[^a-z0-9]+', '-', ascii_name.lower()).strip('-') or 'sito'


def ask(label: str, default: str) -> str:
    return input(f'{label} [{default}]: ').strip() or default


def agent_files(agent: str, resources: dict[str, str] | None = None) -> dict[str, str]:
    if resources is None:
        from .rule_source import load
        resources, _ = load(offline=True)
    files = {'AGENTS.md': resources['agent-config/AGENTS.md']}
    files.update({name: resources[name] for name in SKILL_FILES})
    # Derived compatibility copies preserve existing manifests and old prompts.
    files.update({name: resources[source] for name, source in GUIDE_SOURCES.items()})
    if agent in {'codex', 'claude'}:
        directory = '.agents' if agent == 'codex' else '.claude'
        if agent == 'claude':
            files['CLAUDE.md'] = resources['agent-config/CLAUDE.md']
        files[f'{directory}/skills/websmith-site/SKILL.md'] = resources['agent-config/WEBSMITH_SITE_SKILL.md']
        for name in SKILL_NAMES:
            canonical = resources[f'skills/{name}/SKILL.md']
            # Keep trigger metadata in the agent's discovery directory; all
            # operational content and references live only under skills/.
            frontmatter = canonical.split('---', 2)[:2]
            adapter = '---'.join(frontmatter) + '---\n\n'
            adapter += f'Leggere e applicare [la skill {name}](../../../skills/{name}/SKILL.md). '
            adapter += 'Individuare la radice del sito e leggere AGENTS.md prima di operare.\n'
            files[f'{directory}/skills/{name}/SKILL.md'] = adapter
    return files


def starter(name: str, site_id: str, url: str, language: str) -> dict[str, str]:
    """Return site-owned starter sources; no organization-specific copy."""
    manifest = {
        '$schema': 'https://websmith.local/schemas/websmith-site.schema.json',
        'version': 1,
        'site': {'id': site_id, 'name': name, 'status': 'active', 'base_url': url},
        'paths': dict(composition_guide='COMPOSITION_GUIDE.md', contents='contents', templates='templates/html', components='templates/html/components', component_catalog='templates/html/components/catalog.yaml', css='templates/CSS', media='media', output='web'),
        'content': {'canonical_language': language, 'languages': {language: {'html_lang': language, 'source': f'contents/{language}', 'output': f'web/{language}'}}, 'page_directories': ['pages']},
        'frontmatter': {'required': ['slug', 'status'], 'canonical_page_required': ['id', 'template']},
        'routing': {'output_overrides': {'home': 'index.html'}},
        'templates': {'default': 'page.html', 'profiles': {'page': {'file': 'page.html', 'content_target': 'main'}}},
        'styles': {'publish': {'templates/CSS/main.css': 'web/shared/css/main.css'}},
        'assets': {'shared_images': {'source': 'templates/images', 'output': 'web/shared/images'}, 'editorial_sources': ['media'], 'resolution_roots': ['media', 'templates/images']},
        'brand': {'organization': name, 'email': 'info@example.test', 'logo': 'templates/images/logo.svg', 'published_logo': 'web/shared/images/logo.svg'},
        'root_redirect': {'enabled': True, 'template': 'templates/html/root.html', 'output': 'web/index.html', 'default_language': language, 'destinations': {language: f'{language}/index.html'}, 'alternates': {language: language}, 'title': name, 'description': 'Sito di esempio da personalizzare.', 'language_labels': {language: language}},
    }
    metadata = dict(id='home', slug='home', status='draft', template='page.html', title=name)
    page_body = ('## Example page\n\nReplace this text with your site content.\n' if language == 'en' else '## Pagina di esempio\n\nSostituisci questo testo con i contenuti del tuo sito.\n')
    return {
        'websmith.yaml': yaml.safe_dump(manifest, allow_unicode=True, sort_keys=False),
        f'contents/{language}/pages/home.md': '---\n' + yaml.safe_dump(metadata, allow_unicode=True, sort_keys=False) + '---\n\n' + page_body,
        'templates/html/page.html': '''<!doctype html>
<html lang="it"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title data-websmith-text="page.title">Titolo di esempio</title>
<link rel="stylesheet" href="../../shared/css/main.css"></head>
<body><header><h1 data-websmith-text="page.title">Titolo di esempio</h1></header>
<main data-websmith-body><p>Anteprima del contenuto.</p></main></body></html>
''',
        'templates/html/root.html': '''<!doctype html>
<html lang="it"><head><meta charset="utf-8"><title>Esempio</title>
<meta name="description" content="Esempio"><link rel="canonical" href="https://example.test/">
<!-- websmith:alternates --><!-- /websmith:alternates -->
<script id="websmith-root-redirect"></script></head><body>
<!-- websmith:language-links --><!-- /websmith:language-links -->
</body></html>
''',
        'templates/html/components/catalog.yaml': '''components:
  - name: note
    owned_by: page
    layout_role: block
    fields:
      required: [body]
    render:
      template: note.html
      selector: .note
''',
        'templates/html/components/note.html': '<aside class="note" data-websmith-markdown="body">Nota di esempio.</aside>\n',
        'templates/CSS/main.css': 'body { max-width: 60rem; margin: 3rem auto; padding: 0 1rem; font-family: system-ui, sans-serif; line-height: 1.6; }\n',
        'templates/images/logo.svg': '<svg xmlns="http://www.w3.org/2000/svg" width="64" height="64" viewBox="0 0 64 64"><rect width="64" height="64" rx="12" fill="#334155"/></svg>\n',
        'media/.gitkeep': '',
        'web/.gitkeep': '',

    }


def install_files(root: Path, files: dict[str, str]) -> None:
    """Preflight every path, then exclusively create files. Never replace a file."""
    for name in files:
        target = root / name
        if target.exists() or target.is_symlink():
            raise ValueError(f'File già presente: {name}. Nessun file è stato modificato.')
        for parent in target.parents:
            if parent == root:
                break
            if parent.is_symlink() or (parent.exists() and not parent.is_dir()):
                raise ValueError(f'Percorso incompatibile: {parent.relative_to(root)}')
    created: list[Path] = []
    directories: list[Path] = []
    try:
        for name, text in files.items():
            target = root / name
            missing = []
            parent = target.parent
            while parent != root and not parent.exists():
                missing.append(parent)
                parent = parent.parent
            for parent in reversed(missing):
                parent.mkdir()
                directories.append(parent)
            with target.open('x', encoding='utf-8', newline='\n') as stream:
                created.append(target)
                stream.write(text)
    except OSError:
        for target in reversed(created):
            target.unlink()
        for directory in reversed(directories):
            directory.rmdir()
        raise


def command_init(args) -> int:
    from .engine import validate_site_manifest

    root = (args.site_root or Path.cwd()).resolve()
    if not root.is_dir():
        print('La cartella deve già esistere: apri il terminale nella cartella scelta.')
        return 2
    if (root / '.websmith/project.json').is_file():
        try:
            marker = json.loads((root / '.websmith/project.json').read_text(encoding='utf-8'))
            if not isinstance(marker, dict) or marker.get('format_version') != 1:
                raise ValueError('Formato di inizializzazione non supportato')
        except (OSError, ValueError) as exc:
            print(f'Metadati di inizializzazione non validi: {exc}. Nessun file modificato.')
            return 2
        print('Websmith è già inizializzato. File e modifiche locali preservati.')
        return 0
    existing = (root / 'websmith.yaml').exists()
    if (root / 'websmith.yaml').is_symlink():
        print('Il manifest non può essere un collegamento simbolico durante init.')
        return 2
    if existing:
        _, errors = validate_site_manifest(str(root))
        if errors:
            print('Sito esistente incompatibile; nessun file modificato:\n' + '\n'.join(errors))
            return 2
    else:
        entries = [p for p in root.iterdir() if p.name not in {'.git', '.DS_Store'}]
        if entries:
            print('Cartella non vuota senza websmith.yaml: nessuna migrazione automatica. Usa una cartella vuota.')
            return 2
    interactive = not args.yes and sys.stdin.isatty()
    if not args.yes and not interactive:
        print('Per uso non interattivo indica --yes e le opzioni desiderate. Vedi websmith init --help.')
        return 2
    try:
        agent = args.agent or (ask('Agente: codex, claude, none', 'codex') if interactive else 'none')
        if agent not in {'codex', 'claude', 'none'}:
            raise ValueError('Agente non supportato. Usa codex, claude oppure none.')
        from .rule_source import load
        resources, revision = load(offline=getattr(args, "offline", False))
        files = agent_files(agent, resources)
        if existing:
            # An existing entry point belongs to the site; provide instructions without editing it.
            files = {name: text for name, text in files.items() if not (root / name).exists() and not (root / name).is_symlink()}
        else:
            name = args.name or (ask('Nome del sito', root.name) if interactive else root.name)
            site_id = args.id or (ask('Identificativo del sito', slug(name)) if interactive else slug(name))
            url = args.url or (ask('Indirizzo del sito (anche provvisorio)', 'https://example.test') if interactive else 'https://example.test')
            language = args.language or (ask('Lingua iniziale: it oppure en', 'it') if interactive else 'it')
            if not name.strip() or not re.fullmatch(r'[a-z0-9][a-z0-9-]*', site_id):
                raise ValueError('Nome vuoto o identificativo non valido: usa lettere minuscole, numeri e trattini.')
            parsed = urlparse(url)
            if parsed.scheme not in {'http', 'https'} or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
                raise ValueError('Indirizzo non valido: usa un URL http/https senza credenziali, query o frammenti.')
            if language not in {'it', 'en'}:
                raise ValueError('Lingue iniziali supportate: it, en.')
            files.update(starter(name, site_id, url.rstrip('/'), language))
            # Validate the complete starter before writing anything into the chosen directory.
            with tempfile.TemporaryDirectory(prefix='websmith-init-') as directory:
                stage = Path(directory)
                install_files(stage, files)
                _, errors = validate_site_manifest(str(stage))
                if errors:
                    raise ValueError('Configurazione iniziale non valida:\n' + '\n'.join(errors))
        files['.websmith/project.json'] = json.dumps({'format_version': 1, 'websmith_version': __version__, 'agent': agent, 'instructions_revision': revision}, indent=2) + '\n'
        inventory = {name: hashlib.sha256(text.encode('utf-8')).hexdigest() for name, text in files.items()}
        files['.websmith/installed-files.json'] = json.dumps(inventory, indent=2) + '\n'
        install_files(root, files)
    except (ValueError, OSError, zipfile.BadZipFile, EOFError, KeyboardInterrupt) as exc:
        print(f'Inizializzazione interrotta: {exc}')
        return 2
    print(f'Websmith inizializzato in {root}. Agente: {agent}.')
    if existing:
        print('Sorgenti e istruzioni preesistenti preservati. Leggere AGENTS.md e le guide del sito.')
    else:
        print('Pagina di esempio creata. Personalizzala, poi esegui:\n  websmith validate-site\n  websmith validate-pages\n  websmith render-page home\n  websmith render-root-index\nApri web/index.html nel browser.')
    return 0
