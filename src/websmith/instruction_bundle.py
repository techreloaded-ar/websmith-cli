"""Inventory of external skills and compatibility paths (no embedded rules)."""

SKILL_NAMES = ('editor', 'composer', 'tov', 'mail', 'collaboration')
GUIDE_SOURCES = {
    'EDITORIAL_RULES.md': 'skills/editor/references/EDITORIAL_RULES.md',
    'COMPOSITION_GUIDE.md': 'skills/composer/references/COMPOSITION_GUIDE.md',
    'TONE_OF_VOICE.md': 'skills/tov/references/TONE_OF_VOICE.md',
}
SKILL_FILES = tuple(f'skills/{name}/SKILL.md' for name in SKILL_NAMES) + tuple(GUIDE_SOURCES.values()) + (
    'skills/mail/references/MAIL_GUIDE.md',
    'skills/mail/scripts/check-mail.py',
    'skills/collaboration/references/COLLABORATION_GUIDE.md',
)
AGENT_FILES = ('agent-config/AGENTS.md', 'agent-config/CLAUDE.md',
               'agent-config/WEBSMITH_SITE_SKILL.md')
LEGACY_FILES = tuple('rules/' + name for name in (
    'AGENTS.md', 'COMPOSITION_GUIDE.md', 'TONE_OF_VOICE.md',
    'EDITORIAL_RULES.md', 'CLAUDE.md', 'WEBSMITH_SITE_SKILL.md',
)) + ('docs/HELP.md', 'docs/WEBSMITH_CONTRACT.md')
# Old executables still download the legacy projections. New executables use
# canonical sources, plus the user-facing documentation still under resources/.
SOURCE_PATHS = {name: 'src/websmith/resources/' + name
                for name in ('docs/HELP.md', 'docs/WEBSMITH_CONTRACT.md')}
SOURCE_PATHS.update({name: name for name in (*AGENT_FILES, *SKILL_FILES)})


def legacy_projections(root):
    """Generate the old download layout from the authoritative sources."""
    files = {'rules/' + name: (root / source).read_text(encoding='utf-8')
             for name, source in GUIDE_SOURCES.items()}
    for name in ('CLAUDE.md', 'WEBSMITH_SITE_SKILL.md'):
        files['rules/' + name] = (root / 'agent-config' / name).read_text(encoding='utf-8')
    dispatcher = (root / 'agent-config/AGENTS.md').read_text(encoding='utf-8')
    mail = (root / 'skills/mail/references/MAIL_GUIDE.md').read_text(encoding='utf-8')
    files['rules/AGENTS.md'] = dispatcher + '\n## Posta nelle installazioni precedenti\n\n' + mail
    return files
