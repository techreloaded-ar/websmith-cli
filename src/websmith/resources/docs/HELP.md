# HELP — Comandi Websmith

Usare `websmith HELP` (oppure `websmith help`) per questa guida e
`websmith HELP render-page` per le opzioni correnti di un comando.
Anche `websmith render-page --help` mostra le opzioni senza modificare file.
In chat, una richiesta HELP serve a spiegare i comandi, non a eseguirli.

## Selezionare il sito

Il percorso ordinario parte dalla cartella del sito con `websmith.yaml` o da una
sua sottocartella. Non serve collocare il sito nel repository del programma.
Per sceglierlo da un'altra posizione mettere l'opzione globale prima del comando:

```bash
websmith --site-root /percorso/del/sito validate-site
websmith --site-root /percorso/del/sito render-page home
```

`page_id` è l'identificativo canonico del front matter, non il nome dell'HTML.
Lingue, percorsi e componenti dipendono dal manifest e dal catalogo del sito.
Leggere `AGENTS.md` e la guida di composizione indicata dal manifest.

## Creare un sito e preparare le istruzioni

```bash
websmith init
websmith init --yes --name "Il mio sito" --agent codex
```

`init` richiede una cartella vuota oppure un sito con manifest valido; non
sovrascrive file. Agenti: `codex`, `claude`, `none`. Lingue iniziali: `it`, `en`.
Le opzioni complete sono in `websmith init --help`.

I modelli Markdown esterni sono copiati nella radice del sito come `AGENTS.md`,
`COMPOSITION_GUIDE.md`, `TONE_OF_VOICE.md` ed `EDITORIAL_RULES.md`. Le istruzioni
specifiche Codex/Claude rimandano ad `AGENTS.md`. Websmith non installa o avvia
l'agente, non collega un abbonamento AI e non pubblica il sito.

Le guide esistenti sono preservate. Un sito già inizializzato non viene migrato
automaticamente: i vecchi `.websmith/rules.md` ed `EDITORIAL_GUIDE.md` possono
restare presenti, ma nei nuovi siti non vengono creati.

## Ispezione e validazione

Nelle righe con `SITO` obbligatorio usare il percorso assoluto della cartella del
sito. È una differenza ancora presente nella sintassi dei comandi: non omettere
quel parametro e non sostituirlo con `--site-root` da solo.

| Comando | Scopo | Esempio |
| --- | --- | --- |
| `inspect [SITO]` | Esamina la struttura senza scrivere output. | `websmith inspect` |
| `validate-site [SITO]` | Controlla manifest e risorse dichiarate. | `websmith validate-site` |
| `validate-frontmatter [SITO]` | Controlla il front matter YAML. | `websmith validate-frontmatter` |
| `validate-pages [SITO] [--lang LINGUA]` | Valida le pagine; per impostazione predefinita tutte le lingue. | `websmith validate-pages` |
| `validate-page SITO LINGUA PAGINA` | Valida una pagina. | `websmith validate-page /percorso/del/sito it pages/home` |
| `resolve-page SITO OUTPUT` | Risale dall'HTML al Markdown canonico. | `websmith resolve-page /percorso/del/sito /percorso/del/sito/web/it/index.html` |
| `parse-component SITO FILE COMPONENTE` | Analizza i blocchi di un componente. | `websmith parse-component /percorso/del/sito /percorso/del/sito/contents/it/pages/home.md note` |
| `sync-translations PAGE_ID [--site SITO]` | Controlla struttura e tracciabilità delle traduzioni; non traduce e non sincronizza Git. | `websmith sync-translations home` |

Gli esempi `it`, `home` e `note` si riferiscono al sito iniziale; sostituirli con
valori esistenti nel proprio sito. In `resolve-page` e `parse-component` i percorsi
relativi dei file sono riferiti alla cartella di esecuzione: preferire gli assoluti.

## Generazione

Questi comandi possono scrivere HTML, CSS e asset. La generazione controlla i
sorgenti e si ferma in caso di violazioni del contratto.

| Comando | Scopo | Esempio |
| --- | --- | --- |
| `render-page PAGE_ID [--site SITO] [--lang LINGUA] [--all-langs]` | Genera la pagina; senza lingua usa quella canonica. | `websmith render-page home --all-langs` |
| `render-root-index [--site SITO]` | Genera l'ingresso alle lingue secondo il manifest. | `websmith render-root-index` |
| `validate-family FAMILY_ID [--site SITO] [--no-render]` | Controlla una famiglia multilingue individuata dal prefisso degli ID e ne rigenera le pagine. Con `--no-render` controlla i sorgenti e l'HTML esistente senza rigenerare. | `websmith validate-family prodotto --no-render` |

Scegliere `--lang` oppure `--all-langs`. Le traduzioni devono essere già scritte
nei sorgenti: `--all-langs` genera quelle esistenti senza tradurre.

### Flusso tipico

1. Modificare il Markdown canonico e aggiornare le traduzioni esistenti.
2. Validare manifest, front matter, pagine e allineamento delle traduzioni.
3. Generare le pagine e le lingue interessate e verificare HTML, link e asset.

Per il sito minimo:

```bash
websmith validate-site
websmith validate-frontmatter
websmith validate-pages
websmith sync-translations home
websmith render-page home --all-langs
websmith render-root-index
```

Aprire `web/index.html` nel browser. Modifiche durature nei sorgenti, non soltanto
nell'HTML generato. Le note alla redazione non devono entrare nel contenuto pubblicabile.
La pubblicazione remota è un passaggio separato, configurato per il singolo sito.

## Importazione HTTP

```bash
websmith import https://www.esempio.it
websmith import https://www.esempio.it --output imports/seconda-prova
```

Acquisisce HTML pubblico e risorse sotto `imports/NOME-DOMINIO/`, con `originals/`,
`preview/`, `REPORT.md` e `report.json`. Leggere il rapporto prima della conversione.
Rispetta robots.txt e non esegue JavaScript. Non converte in Markdown e non modifica
i sorgenti del sito. Una destinazione esistente viene rifiutata.

Opzioni: `--output`, `--max-pages`, `--max-depth`, `--max-assets`,
`--max-file-bytes`, `--max-total-bytes`, `--timeout`, `--delay`.
Un sito Websmith già disponibile si copia come progetto e si valida: non esiste
un comando `import folder`. Per un progetto nuovo eseguire `init` prima dell'import.

## Acquisizione browser manuale

```bash
websmith import https://www.esempio.it --browser
```

Apre Chrome in una sessione dedicata. Controllare e scorrere la pagina, poi tornare
al terminale e premere Invio per salvarla. Indicare il prossimo URL dello stesso
sito oppure Invio per terminare. `--single-page` salva soltanto la prima pagina.

La copia è in `imports/NOME-DOMINIO-browser/`, con `originals/`, `rendered/`,
`screenshots/`, `preview/`, `REPORT.md` e `report.json`. Salva le risorse caricate
dal browser senza download supplementari delle risorse bloccate. Non esporta il
profilo e non risolve automaticamente verifiche anti-bot. Per una nuova sessione
scegliere un nuovo `--output`. La conversione resta un lavoro successivo dell'agente.

Richiede un terminale interattivo e un browser installato. Per usare Chromium:

```bash
websmith browser-install
websmith import https://www.esempio.it --browser --browser-channel chromium
```

`websmith browser-install --check` verifica il driver incluso senza installare
Chromium. È disponibile anche `--browser-channel msedge` se Edge è installato.

## Compatibilità con la struttura storica

Il programma conserva selettori di sito per la struttura `websites/<nome>/` e
scorciatoie specifiche TechReloaded. Non sono il modello richiesto ai nuovi siti.
I nomi di sito e `--site NOME` risolvono la struttura storica, non una cartella
locale arbitraria. Non combinare un nome storico con un `--site-root` diverso.
L'assenza di un selettore nei comandi generici non sceglie automaticamente
TechReloaded: occorre un sito locale individuabile o una selezione esplicita.

Dalla radice di un progetto con struttura storica, per esempio:

```bash
websmith validate-site techreloaded
websmith render-page archetipo --site techreloaded --all-langs
```

Le seguenti scorciatoie restano specifiche TechReloaded e possono scrivere output.
Accettano `--lang`, con valore storico predefinito `ita`:

| Comando | Scopo |
| --- | --- |
| `render-index` | Homepage TechReloaded. |
| `render-archetipo` | Pagina Archetipo. |
| `render-archetipo-beta` | Pagina beta Archetipo. |
| `render-documentazione` | Documentazione Archetipo. |
| `render-team` | Indice del team. |
| `render-team-pages [--slug SLUG]` | Schede delle persone, eventualmente una sola. |

Usarle soltanto se i sorgenti e i contratti del sito le supportano. Per i siti
indipendenti usare i comandi generici e gli identificativi del proprio manifest.

Per lo sviluppo nel repository, `python3 scripts/websmith.py` resta un lanciatore
di compatibilità: richiede il pacchetto installato nell'ambiente Python scelto.
Non è un requisito per chi usa l'eseguibile autonomo `websmith`.
