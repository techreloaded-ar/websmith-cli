# HELP — Comandi Websmith

In chat scrivi `HELP` per l'elenco oppure `HELP render-page` per un comando specifico.
Dal terminale, nella cartella principale del repository:

```bash
python3 scripts/websmith.py HELP
python3 scripts/websmith.py HELP render-page
```

È disponibile anche `help` minuscolo. `HELP` mostra questa guida senza modificare
file; `HELP <comando>` mostra la sintassi e tutte le opzioni correnti della CLI.
Puoi ottenere le stesse opzioni con `python3 scripts/websmith.py <comando> --help`.

## Come leggere gli esempi

Ogni riga sotto va preceduta da `python3 scripts/websmith.py `.
Gli esempi usano TechReloaded: sostituisci sito, lingua e pagina con quelli
del tuo sito, consultando `websites/<sito>/COMPOSITION_GUIDE.md`.
I siti possono essere in fasi di migrazione diverse: la presenza nella CLI
non garantisce che abbiano tutti i sorgenti e i contratti necessari.

`page_id` è l'identificativo canonico nel front matter Markdown, non il nome
del file HTML. Nei comandi con `--site`, il valore predefinito è `techreloaded`:
specifica sempre il sito quando lavori altrove.

## Esplorazione e verifica

Questi comandi leggono i file senza rigenerare il sito.

| Comando | A cosa serve | Esempio d'uso |
| --- | --- | --- |
| `HELP [comando]` | Mostra questa guida o le opzioni di un comando. | `HELP render-page` |
| `inspect <sito>` | Esamina la struttura del sito. | `inspect techreloaded` |
| `validate-site <sito>` | Valida il manifest `websmith.yaml` e le risorse locali dichiarate. | `validate-site techreloaded` |
| `validate-frontmatter <sito>` | Controlla il front matter YAML dei sorgenti Markdown. | `validate-frontmatter techreloaded` |
| `validate-page <sito> <lingua> <pagina>` | Valida il contratto di una pagina prima del rendering. | `validate-page techreloaded ita prodotti/archetipo` |
| `validate-pages <sito> [--lang <lingua>]` | Valida le pagine del sito; senza `--lang` controlla tutte le lingue. | `validate-pages techreloaded --lang ita` |
| `resolve-page <sito> <output>` | Risale dall'HTML al Markdown canonico e indica il comando di rendering. Usa un percorso assoluto o relativo alla radice del repository. | `resolve-page techreloaded websites/techreloaded/web/ita/prodotti/archetipo/index.html` |
| `sync-translations <page_id> [--site <sito>]` | Controlla struttura e tracciabilità delle traduzioni esistenti. Non traduce e non crea file mancanti. | `sync-translations archetipo --site techreloaded` |
| `parse-component <sito> <file> <componente>` | Analizza i blocchi di un componente nel Markdown senza generare HTML. | `parse-component techreloaded websites/techreloaded/contents/ita/prodotti/archetipo.md highlights-box-sx` |

## Generazione e famiglie di pagine

Questi comandi possono scrivere HTML, CSS e asset nell'output del sito.
Il rendering valida prima i sorgenti e si ferma in caso di violazioni del contratto.

| Comando | A cosa serve | Esempio d'uso |
| --- | --- | --- |
| `render-page <page_id> [--site <sito>] [--lang <lingua>] [--all-langs]` | Genera una pagina nell'output configurato. Senza opzioni di lingua usa quella canonica; `--all-langs` genera tutte le lingue configurate con un sorgente esistente. | `render-page archetipo --site techreloaded --all-langs` |
| `render-root-index [--site <sito>]` | Genera il reindirizzamento iniziale alle lingue, secondo il manifest del sito. | `render-root-index --site techreloaded` |
| `validate-family <family_id> [--site <sito>] [--no-render]` | Controlla una famiglia multilingue individuata dal prefisso dell'ID canonico e ne rigenera le pagine. Con `--no-render` valida i sorgenti e ispeziona l'HTML esistente senza rigenerarlo. | `validate-family archetipo --site techreloaded --no-render` |

Per una sola lingua usa, per esempio, `render-page archetipo --site techreloaded --lang ita`.
Scegli `--lang` oppure `--all-langs` secondo l'obiettivo.

## Scorciatoie di compatibilità TechReloaded

Questi comandi sono specifici di TechReloaded e scrivono l'output generato.
Accettano `--lang`, con valore predefinito `ita`; usa solo lingue con sorgenti disponibili.
Per gli altri siti usa `render-page` con l'ID della pagina e `--site`.

| Comando | A cosa serve | Esempio d'uso |
| --- | --- | --- |
| `render-index` | Genera la homepage. | `render-index --lang ita` |
| `render-archetipo` | Genera la pagina del prodotto Archetipo. | `render-archetipo --lang ita` |
| `render-archetipo-beta` | Genera la pagina beta di Archetipo. | `render-archetipo-beta --lang ita` |
| `render-documentazione` | Genera la documentazione di Archetipo. | `render-documentazione --lang ita` |
| `render-team` | Genera l'indice del team. | `render-team --lang ita` |
| `render-team-pages` | Genera le schede delle persone; `--slug` limita l'operazione a una persona. | `render-team-pages --lang ita --slug giovanni-puliti` |

## Flusso tipico dopo una modifica editoriale

1. Modifica il Markdown canonico e aggiorna le traduzioni esistenti previste dal sito.
2. Controlla manifest, front matter, pagina e struttura delle traduzioni.
3. Rigenera le lingue interessate e verifica HTML, link e asset.

Esempio per Archetipo:

```bash
python3 scripts/websmith.py validate-site techreloaded
python3 scripts/websmith.py validate-frontmatter techreloaded
python3 scripts/websmith.py validate-pages techreloaded
python3 scripts/websmith.py sync-translations archetipo --site techreloaded
python3 scripts/websmith.py render-page archetipo --site techreloaded --all-langs
```

Questi comandi operano localmente. La pubblicazione remota è gestita dal flusso Git
del progetto, esterno a questa CLI.
