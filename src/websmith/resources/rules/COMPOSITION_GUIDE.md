# Composizione del sito

> Base gestita da Websmith. Dopo questo file leggere `COMPOSITION_GUIDE.local.md`, se presente: le indicazioni locali integrano e prevalgono sui punti corrispondenti. L'assenza del file locale è normale. Per personalizzare le regole del sito, l'agente scrive solo nel file `.local.md`, senza modificare questa base.

## Regole tecniche

Il motore valida e genera HTML in modo deterministico; non inventa contenuti o traduzioni. I sorgenti autorevoli sono Markdown, template, componenti, CSS e media. Le modifiche durature vanno riportate nei sorgenti, non solo in `web/`.

Leggere il manifest prima di cambiare composizione. I componenti appartengono al sito: consultare il catalogo dichiarato nel manifest. Non importare decisioni visuali o editoriali da altri siti nel renderer comune.

Aggiornare le traduzioni esistenti previste dal sito e preservarne la struttura. Validare manifest e pagine prima di generare; verificare HTML, link e immagini. Conservare front matter tecnico, direttive dei componenti e riferimenti logici durante gli interventi sui testi.

I valori editoriali devono avere una destinazione dichiarata nei template; i contenuti di anteprima non devono sopravvivere quando il sorgente manca. Le note alla redazione e i metadati di lavorazione non fanno parte del contenuto pubblicabile e non vanno inseriti nel corpo o nei campi editoriali destinati all'HTML.

La pubblicazione remota è distinta dall'inizializzazione e dalla generazione.

## Individuare il sito e i sorgenti

Identificare la cartella del sito e leggere `AGENTS.md`, il manifest e questa guida prima di modificare pagine, template, componenti, CSS o asset. Se il manifest dichiara un'altra guida di composizione, consultare quella.

Non assumere che percorsi, lingue o componenti di TechReloaded valgano per altri siti. Se mancano una guida o un catalogo necessari, segnalarlo e limitarsi alle operazioni il cui comportamento è già univoco. Un sito precedente al modello Markdown-first segue i propri sorgenti documentati: non migrarlo implicitamente durante un'altra modifica.

Se una richiesta indica un file HTML o una pagina visibile, risalire ai sorgenti corrispondenti. Se l'HTML è stato modificato per una prova visuale, identificare le differenze, riportarle in Markdown, template, componenti, CSS o asset, rigenerare e verificare che siano conservate.

## Responsabilità dei file

| Sorgente | Responsabilità |
| --- | --- |
| Markdown e front matter | Contenuti, metadati, dati dei componenti, ordine dei blocchi e riferimenti logici. |
| Template HTML | Struttura WYSIWYG, elementi fissi e destinazioni DOM stabili. |
| Componenti e catalogo | Composizioni riutilizzabili, parametri supportati, proprietà dei campi ed esempi realistici. |
| CSS | Tipografia, colori, spaziature, layout, comportamento responsive e stati interattivi. |
| Manifest e guida di composizione | Configurazione, percorsi e responsabilità; non duplicano i valori visuali esatti del CSS. |
| HTML generato | Risultato da ispezionare e pubblicare, non sede di decisioni presenti solo nell'output. |

Se un valore visuale è duplicato, il CSS sorgente prevale. Il renderer comune non deve inventare contenuti, indovinare strutture ambigue o incorporare decisioni editoriali o visuali proprie di un sito. Le vecchie versioni restano nella storia Git, non in copie con suffissi nella cartella pubblicabile.

## Contenuti canonici e traduzioni

Modificare prima il Markdown nella lingua canonica dichiarata dal sito. Propagare poi la modifica a tutte le traduzioni esistenti previste dal manifest, validare e generare ogni pagina e lingua interessata.

Durante la traduzione:

- conservare gerarchia dei titoli, direttive dei componenti, confini degli item, tabelle, blocchi di codice, asset e riferimenti logici;
- conservare il front matter tecnico necessario alla generazione e alla tracciabilità;
- tradurre naturalmente il testo editoriale, compresi metadati, hero, etichette degli inviti all'azione, tabelle e FAQ;
- lasciare stabili nomi, identificativi di prodotto, comandi, percorsi, codice e nomi dei componenti, salvo cambiamenti espliciti nella fonte;
- lavorare sul Markdown di destinazione, non sull'HTML generato;
- segnalare le ambiguità senza inventare conoscenze sul prodotto.

Usare i controlli di allineamento delle traduzioni documentati dal sito prima e dopo l'intervento, quando disponibili. `sync-translations` controlla struttura e tracciabilità: non traduce né sincronizza repository Git.

## Template e collocazione dei dati

I template dichiarano le destinazioni dei valori Markdown mediante attributi `data-websmith-*`. Prima di scrivere l'output devono essere rispettati entrambi i versi del contratto:

- un valore assente rimuove il nodo di anteprima associato o ne omette il contenuto; il testo di esempio non deve comparire nell'HTML finale;
- ogni valore editoriale popolato deve essere consumato da un binding, componente o altra destinazione dichiarata;
- un corpo Markdown non vuoto richiede una destinazione nel template;
- i campi tecnici di routing e ciclo di vita non richiedono segnaposto visibili; non classificare campi editoriali come tecnici per aggirare la validazione;
- controllare i valori foglia dei mapping e ogni elemento dei record ripetuti; segnalare i percorsi non consumati prima di scrivere HTML, CSS o asset.

## Componenti

Prima di aggiungere o modificare direttive, consultare il catalogo dichiarato nel manifest. Rispettare nome, `owned_by`, `layout_role`, campi richiesti e facoltativi, campi degli item, deprecazioni e istruzioni d'uso.

La sintassi canonica di un blocco è:

```md
<!-- component: nome-componente -->
body: Testo Markdown.
<!-- /component -->
```

Il nome e i campi dell'esempio devono esistere nel catalogo del sito. Per i componenti ripetuti ogni elemento inizia con `<!-- item -->`; chiusure e annidamento seguono il contratto del componente. Il marcatore di apertura include sempre i due punti.

Non introdurre marcatori o nomi di campo legacy nei nuovi contenuti. Non sostituire componenti dichiarati con markup generico o varianti inventate. Se un componente o un campo è mancante o ambiguo, segnalarlo prima di procedere.

## Asset e verifiche finali

Per ogni riferimento locale nuovo o modificato identificare l'asset sorgente del sito, seguire le regole di copia o risoluzione dichiarate, generare la pagina e verificare che il percorso emesso nell'HTML trovi il file nell'output. Non dipendere da asset di un altro sito.

Prima di terminare:

1. validare manifest, front matter e pagine con i comandi supportati;
2. generare ogni pagina e lingua modificata;
3. verificare contenuti, link, componenti, metadati e percorsi degli asset nell'HTML;
4. risolvere i problemi nei sorgenti, senza aggirare la validazione o nasconderli con ritocchi all'output.

Non annullare modifiche estranee dei collaboratori. Non eliminare file legacy o asset senza richiesta di pulizia e verifica del loro mancato utilizzo. Tenere distinti i commit per responsabilità, salvo incarichi che comprendano esplicitamente più ambiti. Le operazioni dirette sull'hosting o via FTP richiedono una richiesta esplicita; il flusso di pubblicazione effettivo dipende dal sito e non va presunto.

## Richieste di aiuto

Quando l'utente chiede HELP, spiegare scopo, sintassi ed esempi dei comandi in italiano. Consultare `websmith HELP` per la panoramica con i prompt di esempio, `websmith HELP guida` per la guida completa, e verificare le opzioni correnti con `websmith COMANDO --help` oppure `websmith HELP COMANDO`. La richiesta di aiuto non autorizza a eseguire le operazioni illustrate. Distinguere sempre comandi locali generici e scorciatoie storiche specifiche di TechReloaded.

## Composizione iniziale

I percorsi e i comandi descritti sotto si riferiscono al sito minimo creato da init. Su un sito esistente verificare il manifest e documentare percorsi e comandi specifici in `COMPOSITION_GUIDE.local.md` prima di applicarli.

Per lingua canonica, lingue disponibili e percorsi leggere `websmith.yaml`. Nel sito iniziale la homepage è `contents/<lingua>/pages/home.md`.
Modificare i testi nel Markdown e la struttura in `templates/html/page.html`.
La composizione di esempio è volutamente minima: prima della pubblicazione
sostituire testi, logo, dominio ed email di esempio nel manifest.
Il CSS è in `templates/CSS/main.css`; i media del sito sono in `media/`.
Il catalogo è `templates/html/components/catalog.yaml`; il componente note
espone il campo body. Non esistono componenti globali impliciti.

```bash
websmith validate-site
websmith validate-pages
websmith render-page home
websmith render-root-index
```

L'output della homepage è `web/<lingua>/index.html`; `web/index.html` reindirizza
alla lingua iniziale. Dopo la generazione ispezionare HTML, link e immagini.
Aprire `web/index.html` nel browser per l'anteprima. `web/` è generata e non è
il luogo per modifiche durature. Non sono configurati FTP o pubblicazione remota.
Aggiungere una lingua richiede dichiararla nel manifest e scriverne i Markdown;
il programma non traduce i contenuti. Per i testi leggere `TONE_OF_VOICE.md` ed `EDITORIAL_RULES.md`.
