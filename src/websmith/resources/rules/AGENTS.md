# Istruzioni per questo sito

## Basi e personalizzazioni

Le tre guide di base sono distribuite e aggiornate da Websmith. Leggere ciascuna base prima dell'eventuale file locale corrispondente:

| Base | Personalizzazioni facoltative del sito |
| --- | --- |
| `COMPOSITION_GUIDE.md` | `COMPOSITION_GUIDE.local.md` |
| `TONE_OF_VOICE.md` | `TONE_OF_VOICE.local.md` |
| `EDITORIAL_RULES.md` | `EDITORIAL_RULES.local.md` |

I file `.local.md` integrano le basi e prevalgono sui punti che modificano; il resto della base continua a valere. Se un file locale non esiste, usare solo la base senza segnalare un errore e senza crearne uno vuoto.

Quando l'utente chiede di modificare le regole del sito, creare o aggiornare esclusivamente il relativo `.local.md`. Scrivere solo le differenze e le aggiunte, senza ricopiare l'intera base. Conservare le personalizzazioni già presenti. Non modificare le tre basi: `websmith update` le sostituisce con quelle della versione installata.

Per composizione, template, componenti, asset, traduzioni, validazione e generazione leggere la coppia di composizione e il manifest `websmith.yaml`. Se il manifest indica un'altra guida di composizione, consultarla insieme alla sua eventuale variante `.local.md` e conservarvi le scelte specifiche del sito.

Per scrivere o revisionare testi leggere le coppie di tone of voice e regole editoriali. I limiti dell'editor si applicano alla revisione di testi già scritti. Gli esempi e le proposte da confermare non sono preferenze approvate.
