---
name: mail
description: Controlla la sola casella condivisa trtalks@techreloaded.it per Websmith e presenta messaggi e allegati. Usare per «c'è posta per me?», «controlla la posta» o «ci sono nuovi articoli?». Durante la prova corrente legge tutta INBOX senza filtri per sito e senza modificare le email.
---

# Controllo della posta

Leggere [la guida della posta](references/MAIL_GUIDE.md) prima di eseguire comandi.
La guida distingue il controllo corrente senza filtri dalla CLI di acquisizione
delle bozze, che conserva il proprio filtro per sito.

Lo script dedicato è [scripts/check-mail.py](scripts/check-mail.py). Nella copia
di sviluppo rimane disponibile il comando storico `.venv/bin/python
scripts/check-mail.py --all-messages` dalla radice del repository.
Lo script usa il codice Python di Websmith: la sola copia della skill non fornisce
un interprete, il pacchetto o le credenziali. Se mancano, segnalare il requisito
effettivo senza ripiegare su Gmail personale o su altre caselle.

Interpretare il JSON come descritto nella guida e rispondere in italiano.
Non collegarsi alla posta per verificare l'installazione di questa skill.
