---
name: composer
description: Compone e modifica siti Websmith intervenendo su Markdown, front matter, template, componenti, CSS e asset. Usare per creare pagine dai contenuti forniti, cambiare layout, gestire traduzioni, validare sorgenti e generare e verificare HTML.
---

# Composizione del sito

1. Individuare la radice del sito. Leggere `AGENTS.md`, `websmith.yaml` e
   [la guida di composizione](references/COMPOSITION_GUIDE.md), poi
   `COMPOSITION_GUIDE.local.md` nella radice del sito, se presente.
2. Se il manifest dichiara un'altra guida, consultarla con la sua eventuale
   variante `.local.md`. Individuare sorgenti, lingue e catalogo dei componenti.
3. Modificare i sorgenti autorevoli secondo la responsabilità dei file descritta
   nella guida. Per revisione dei testi usare [editor](../editor/SKILL.md);
   per scrittura o traduzione applicare [tov](../tov/SKILL.md) e le regole
   editoriali di editor. Non inventare dati mancanti.
4. Aggiornare le traduzioni esistenti previste dal sito mantenendone la struttura.
5. Validare i sorgenti, generare tutte le pagine e lingue interessate e verificare
   HTML, link, componenti, metadati e asset secondo la guida.

Riferire le modifiche e le verifiche effettivamente svolte. La generazione locale
non pubblica il sito: le operazioni sull'hosting seguono una richiesta esplicita.
