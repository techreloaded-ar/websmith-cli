# Websmith CLI

Prima versione sperimentale del programma per siti indipendenti. Richiede Python
3.11 o successivo. Il sito e il programma si trovano in cartelle separate.

## Installazione da GitHub

Il repository è privato: occorre un account GitHub autorizzato e Git configurato
per accedervi. Per installare la prima versione:

```bash
pipx install 'git+https://github.com/techreloaded-ar/websmith-cli.git@v0.1.0a1'
```

Serve anche Git. `pipx` installa il programma in un ambiente Python separato;
non scarica il programma dentro il sito. Usare un tag o un commit identificabile.

Per provare la copia locale senza pubblicarla:

```bash
python3.11 -m venv .venv
.venv/bin/python -m pip install -c requirements.lock .
.venv/bin/websmith --version
.venv/bin/websmith --help
```

## Sito indipendente

Da una cartella contenente `websmith.yaml`, anche da una sua sottocartella:

```bash
websmith validate-site
websmith inspect
websmith validate-pages
websmith render-page ID_PAGINA --all-langs
```

Oppure indicare il sito esplicitamente, prima del comando:

```bash
websmith --site-root /percorso/del/sito validate-site
websmith --site-root /percorso/del/sito render-page ID_PAGINA --all-langs
```

I comandi storici con argomento sito restano disponibili dalla cartella che
contiene `websites/`. Per i comandi che richiedono più argomenti posizionali,
indicare il percorso assoluto del sito al posto del suo nome.
`resolve-page` e `parse-component` interpretano ancora i percorsi relativi dalla
cartella di esecuzione: usare percorsi assoluti per evitare ambiguità.

`websmith HELP` contiene la guida storica recuperata dall'originale: gli esempi
`python3 scripts/websmith.py` si riferiscono alla precedente organizzazione.
`websmith COMANDO --help` mostra le opzioni attuali.

Questa versione non include ancora `websmith init`, installazione delle skill,
controllo della versione richiesta dal sito, sincronizzazione Git o pubblicazione.
Non inizializza né migra automaticamente un sito esistente. Il nuovo TechReloaded
sarà creato soltanto nel percorso scelto dall'utente.

## Verifica

```bash
.venv/bin/python -m unittest discover -s tests -v
```

La provenienza dei file recuperati è registrata in `PROVENANCE.json` con le
impronte SHA-256 dei sorgenti originali. Le risorse comuni sono incluse nel
pacchetto: l'installazione non dipende dalla cartella del motore originale.

`requirements.lock` registra tutte le versioni delle librerie verificate con
Python 3.11. I controlli GitHub usano queste versioni anche sulle altre versioni
Python dichiarate nella matrice; tali esecuzioni remote non sono ancora avvenute.

## Distribuzione npm in preparazione

L'obiettivo concordato è installare il programma con:

```bash
npm install -g @techreloaded/websmith
websmith version
```

Questo comando sarà disponibile dopo la pubblicazione su npm. Lo scope
`@techreloaded` è indipendente dal proprietario GitHub `techreloaded-ar`.
L'accesso npm allo scope deve ancora essere verificato: questa macchina non
risulta autenticata su npm. Nessun pacchetto è stato pubblicato.

Il pacchetto principale in `npm/websmith` avvia il motore autonomo della
piattaforma, installato come dipendenza facoltativa selezionata da npm.
Non occorrono Python, pipx o Git sul computer dell'utilizzatore per lavorare
localmente. Occorrono Node.js 20+ e npm; non usare `--omit=optional`.
I target iniziali sono macOS ARM64/Intel, Windows x64 e Linux x64.

Per costruire il motore sulla propria piattaforma (solo sviluppo):

```bash
.venv/bin/python -m pip install PyInstaller==6.16.0
.venv/bin/python scripts/build-native.py
npm test
npm pack ./npm/websmith
```

La preparazione degli altri sistemi è definita in
`.github/workflows/native.yml`. Ogni sistema costruisce il proprio eseguibile;
non viene simulata una compilazione per Windows da macOS.
Le versioni npm usano `0.1.0-alpha.1`, equivalente alla versione Python `0.1.0a1`.
Prima di pubblicare occorre verificare tutti gli eseguibili e pubblicare i
pacchetti di piattaforma prima del pacchetto principale. `websmith init` resta
un lavoro separato ancora da implementare.
