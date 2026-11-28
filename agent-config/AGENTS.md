# Istruzioni per questo sito Websmith

## Scegliere la capacità

Identificare la radice del sito e leggere il suo `websmith.yaml`. Usare le skill
in `skills/`, leggendo il relativo `SKILL.md` prima di svolgere il lavoro:

| Richiesta | Skill |
| --- | --- |
| Revisionare un testo esistente | `skills/editor/SKILL.md` |
| Modificare pagine, template, componenti, CSS, asset; validare e generare HTML | `skills/composer/SKILL.md` |
| Definire o modificare voce, pubblico e lessico; applicare il profilo | `skills/tov/SKILL.md` |
| «C'è posta per me?», controllo messaggi e allegati | `skills/mail/SKILL.md` |

Combinare le skill necessarie: una revisione con aggiornamento della pagina usa
editor, tov e composer. Le traduzioni seguono per ora composer. Per scrivere nuovi
testi leggere comunque il profilo tov e le regole editoriali; i limiti dell'editor
si applicano alla revisione di testi già scritti. Non considerare gli esempi o le
proposte da confermare come preferenze approvate.

## Regole e personalizzazioni

Le regole autorevoli appartengono alle skill. Leggere prima la base e poi
l'eventuale personalizzazione nella **radice del sito**:

| Base della skill | Personalizzazione del sito |
| --- | --- |
| `skills/editor/references/EDITORIAL_RULES.md` | `EDITORIAL_RULES.local.md` |
| `skills/composer/references/COMPOSITION_GUIDE.md` | `COMPOSITION_GUIDE.local.md` |
| `skills/tov/references/TONE_OF_VOICE.md` | `TONE_OF_VOICE.local.md` |

I file `.local.md` integrano le basi e prevalgono sui punti modificati. Se assenti,
usare la base senza segnalare errori o creare file vuoti. Quando l'utente modifica
le regole del sito, scrivere solo differenze e aggiunte nel relativo `.local.md`,
conservando le personalizzazioni esistenti. Non modificare le basi distribuite.

Se il manifest indica una diversa guida di composizione, consultarla insieme
alla sua variante `.local.md`, se presente, e conservarvi le scelte del sito.
Non migrare implicitamente sorgenti o configurazioni di siti esistenti.

Le guide omonime nella radice sono copie di compatibilità gestite da Websmith;
non mantenerle manualmente. Nelle installazioni precedenti senza `skills/`,
leggere queste guide prima delle rispettive varianti `.local.md`.

## Installazione, aggiornamento e aiuto

Per inizializzazione e aggiornamento consultare `websmith HELP init` e
`websmith HELP update`. Conservare contenuti e personalizzazioni e usare
`websmith update --dry-run` per verificare la migrazione. Per l'aiuto generale
consultare `websmith HELP` o `websmith HELP guida`.

La pubblicazione remota richiede una richiesta dell'utente e il flusso del sito.
Conservare le modifiche dei collaboratori.
