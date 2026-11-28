---
name: collaboration
description: Aiuta persone non tecniche a lavorare sullo stesso sito Websmith con copie locali e una condivisione Git. Usare per elencare i siti del team, aprire un sito, ricevere gli aggiornamenti degli altri, condividere modifiche o gestire versioni sovrapposte; anche per configurare catalogo e collegamento iniziali.
---

# Collaborare su un sito

Leggere [il flusso e le regole di collaborazione](references/COLLABORATION_GUIDE.md)
prima di usare i comandi. Leggere `AGENTS.md` del sito quando disponibile.

Interpretare le richieste senza richiedere all'utente conoscenze di Git:

| Richiesta | Operazione |
| --- | --- |
| «Quali siti posso modificare?» | `websmith collaboration list` |
| «Voglio lavorare su miosito.it» | Individuare il sito nel catalogo, poi `open`. |
| «Ci sono aggiornamenti di Giovanni?» | `status`, che non cambia i sorgenti. |
| «Scarica gli aggiornamenti» | `sync`. |
| «Condividi le mie modifiche» | `share`, con una descrizione del lavoro. |
| «Collega questo sito» | Configurazione iniziale `connect` e, se richiesto, `register`. |

Tutti i siti sono nel repository comune `websmith-sites`, in `sites/<site.id>`.
Per configurare il primo accesso raccogliere il collegamento a quel repository, nome ed
email dell'autore. Usare le credenziali Git già configurate sul computer senza
chiedere password in chat né salvarle nei sorgenti. Spiegare in modo concreto
eventuali requisiti mancanti. `websmith HELP collaboration` espone i comandi;
le opzioni di ciascuna azione si consultano con `--help`.

Per le modifiche ai contenuti usare [composer](../composer/SKILL.md) e le altre
skill pertinenti. Presentare stato, risultati e problemi in italiano, parlando
di aggiornamenti e versioni invece di index, stash, rebase o ref.

Se le modifiche si sovrappongono, conservare le copie, mostrare le differenze
e raccogliere la scelta dell'utente prima di scartare o sostituire informazioni.
La guida spiega come registrare la scelta per le sole versioni confrontate.
Una richiesta di sola verifica non autorizza a ricevere o inviare modifiche.
