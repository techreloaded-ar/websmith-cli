# Lavorare sullo stesso sito con Websmith

Giovanni e Marta lavorano su copie locali indipendenti di `miosito.it`.
Websmith usa Git per scambiare i sorgenti e riconoscere le versioni, mentre
l'agente presenta le operazioni in linguaggio naturale.

## Il lavoro quotidiano di Marta

Dopo la configurazione iniziale Marta può chiedere:

| Richiesta | Risultato |
| --- | --- |
| «Quali siti sono disponibili?» | Elenco dei siti del catalogo del gruppo. |
| «Voglio lavorare su miosito.it» | Preparazione della copia locale in una nuova cartella. |
| «Ci sono aggiornamenti di Giovanni?» | Confronto con la versione condivisa, senza modificare i contenuti. |
| «Ricevi gli aggiornamenti» | Integrazione delle modifiche compatibili, conservando il lavoro locale. |
| «Condividi le mie modifiche» | Controllo dei sorgenti e invio delle modifiche agli altri collaboratori. |

L'agente usa la skill `collaboration`. Se entrambi cambiano lo stesso passaggio,
mostra le differenze e raccoglie una scelta: conserva le copie e non decide
arbitrariamente quali informazioni perdere. Si può continuare a lavorare offline;
per confrontare o condividere serve l'accesso al repository.

## Preparazione iniziale del responsabile

Preparare sul servizio Git scelto un solo repository, `websmith-sites`, con gli
accessi di Giovanni e Marta. Contiene catalogo e sorgenti di tutti i siti:

| Percorso nel repository | Contenuto |
| --- | --- |
| `sites.json` | Elenco dei siti; aggiornato da Websmith. |
| `sites/miosito/` | Manifest, contenuti, template e media di miosito.it. |
| `sites/techreloaded/` | Sorgenti del sito TechReloaded. |

La cartella usa il `site.id` del manifest, quindi ogni identificativo deve essere
unico nel gruppo. Tutti i siti usano lo stesso repository e la stessa versione
Git. Sul computer ciascuna copia di lavoro contiene solo il sito scelto;
le modifiche agli altri siti e al catalogo sono conservate durante gli invii.

Il repository può essere inizialmente vuoto o contenere un README: Websmith crea
le cartelle e il catalogo quando vengono condivisi e registrati i siti.
Non crea repository o utenti sul servizio Git. Verificare eventuali automazioni
già collegate, installare Git e autorizzare l'accesso sul computer tramite il
gestore di credenziali o una chiave SSH. Non inserire password o token negli URL.

I permessi sono sul repository intero: chi vi accede può accedere a tutti i siti.
La scelta di un sito in Websmith organizza il lavoro e non costituisce una
separazione dei permessi. Anche la cache Git interna può contenere oggetti degli
altri siti; la cartella di lavoro mostra soltanto quello selezionato.

Sul computer di Giovanni configurare il repository comune una volta:

```bash
websmith collaboration configure --repository https://github.com/ORGANIZZAZIONE/websmith-sites.git --name "Giovanni" --email giovanni@example.test
```

Dalla cartella del sito locale esistente:

```bash
websmith collaboration connect
websmith collaboration share --dry-run
websmith collaboration share --message "Prima versione condivisa"
websmith collaboration register
```

Gli indirizzi e le email degli esempi vanno sostituiti. La versione Git condivisa
predefinita è `main`; `configure --branch` permette di cambiarla per tutti i siti.
`connect` usa il repository e l’identità già configurati, senza chiedere un altro URL.
Il dominio da cui riconoscere il sito è quello del manifest `websmith.yaml`.

## Primo accesso di Marta

Il responsabile fornisce a Marta il collegamento a `websmith-sites` e la aiuta ad
autorizzare l'accesso al servizio Git. Il nome e l'email identificano l'autore delle
modifiche; non sono credenziali di accesso. La configurazione è per computer:

```bash
websmith collaboration configure --repository https://github.com/ORGANIZZAZIONE/websmith-sites.git --name "Marta" --email marta@example.test
websmith collaboration list
websmith collaboration open miosito.it --destination ./miosito --agent codex
```

Marta apre la cartella preparata in Codex o Claude. Le skill sono installate nel
sito e le successive richieste possono essere quelle della tabella iniziale.
In alternativa può chiedere all'agente di eseguire la configurazione e l'apertura,
fornendo il collegamento al catalogo e la propria identità: non deve conoscere
i comandi Git.

`open` richiede una cartella nuova e non sovrascrive cartelle esistenti.
`--agent claude` prepara i riferimenti per Claude. `--offline` riguarda solo le
istruzioni Websmith già scaricate: il sito viene comunque acquisito da Git.

## Verifica, ricezione e condivisione

Le operazioni disponibili nella cartella del sito sono:

```bash
websmith collaboration status
websmith collaboration sync --dry-run
websmith collaboration sync
websmith collaboration share --dry-run
websmith collaboration share --message "Aggiornata la pagina contatti"
```

`status` controlla; `sync` riceve; `share` invia il lavoro e integra gli aggiornamenti
compatibili degli altri. Le anteprime non cambiano i sorgenti e non inviano dati;
aggiornano la cache Git interna. Prima di applicare o inviare vengono controllati
manifest e pagine della versione combinata. L'anteprima HTML si genera con composer.

La condivisione include le regole specifiche del sito nei file `.local.md`.
Output generato, dati personali dell'installazione e bozze email non importate
nei sorgenti rimangono locali. Il Git interno non modifica lo staging o il ramo
di un eventuale repository Git già usato nella cartella del sito.

## Limiti della prima versione

L'accesso iniziale a Git richiede una preparazione del computer e i permessi del
provider; Websmith riconosce gli errori di accesso e li presenta in italiano, ma
non implementa un login GitHub proprietario. Il catalogo elenca i siti registrati,
mentre i permessi effettivi riguardano il repository comune e sono verificati dal servizio Git.

Non sono previste modifica simultanea in tempo reale, prenotazione remota dei file,
backend Google Drive o pubblicazione universale sull'hosting. Per regole complete
su sorgenti selezionati, conflitti, copie di recupero e scelte delle versioni,
consultare la [guida della collaborazione](../skills/collaboration/references/COLLABORATION_GUIDE.md).

I nuovi comandi e la skill richiedono una release del programma che li includa.
La presenza del codice nel repository non aggiorna gli eseguibili già installati.
