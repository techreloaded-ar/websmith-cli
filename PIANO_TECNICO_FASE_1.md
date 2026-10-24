# Websmith — piano tecnico della prima fase

Data: 24 ottobre 2026. Stato: piano operativo; nessuna funzionalità ancora implementata.

## Obiettivo e decisioni già concordate

Installare il programma una volta e usarlo su cartelle sito indipendenti.
L'inizializzazione parte dalla cartella del sito: configurazione, guide e istruzioni
per gli agenti stanno accanto a `web/`. Il motore non va copiato integralmente in
ogni sito. I contenuti e le regole di composizione restano di proprietà del sito.

Il lavoro si svolge in questo progetto. Il progetto originale
`/Users/giovanni/progetti/websmith` è soltanto una fonte di riferimento.
Le prove useranno dati sintetici o copie separate e selezionate, senza credenziali.
Non sono previste pubblicazioni remote.

Questo piano attua i primi due passi del passaggio di contesto e prepara `init`.
Catalogo remoto, collaborazione Git, permessi editoriali e pubblicazione automatica
restano fasi successive. Multiutente in questa fase significa predisporre file di
progetto condivisibili, non introdurre account o un server di autenticazione.

## Evidenze nel codice originale

Riferimenti verificati il 24 ottobre 2026; prima di recuperare codice registrarne
una copia identificabile, perché l'originale può cambiare.

| Punto del codice `scripts/websmith.py` | Effetto attuale | Adattamento necessario |
| --- | --- | --- |
| `REPO_ROOT`, `WEBSITES_ROOT`, `SITE_SCHEMA_PATH` | Motore, siti e schema dipendono dalla posizione dello script | Separare risorse del programma e cartella del sito |
| `relative()` | Usa `relative_to(REPO_ROOT)` e può fallire per siti esterni | Diagnostica relativa al sito, con percorso assoluto quando esterno |
| `load_site_config()`, `config_for_root()` | Ricaricano il sito per nome, ricavato anche dal nome della cartella | Caricare e memorizzare la configurazione per percorso assoluto risolto |
| `load_component_catalog()`, `component_catalog_for_root()` | Catalogo memorizzato per nome sito | Isolare la cache per cartella, anche con nomi o ID uguali |
| `validate_site_manifest()` | Richiede ID uguale al nome passato e `$schema` risolto sullo schema centrale | Separare ID logico, nome cartella e ubicazione dello schema |
| `build_parser()`, `available_sites()` | Argomenti limitati ai siti dentro `websites/`; alcuni comandi scelgono TechReloaded | Risolvere il contesto prima dell'esecuzione, senza scegliere un sito estraneo |
| `command_resolve_page()`, `command_parse_component()` | Percorsi relativi interpretati dal repository del motore | Definire una base esplicita per modalità locale e compatibilità |
| `render_family_page()` con `current-html` | Cerca prima un HTML relativo al repository | Separare la risoluzione locale dalla compatibilità documentata |
| Comandi abbreviati TechReloaded | Restano specifici del sito | Preservarli nelle prove di compatibilità, senza renderli universali |

Lo schema attuale consente di dichiarare percorsi ma la validazione Python svolge
anche controlli sulle risorse e sul contenimento nella cartella sito. Vanno
conservati entrambi. Un sito precedente alla migrazione può essere ispezionabile
senza essere generabile: non va convertito implicitamente.

I riferimenti normativi letti sono `AGENTS.md`, `docs/WEBSMITH_CONTRACT.md`,
`docs/HELP.md` e `schemas/websmith-site.schema.json` dell'originale.
Il renderer deve continuare a validare prima di scrivere, verificare destinazioni
dei dati editoriali, collegamenti e immagini, e lasciare le traduzioni agli agenti.

## Contenuto dell'installazione nel sito

La seguente organizzazione è una proposta tecnica per l'implementazione, distinta
dalle decisioni dell'utente. Non seleziona ancora un canale di distribuzione o un agente.

```text
sito/
  .websmith/
    project.json
    rules.md
    installed-files.json
  AGENTS.md
  websmith.yaml
  COMPOSITION_GUIDE.md
  EDITORIAL_GUIDE.md           facoltativa
  contents/                   percorsi effettivi dichiarati nel manifest
  templates/
  media/
  web/
```

- `project.json`: versione del formato dell'inizializzazione e versione esatta
  richiesta del programma. La versione del formato `websmith.yaml` resta separata.
  La scelta dell'agente si registra solo quando sarà definito il relativo supporto.
- `rules.md`: unica copia locale delle regole comuni, distribuita con la versione
  del motore. Non contiene regole editoriali o visuali prese da altri siti.
- `installed-files.json`: elenco dei file gestiti e delle impronte del contenuto
  installato, per riconoscere modifiche locali durante una futura reinizializzazione.
  Non contiene percorsi assoluti del computer, credenziali o elenco degli utenti.
- `AGENTS.md`: breve punto di ingresso che rimanda alle regole comuni, al manifest,
  alla guida di composizione e, quando presente, alla guida editoriale.
- Le skill dell'agente conterranno istruzioni operative e rimandi alle stesse
  regole. Percorso e formato saranno definiti per l'agente scelto; nessuna seconda
  copia della politica comune. Questo piano non crea ancora una skill installabile.

I tre file di `.websmith/` vanno condivisi insieme ai sorgenti. Cache e file
temporanei futuri non devono essere necessari per ricostruire un sito.
Gli schemi autorevoli restano nella distribuzione del programma; una futura copia
locale per l'editor dovrà essere gestita come file versionato, non come alternativa
modificabile alla validazione del programma.

Un sito con manifest ma senza `.websmith/` deve continuare a essere riconosciuto:
inizializzazione dell'agente e riconoscimento dei sorgenti sono operazioni distinte.
Se è dichiarata una versione richiesta diversa da quella in esecuzione, le
operazioni di scrittura dovranno fermarsi con una spiegazione; nessun aggiornamento
o download implicito del programma.

## Riconoscimento della cartella sito

Introdurre un oggetto di contesto con cartella del sito, percorso del manifest,
modalità locale o di compatibilità e cartella delle risorse del programma.
Le funzioni comuni riceveranno questo contesto o il percorso del sito: non
ricostruiranno la posizione a partire da un nome.

Ordine proposto:

1. Un'opzione esplicita `--site-root <cartella>` seleziona il sito. Se il manifest
   manca o è errato, segnalare l'errore senza ripiegare su un altro sito.
2. Senza selezione esplicita, cercare `websmith.yaml` dalla cartella corrente verso
   i genitori; usare il primo trovato. Non cercare ricorsivamente tra cartelle figlie.
3. I comandi storici che specificano un nome sito continuano a risolverlo dentro
   una struttura `websites/` esplicitamente individuata per la compatibilità.
   Il nuovo programma non deve conoscere il percorso assoluto dell'originale.
4. In assenza di un sito individuabile, spiegare come indicarlo. I comandi generici
   non scelgono automaticamente TechReloaded fuori dalla modalità storica.

Se selettori locali e storici sono presenti insieme, verificare che identifichino
la stessa cartella oppure segnalare il conflitto. Un manifest locale invalido
interrompe la ricerca; non si passa silenziosamente a un manifest genitore.

L'ID nel manifest identifica il sito; non deve coincidere con il nome della sua
cartella locale. Due copie dello stesso sito devono poter convivere. Cache e
cataloghi vanno identificati per percorso risolto e invalidati tra esecuzioni
indipendenti; evitare uno stato globale che mescoli siti.

Nella modalità locale i percorsi dichiarati sono relativi alla cartella sito.
Anche gli argomenti relativi di `resolve-page` e `parse-component` saranno riferiti
al sito selezionato. Nella modalità storica resta la base del repository di prova,
come documentato oggi. HELP deve spiegare la differenza.

La validazione non deve dipendere dalla posizione fisica di `$schema` nel vecchio
repository: definire un identificatore stabile dello schema fornito dal programma
e riconoscere separatamente i riferimenti relativi storici nelle copie di prova.
Non scaricare schemi dalla rete e non accettare uno schema arbitrario in sostituzione
di quello del programma.

Per tutti i percorsi risolvere `..` e collegamenti simbolici prima di verificare
che restino nel sito. Applicare lo stesso criterio a sorgenti, template, asset e
destinazioni; includere `current_html` nella revisione. Errori di contenimento
devono precedere qualsiasi scrittura.

## Sequenza di implementazione e verifiche

1. **Preparare la base nel nuovo progetto.** Recuperare soltanto motore, schema,
   documentazione comune e dipendenze effettivamente usate. Registrare provenienza
   e impronte dei file; non copiare siti, configurazioni personali o workflow di
   pubblicazione. Preparare un sito sintetico completo e una sua copia nella
   struttura storica `websites/`. Conservare il comportamento iniziale come confronto.
2. **Separare contesto e risorse.** Implementare individuazione del sito, selezione
   esplicita, diagnostica esterna e caricamento per percorso. Verificare cartella
   corrente, sottocartella, nomi con spazi, manifest mancante o invalido e selettori
   in conflitto. Verificare due siti con lo stesso nome cartella o lo stesso ID.
3. **Adattare tutti i comandi.** Controllare ogni uso di `REPO_ROOT`, `WEBSITES_ROOT`
   e ricostruzione per nome; aggiornare HELP. Confrontare validazione e generazione
   tra sito autonomo e copia storica: HTML, metadati, lingue, componenti, CSS e asset.
   Un errore nei sorgenti deve lasciare invariati i file di output.
4. **Implementare `init` in un passo successivo.** Prima distinguere cartella vuota,
   sito con manifest e cartella con file preesistenti ma senza manifest. In
   quest'ultimo caso proporre una diagnosi, senza dedurre una migrazione.
   Chiedere l'agente soltanto in modalità interattiva; per gli script prevedere
   una selezione esplicita. Prima di scrivere controllare tutti i conflitti.
   Preservare `AGENTS.md`, skill e guide esistenti; file modificati non vanno
   sovrascritti. Ripetere `init` senza variazioni non deve cambiare i file.
5. **Scegliere e verificare la distribuzione.** Il codice esaminato è Python e usa
   PyYAML, Beautiful Soup e jsonschema. Un pacchetto Python con comando `websmith`
   è un candidato da valutare, non una decisione già presa. Verificare dipendenze
   effettive, versioni riproducibili, risorse incluse e installazione in ambiente
   isolato prima di scegliere il canale.

La prima consegna eseguibile comprende i passi 1–3. La verifica finale dell'intera
prima fase aggiungerà inizializzazione, modifica di un Markdown, validazione e
generazione di `web/` da un sito esterno al motore, poi una seconda inizializzazione
con modifiche locali da preservare. Nessuna prova scrive nell'originale.

## Scelte ancora aperte

Restano da scegliere gli agenti iniziali, il loro percorso skill, il canale di
installazione, il sito e l'hosting del pilota. Repository separati, catalogo,
autorizzazioni e gestione degli HTML generati in Git restano proposte successive.
Queste scelte non bloccano la separazione tra motore e cartella sito.
