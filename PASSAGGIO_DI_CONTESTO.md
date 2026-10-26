# Websmith CLI — passaggio di contesto

Aggiornato il 24 ottobre 2026.

## Stato e confini del lavoro

Questo è il nuovo progetto indipendente `/Users/giovanni/progetti/websmith-cli`.
Il nome è stato proposto per distinguere il tool locale da un servizio cloud.
Il progetto originale `/Users/giovanni/progetti/websmith` non deve essere modificato.
Può essere letto come riferimento e come base da cui recuperare il codice utile.
Non copiare indiscriminatamente siti, file locali, credenziali o modifiche estranee.

Al momento del passaggio iniziale non era stata implementata alcuna funzionalità
nel nuovo progetto; vedere l’avanzamento sotto per lo stato corrente. Nel progetto originale è stata preparata una proposta di distribuzione
e collaborazione, poi ampliata per spiegare il lessico tecnico.

## Obiettivo complessivo

Websmith deve diventare un tool installabile, multiutente e multisito:

- ciascun utente lavora localmente sui siti che sceglie ed è autorizzato a modificare;
- più utenti possono condividere le modifiche di uno stesso sito senza perdere lavoro;
- un sito può nascere in locale e successivamente essere condiviso e pubblicato;
- la pubblicazione online avviene automaticamente dopo i controlli previsti;
- il programma resta deterministico: non inventa contenuti o traduzioni.

## Decisione principale concordata

L'utente ha corretto la proposta iniziale: il punto di partenza è la cartella del
sito, dentro cui Websmith viene inizializzato, come nell'esperienza di ARchetipo.
Regole, skill e configurazione devono stare accanto alla cartella `web/`.
Non si vuole obbligare l'utente a collocare il sito nel repository del motore.

Distinguere due operazioni:

1. installazione del programma Websmith sul computer;
2. inizializzazione di Websmith nel progetto sito, con regole, skill e configurazione.

La collocazione esatta del motore e il canale di distribuzione sono ancora da
progettare. Non è stato deciso di copiarne integralmente il codice in ogni sito.

Struttura indicativa proposta, non ancora uno schema implementato:

```text
sito-xy/
├── .websmith/          configurazione e versione di Websmith
├── AGENTS.md           istruzioni per lavorare sul sito
├── [skill per agente]  percorso da definire per lo strumento scelto
├── websmith.yaml       impostazioni del sito
├── COMPOSITION_GUIDE.md
├── EDITORIAL_GUIDE.md  facoltativa
├── contents/           contenuti Markdown
├── templates/          modelli HTML, componenti e CSS
├── media/              immagini e altri materiali
└── web/                sito generato da pubblicare
```

Multisito significa poter gestire più cartelle sito indipendenti con lo stesso
programma, senza scaricare necessariamente tutti i siti.

## Piano della prima fase

Dobbiamo realizzare l'inizializzazione di Websmith nella cartella di un sito,
preservando i comandi e il comportamento dei siti attuali durante la transizione.
Questo vincolo non autorizza modifiche al progetto originale: le verifiche devono
usare il nuovo progetto e copie o dati di prova separati.

1. **Definire cosa installare nel sito.** Stabilire il contenuto di `.websmith/`,
   delle istruzioni per gli agenti e delle skill. Separare le regole comuni di
   Websmith dalle guide specifiche del sito, evitando duplicazioni.
2. **Adattare il motore alla cartella corrente.** I comandi devono riconoscere il
   sito dal suo `websmith.yaml` e trovare contenuti, template, immagini e cartella
   `web/` senza dipendere dal repository centrale.
3. **Creare il comando di inizializzazione.** Un futuro `websmith init`, eseguito
   dentro `sito-xy/`, dovrà:
   - chiedere quale agente configurare;
   - installare regole e skill;
   - registrare la versione di Websmith;
   - distinguere un sito nuovo da uno già esistente;
   - preservare i file presenti e segnalare eventuali incompatibilità.
4. **Preparare l'installazione del programma.** Scegliere come distribuire Websmith
   e le sue dipendenze. Il programma sarà installabile sul computer; ogni sito
   manterrà la propria configurazione e la versione richiesta.
5. **Verificare il percorso completo.** In una cartella di prova: inizializzare un
   sito, modificare un Markdown, validarlo e generare `web/`. Verificare anche che
   ripetere l'inizializzazione non cancelli modifiche e che i comportamenti attuali
   restino supportati.

Si parte dai primi due passaggi: definire il contenuto dell'installazione locale
e adattare il riconoscimento della cartella sito. Sono la base per costruire `init`.

## Fasi successive: proposte ancora da confermare nei dettagli

- GitHub come archivio remoto dei progetti e strumento di collaborazione.
- Un repository per sito, con permessi indipendenti.
- Catalogo centrale contenente riferimenti ai repository, non necessariamente
  tutti i file di tutti i siti.
- Download dei soli siti scelti e autorizzati.
- Sincronizzazione che distingua condivisione delle bozze e pubblicazione online.
- Per il pilota: rami di lavoro, pull request e integrazione su `main` dopo i controlli.
- Automazione GitHub che valida i sorgenti, genera tutte le lingue previste e
  pubblica i file soltanto dopo la preparazione riuscita.
- Prova con due copie locali, modifiche concorrenti, conflitto e hosting di test.
- Creazione di un sito locale, registrazione nel catalogo e attivazione della
  pubblicazione come operazioni distinte.

Non sono ancora decisi canale di installazione, agenti inizialmente supportati,
formato del catalogo, gestione dei permessi editoriali e hosting del pilota.
La prima fase non deve estendersi implicitamente a queste funzionalità.

## Evidenze raccolte nel progetto originale

Da verificare nuovamente prima di riutilizzare codice, perché il progetto può evolvere:

- `scripts/websmith.py` ricava `WEBSITES_ROOT` dalla posizione del motore e cerca
  i siti sotto `websites/`.
- Sono presenti comandi di ispezione, validazione e rendering.
- `sync-translations` controlla le traduzioni; non sincronizza repository Git.
- `.github/workflows/deploy-ftp.yml` pubblica dopo i push su `main`, trasferendo
  via FTPS i file già presenti in `websites/techreloaded/web/` e
  `websites/humanreloaded/web/` verso i rispettivi server di hosting.
- Quel workflow non valida o rigenera le pagine prima del trasferimento.
- I siti esistenti hanno organizzazioni e livelli di migrazione diversi: non
  assumere che siano tutti compatibili con il modello Markdown-first.
- Il repository originale presenta numerose modifiche preesistenti, anche non
  collegate a questo lavoro: non alterarle e non trattarle come una base pulita.

## Regole tecniche da preservare

Leggere i riferimenti originali, senza considerare questo riepilogo un sostituto:

- `/Users/giovanni/progetti/websmith/AGENTS.md`
- `/Users/giovanni/progetti/websmith/docs/WEBSMITH_CONTRACT.md`
- `/Users/giovanni/progetti/websmith/scripts/websmith.py`
- `/Users/giovanni/progetti/websmith/schemas/websmith-site.schema.json`
- `/Users/giovanni/progetti/websmith/docs/HELP.md`

In particolare: sorgenti autorevoli espliciti; regole di composizione e componenti
specifici del sito; nessuna decisione editoriale incorporata nel renderer comune;
validazione prima della generazione; dati editoriali collocati esplicitamente nei
template; immagini e collegamenti verificati; traduzioni svolte dagli agenti nei
Markdown, non inventate dal motore.

## Documentazione di riferimento copiata

`PROPOSTA_DISTRIBUZIONE_ORIGINALE.md` è una copia della proposta estesa scritta
nel progetto originale. Conserva ragionamenti, glossario, esempio con due utenti
e criteri del pilota. Precede la decisione finale di inizializzare Websmith dentro
la cartella sito: dove differisce, prevale la decisione riportata qui.

L'utente ha chiesto spiegazioni accessibili: definire i termini tecnici e rendere
espliciti origine e destinazione dei trasferimenti. Evitare formule non spiegate
come «contratto», «nuovo flusso», «artefatto», «CI» o «deployment».

## Filone separato: contenuti consultabili dalle AI

L'utente desidera anche rendere l'offerta dei siti comprensibile ai chatbot che
li consultano. La proposta è pubblicare contenuti utili e verificabili, comprese
risposte alle domande reali, e documentarne i criteri nelle guide editoriali dei
singoli siti. Non è stato deciso di introdurre testo nascosto o una sezione `/ai`
obbligatoria. Questo lavoro non è un prerequisito del tool multiutente multisito.

## Ripresa del lavoro

### Avanzamento del 24 ottobre 2026

Letti i riferimenti originali e verificati i punti di dipendenza del motore dal
repository centrale. Il piano operativo è ora in `PIANO_TECNICO_FASE_1.md`:
descrive file locali proposti, riconoscimento della cartella sito, compatibilità
e verifiche. Le scelte tecniche proposte non sono nuove decisioni dell'utente.
È stata successivamente preparata la versione sperimentale `0.1.0a1`:

- pacchetto Python 3.11+ con comando `websmith`, schema e documentazione inclusi;
- motore recuperato selettivamente, con provenienza e impronte in `PROVENANCE.json`;
- selezione `--site-root` e riconoscimento del manifest dalla cartella corrente
  e dalle sottocartelle; caricamento di configurazione e catalogo per percorso;
- prove sintetiche temporanee, senza creare ancora il nuovo TechReloaded;
- installazione locale in `.venv`, cinque test superati e dipendenze coerenti;
- pacchetto installabile in `dist/` e controlli GitHub in `.github/workflows/check.yml`;
- repository GitHub privato `https://github.com/techreloaded-ar/websmith-cli`,
  trasferito nell’organizzazione techreloaded-ar scelta dall’utente.

L'utente ha scelto di usare il nuovo TechReloaded come sito indipendente, in una
posizione che indicherà. Non creare ora un sito reale né installare il motore
all'interno della cartella sito. Il programma si installerà da GitHub.

La prima versione viene condivisa sul ramo `main` e identificata dal tag
`v0.1.0a1`. Il prossimo passo è verificare i controlli GitHub e provare
l’installazione dal riferimento remoto privato. `websmith init`, skill e controllo della versione richiesta
dal sito restano da implementare prima dell'inizializzazione di TechReloaded.
La guida HELP incorporata conserva ancora gli esempi storici; leggere README
per la sintassi locale e i limiti. Non è stata certificata una migrazione di tutti
i siti originali: la compatibilità verificata riguarda il sito sintetico.
Il progetto originale resta invariato.

Leggere questo documento e la proposta copiata, esaminare i riferimenti originali
e preparare nel nuovo progetto il piano tecnico della prima fase. Distinguere
le decisioni dell'utente dalle proposte ancora aperte. Non modificare il progetto
originale e non attivare pubblicazioni remote.

## Aggiornamento del 25 ottobre 2026: distribuzione npm

L'utente ha scelto l'esperienza npm, sul modello di ARchetipo. Il nome proposto è
`@techreloaded/websmith`; lo scope npm non è determinato dall'organizzazione GitHub.
La distribuzione pipx resta disponibile ma non è il percorso semplificato scelto.
Sono stati preparati il lanciatore Node, i pacchetti per piattaforma e la
costruzione PyInstaller del motore Python autonomo. La macchina non è autenticata
su npm: non è stata verificata l'autorizzazione allo scope né pubblicato alcunché.
Vedere README per istruzioni e limiti. Non confondere preparazione locale,
verifica su tutti i sistemi e pubblicazione effettiva del pacchetto.


## Decisione del 26 ottobre 2026: GitHub senza npm

L'utente, dopo confronto con i colleghi, ha abbandonato npm e richiesto un
`setup.sh` sul modello di archetipo-workshop. Ha esplicitamente autorizzato a
rendere pubblico websmith-cli per consentire curl senza login. Nessun pacchetto
npm è stato pubblicato. I sorgenti della distribuzione npm sono rimossi; il file
locale di recupero npm è ignorato, non letto e non incluso nella distribuzione.
La distribuzione usa eseguibili autonomi in GitHub Releases e verifica SHA-256.
Vedere README per sistemi supportati e istruzioni. `init` resta da implementare.

Il cambio di visibilità è stato tentato ma GitHub lo ha rifiutato: `gpuliti` ha
permesso push, non admin. Il repository resta privato fino all'intervento di un
amministratore; il README distingue il comando autenticato da quello pubblico.
Le sette prove locali del motore e dell'installer sono riuscite.
