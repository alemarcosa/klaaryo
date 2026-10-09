# Decisioni Architetturali e Tecniche - Klaaryo ATS Integration

Documento di sintesi delle motivazioni progettuali, dei trade-off accettati, dei suggerimenti dell'AI scartati e delle deviazioni motivate rispetto alle specifiche iniziali.

---

## 1. Scelte Architetturali e Motivazioni

### 1.1 Event Bus su Redis Streams con Transactional Outbox (D1, D2)
- **Motivazione**: L'approccio ingenuo di scrivere sul DB e subito dopo pubblicare sull'event bus soffre del *Dual-Write Problem*: se la connessione verso il broker cade a metà, il DB è aggiornato ma l'evento non parte mai (o viceversa). Abbiamo implementato un **Transactional Outbox**: il salvataggio del `Candidate` e la riga `OutboxEvent` avvengono nella stessa transazione atomica SQL. Un thread daemon (`OutboxRelay`) legge gli eventi pending e li pubblica su **Redis Streams** con `XADD`. Abbiamo scartato Redis Pub/Sub perché volatile (se il consumer è in fase di riavvio perde i messaggi), mentre gli Streams con Consumer Groups e `XACK` forniscono garanzie *at-least-once* reali.

### 1.2 Pattern Adapter + Registry Esplicito per gli ATS (D4)
- **Motivazione**: I vendor ATS hanno dialetti eterogenei (formati data ISO vs Unix, mapping di status diversi, campi annidati o appiattiti). Invece di disseminare rami condizionali `if source == "alpha"` nel business logic, ogni ATS implementa l'interfaccia `AtsAdapter` (`fetch_since` e `normalize`). Un dizionario esplicito `_ADAPTERS` funge da registry. Per aggiungere un terzo ATS basta creare una nuova classe adapter e registrarla in una riga di configurazione, rispettando l'Open/Closed Principle.

### 1.3 Cursore Watermark Monotono con Overlap Temporale (D5)
- **Motivazione**: Non usiamo `datetime.now()` del server locale per impostare il cursore di sincronizzazione, poiché soggetto a *clock skew* tra macchine diverse e al rischio di perdere record committati con ritardo sulla sorgente. Il cursore memorizza il valore massimo di `updated_at` (watermark) effettivamente ricevuto dalla sorgente. Nelle run successive, la query richiede i record con un overlap all'indietro di 300 secondi (`since = cursor - 300s`). L'idempotenza a valle dell'upsert garantisce che la rilettura dei record al bordo non provochi duplicati. Il cursore avanza solo ed esclusivamente se l'intera run si conclude con status `success`.

### 1.4 Calcolo dell'Età Deterministico Ancorato a `applied_at` (D6)
- **Motivazione**: La normalizzazione deve essere una funzione pura e deterministica: a parità di payload di input deve sempre produrre lo stesso identico output. Se calcolassimo l'età usando `date.today()`, lo scoccare della mezzanotte del compleanno di un candidato farebbe variare il campo `age` (es. da 29 a 30) pur in assenza di modifiche nell'ATS, scatenando un falso evento `candidate.updated` e violando l'idempotenza della sync. L'età viene calcolata esattamente alla data di candidatura (`age_at(birth_date, applied_at.date())`).

### 1.5 Deduplicazione Atomica su Vincolo UNIQUE a Livello Database
- **Motivazione**: Nel consumer `event_logger`, non facciamo un controllo applicativo del tipo `if not exists: create()`, perché in scenari concorrenti soffre del problema *Check-Then-Act* (race condition). L'inserimento dell'evento delega la verifica atomica al vincolo `UNIQUE(event_id)` del database relazionale: se scatta un `IntegrityError`, l'evento viene immediatamente classificato come `DUPLICATE` senza alcun rischio di doppie scritture.

---

## 2. Proposte dell'AI Rifiutate e Motivazioni

Durante la sessione di sviluppo assistito, l'AI ha proposto varie scorciatoie e pattern standard che sono stati esplicitamente scartati:

1. **Adozione di Django REST Framework (DRF) e ViewSets**:
   - *Proposta AI*: Installare `djangorestframework`, creare Serializer e ViewSet con router automatico per esporre le API di sincronizzazione.
   - *Motivo del rifiuto*: Sovradimensionato per due soli endpoint (`POST /sync/<ats>` e `GET /sync/<ats>/status`). DRF introduce overhead e complessità di serializzazione non necessaria; è bastato l'uso di standard Django con `JsonResponse`, decoratori HTTP (`require_POST`, `csrf_exempt`) e dataclass DTO immutabili.
2. **Uso di Pydantic per la validazione di `push_data_manager`**:
   - *Proposta AI*: Usare modelli Pydantic per validare i candidati e catturare gli errori con `ValidationError`.
   - *Motivo del rifiuto*: I `ValidationError` di Pydantic raggruppano gli errori in strutture complesse e generiche, rendendo difficile e contorto il mapping 1-a-1 sui singoli `SkipReason` di business richiesti dallo spec (es. `underage`, `missing_phone`, `invalid_birth_date`). Abbiamo preferito una funzione di validazione esplicita in `candidate_rules.py` che solleva `NormalizationError` con l'esatto motivo di scarto.
3. **Check-then-insert applicativo per la deduplicazione**:
   - *Proposta AI*: Eseguire una query preliminare `if ProcessedEvent.objects.filter(event_id=...).exists(): return DUPLICATE`.
   - *Motivo del rifiuto*: Anti-pattern nei sistemi distribuiti. Due worker paralleli che leggono lo stesso evento simultaneamente vedrebbero entrambi l'assenza del record, tentando un doppio insert. È stata imposta l'intercettazione atomica di `IntegrityError` sul vincolo unique della tabella.
4. **Auto-discovery degli Adapter ATS con Metaclassi o Decoratori magici**:
   - *Proposta AI*: Creare un registry dinamico con decorator `@register_ats` e scanning automatico dei moduli.
   - *Motivo del rifiuto*: Aggiunge "magia" e dipendenza dall'ordine di importazione dei moduli. Un dizionario esplicito `_ADAPTERS = {"alpha": AlphaAdapter, "beta": BetaAdapter}` in `registry.py` è trasparente, leggibile, facilissimo da tracciare ed esente da side-effect.

---

## 3. Trade-off Espliciti

1. **SQLite in modalità WAL con `IMMEDIATE transaction_mode` vs PostgreSQL**:
   - *Trade-off*: Abbiamo scelto SQLite per garantire avvio a zero-configurazione locale e conformità con l'ambiente Compose. Con `PRAGMA journal_mode=WAL` e `transaction_mode: IMMEDIATE`, SQLite acquisisce subito il write lock ed evita race condition di lettura/scrittura. Tuttavia, `select_for_update` è una no-op su SQLite. In produzione distribuita multi-istanza, il backend naturale sarà PostgreSQL usando clausole native `INSERT ... ON CONFLICT DO UPDATE`.
2. **Polling Outbox in Background Thread vs Change Data Capture (CDC / Debezium)**:
   - *Trade-off*: Il thread daemon `OutboxRelay` controlla la tabella `OutboxEvent` a intervalli di 500ms. Questo introduce una latenza teorica massima di 500ms prima che l'evento finisca su Redis, ma non richiede componenti infrastrutturali pesanti (Kafka Connect, Debezium, engine CDC). Per i requisiti del sistema, il rapporto semplicità/efficacia è ottimale.
3. **Split del Nome di Beta Lossy (`maxsplit=1`)**:
   - *Trade-off*: L'ATS Beta fornisce un unico campo `full_name`. L'operazione `full_name.split(maxsplit=1)` mappa il primo token su `first_name` e il resto su `last_name`. Per nominativi composti (es. `"Maria Grazia Rossi"` -> `"Maria"` e `"Grazia Rossi"`), l'attribuzione è inevitabilmente un'approssimazione. In un sistema enterprise, conserveremmo anche la stringa originale `raw_full_name` per verifiche manuali.

---

## 4. Cosa Rifarei Diversamente

1. **Paginazione a Cursore nelle API ATS**:
   - Attualmente le chiamate `GET /api/applications` e `GET /v2/candidates` scaricano l'intero batch in una singola risposta JSON. Se un vendor avesse centinaia di migliaia di candidature, la memoria del processo verrebbe saturata. Implementerei una paginazione basata su link header o cursore (`limit` + `next_cursor`) elaborando i record in streaming a blocchi.
2. **Dead Letter Queue (DLQ) e Retry Policy con Backoff per l'Event Bus**:
   - Attualmente i messaggi poison non parsabili vengono loggati e scartati immediatamente (`XACK`). In produzione strutturerei una Dead Letter Queue dedicata dove indirizzare i messaggi anomali dopo 3 tentativi falliti, abilitando un monitoraggio proattivo degli errori di schema senza perdere i dati.

---

## 5. Cosa Ho Fatto Diversamente dallo Spec (e Perché)

### La Specifica:
> *"estrarre le candidature create dopo `since`"*

### Cosa Ho Fatto Diversamente:
Negli ATS fake (`fake_ats_alpha` e `fake_ats_beta`), le API filtrano il parametro `since` / `updated_after` **sulla data di ultima modifica del record** (`updated_at` / `updated_timestamp`), anziché esclusivamente sulla data di candidatura originaria (`applied_at` / `submitted_timestamp`).

### Perché:
Se il filtro `since` considerasse unicamente la data di creazione della candidatura:
1. Una candidatura inviata un mese fa e modificata oggi da un recruiter (ad esempio: status aggiornato da `IN_REVIEW` a `HIRED`, o variazione del numero di telefono) **non verrebbe mai più estratta da `push_data_manager`**, perché la sua data di creazione cadrebbe sempre fuori dalla finestra di sync incrementale!
2. Lo scenario dimostrativo fondamentale (`candidate.updated` quando una candidatura esistente cambia stato) sarebbe tecnicamente impossibile senza rileggere costantemente l'intero database storico ad ogni sync.
3. Nei sistemi ATS enterprise reali (come Workday, Greenhouse o Lever), gli endpoint di estrazione incrementale filtrano sempre sul timestamp di *last-modified*.
4. Per tutte le candidature che non hanno mai subito modifiche, `updated_at == applied_at`: pertanto il comportamento per i nuovi inserimenti rimane identico a quanto descritto nello spec, garantendo piena retrocompatibilità.
