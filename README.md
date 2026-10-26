# Websmith CLI

Programma deterministico per siti indipendenti. Il programma si installa sul
computer; configurazione e sorgenti rimangono nella cartella di ciascun sito.

## Installazione da GitHub (macOS e Linux x64)

Il comando senza login richiede che un amministratore renda pubblico il repository.
Al momento della preparazione il repository è ancora privato. Gli utenti già
abilitati possono usare GitHub CLI autenticata:

```bash
gh api repos/techreloaded-ar/websmith-cli/contents/setup.sh -H 'Accept: application/vnd.github.raw+json' | bash
```

Dopo il cambio di visibilità sarà disponibile:

```bash
curl -fsSL https://raw.githubusercontent.com/techreloaded-ar/websmith-cli/main/setup.sh | bash
```

Lo script scarica l'eseguibile autonomo della release GitHub corrente, verifica
il checksum SHA-256 e installa `~/.local/bin/websmith`. Non richiede Python,
Node.js, npm o Git. Servono Bash, curl, unzip e shasum oppure sha256sum.
Su Linux sono supportate le distribuzioni compatibili con Ubuntu 22.04 o successive.
I target Mac sono Intel e Apple Silicon.

Se la cartella non è già nel PATH, aggiungere alla configurazione della shell:

```bash
export PATH="$HOME/.local/bin:$PATH"
```

Poi:

```bash
websmith --version
websmith --help
```

Per scegliere una versione o una destinazione:

```bash
curl -fsSL https://raw.githubusercontent.com/techreloaded-ar/websmith-cli/main/setup.sh | WEBSMITH_VERSION=v0.1.0a1 WEBSMITH_INSTALL_DIR="$HOME/.local/bin" bash
```

Per aggiornare, rieseguire lo script. L'eseguibile precedente viene sostituito
solo dopo download, checksum e verifica di avvio riusciti. Il checksum verifica
la corrispondenza con gli asset della release, non è una firma indipendente.
Lo script non modifica automaticamente il profilo della shell né crea siti.

Su Windows scaricare `websmith-win32-x64.zip` dalla sezione Releases del repository,
estrarre `websmith.exe` e aggiungere la sua cartella al PATH. Lo script Bash non
è un installer Windows. Le versioni distribuite non hanno ancora firma digitale.

## Utilizzo su un sito esistente

Dalla cartella con `websmith.yaml`, anche dalle sue sottocartelle:

```bash
websmith validate-site
websmith validate-pages
websmith render-page ID_PAGINA --all-langs
```

Oppure:

```bash
websmith --site-root /percorso/del/sito validate-site
```

`websmith init` e la configurazione degli agenti restano da implementare.
Il nuovo TechReloaded sarà creato solo nel percorso scelto dall'utente.
La guida `websmith HELP` conserva gli esempi storici; per le opzioni attuali usare
`websmith COMANDO --help`. I percorsi relativi di `resolve-page` e `parse-component`
restano riferiti alla cartella di esecuzione: usare percorsi assoluti.

## Sviluppo

Richiede Python 3.11+:

```bash
python3.11 -m venv .venv
.venv/bin/python -m pip install -c requirements.lock .
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python -m pip install PyInstaller==6.16.0
.venv/bin/python scripts/build-native.py
.venv/bin/python scripts/package-native.py
```

Le versioni delle librerie sono in `requirements.lock`; la provenienza dei file
recuperati è in `PROVENANCE.json`. GitHub costruisce e verifica gli eseguibili
per quattro piattaforme prima della distribuzione. I pacchetti npm sono stati
abbandonati prima di qualsiasi pubblicazione. L'installazione pipx dal tag GitHub
rimane possibile per chi preferisce il pacchetto Python.
