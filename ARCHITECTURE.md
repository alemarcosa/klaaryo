# Architettura del Sistema - Klaaryo ATS Integration

Il sistema realizza una pipeline ETL (Extract, Transform, Load) e una distribuzione asincrona di eventi per integrare molteplici Applicant Tracking System (ATS) eterogenei in un unico repository centrale di candidati (*Talent Pool*), garantendo idempotenza, tolleranza ai guasti e resilienza a disconnessioni.

---

## 1. Mappa dei Componenti

L'architettura è distribuita in un mono-repo con 5 servizi indipendenti orchestrati tramite Docker Compose:

```
[fake_ats_alpha] (:8001)               [fake_ats_beta] (:8002)
 (FastAPI - ISO dates)                  (FastAPI - Unix ts)
         ▲                                      ▲
         │ HTTP GET /applications               │ HTTP GET /candidates
         └──────────────────┬───────────────────┘
                            │
               ┌────────────┴────────────┐
               │    push_data_manager    │ (:8000)
               │ (Orchestratore Django)  │
               └────────────┬────────────┘
                            │ gRPC (TalentPool/UpsertCandidate)
                            ▼
               ┌─────────────────────────┐
               │       talent_pool       │ (:50051)
               │  - Candidate Table      │
               │  - OutboxEvent Table    │
               │  - Thread OutboxRelay   │
               └────────────┬────────────┘
                            │ XADD (Redis Streams)
                            ▼
               ┌─────────────────────────┐
               │          redis          │ (:6379)
               │ Stream: candidate.*     │
               └────────────┬────────────┘
                            │ XREADGROUP / XACK (Group: "event_logger")
                            ▼
               ┌─────────────────────────┐
               │      event_logger       │
               │ (Consumer Idempotente)  │
               │  - ProcessedEvent Table │
               └─────────────────────────┘
```

- **`fake_ats_alpha`** & **`fake_ats_beta`** (FastAPI): Mock dei vendor ATS. Persistono lo stato su file JSON mountati dall'host (`var/`) e utilizzano un `ChangeTracker` in memoria per aggiornare il timestamp di modifica (`updated_at` / `updated_timestamp`) ogni volta che il contenuto di un record varia.
- **`push_data_manager`** (Django standalone, no DRF): Orchestratore della sincronizzazione. Espone endpoint REST (`/api/v1/sync/<source>`), converte i dati tramite adapter dedicati, applica regole di business e invia i record puliti a `talent_pool` via gRPC.
- **`talent_pool`** (gRPC server con Django ORM): Repository centrale dei candidati. Esegue l'upsert atomico, calcola i campi variati in ordine alfabetico e persiste gli eventi in una tabella locale `OutboxEvent`. Un thread interno (`OutboxRelay`) pubblica gli eventi su Redis.
- **`event_logger`** (Worker Python con Django ORM): Consuma gli eventi da Redis Streams in un Consumer Group e garantisce la deduplicazione atomica a livello database tramite vincolo UNIQUE.

---

## 2. Contratti gRPC (`talent_pool.proto`)

La comunicazione tra l'orchestratore e il database centrale avviene su gRPC (HTTP/2 con payload binario Protobuf), garantendo tipizzazione statica e contratti formali.

```protobuf
syntax = "proto3";
package klaaryo.talent_pool.v1;
import "google/protobuf/timestamp.proto";

enum InternalStatus {
  INTERNAL_STATUS_UNSPECIFIED = 0;
  INTERNAL_STATUS_NEW = 1;
  INTERNAL_STATUS_IN_REVIEW = 2;
  INTERNAL_STATUS_REJECTED = 3;
  INTERNAL_STATUS_HIRED = 4;
}

message NormalizedCandidate {
  string external_id = 1;
  string ats_source = 2;
  string first_name = 3;
  string last_name = 4;
  string email = 5;
  string phone = 6;
  int32 age = 7;
  string job_external_id = 8;
  InternalStatus internal_status = 9;
  google.protobuf.Timestamp applied_at = 10;
}

message UpsertResult {
  int64 candidate_pk = 1;
  bool created = 2;
  repeated string changed_fields = 3;
}

service TalentPool {
  rpc UpsertCandidate(NormalizedCandidate) returns (UpsertResult);
  rpc GetCandidate(GetCandidateRequest) returns (Candidate);
  rpc ListCandidates(ListCandidatesRequest) returns (ListCandidatesResponse);
}
```

### Scelte di design del contratto:
- `ats_source` è una stringa libera (non un enum): `talent_pool` rimane completamente agnostico rispetto ai vendor esterni. L'aggiunta di un terzo ATS non richiede la ricompilazione del proto.
- Il server abilita gRPC Reflection (`reflection.enable_server_reflection`): permette l'ispezione runtime e il debug tramite utility come `grpcurl`.

---

## 3. Eventi e Payload

Gli eventi scaturiti dal ciclo di vita dei candidati vengono serializzati in JSON e inviati sull'event bus con due topic distinti:
- `candidate.created`: emesso al primo inserimento del candidato.
- `candidate.updated`: emesso solo se almeno uno dei campi tracciati è variato rispetto allo stato precedente nel DB.

### Struttura canonica del payload (`CandidateEvent`):
```json
{
  "event_id": "3f4cec58-fce8-4147-951f-df42dd1c3370",
  "event_type": "candidate.updated",
  "occurred_at": "2026-10-09T14:46:55Z",
  "candidate_pk": 4,
  "ats_source": "alpha",
  "external_id": "alpha-1004",
  "changed_fields": ["internal_status"]
}
```

- `event_id`: UUIDv4 generato alla creazione dell'evento, immutabile e usato come chiave di deduplicazione a valle.
- `changed_fields`: array ordinato alfabeticamente. Per `candidate.created` è sempre presente come array vuoto `[]`.

---

## 4. Gestione di ATS Multipli: Pattern Adapter + Registry

Per rispettare l'Open/Closed Principle ed evitare costrutti condizionali (`if ats_source == "alpha"`), la normalizzazione è organizzata in moduli dedicati:

1. **`AtsAdapter` (Porta astratta)**: Interfaccia con due soli metodi:
   - `fetch_since(since: datetime) -> list[RawApplication]`
   - `normalize(raw: RawApplication) -> NormalizedCandidate`
2. **Adapter specifici (`AlphaAdapter`, `BetaAdapter`)**:
   - `AlphaAdapter`: mappa date ISO-8601, stati specifici (`NEW`, `IN_REVIEW`, ecc.) e calcola l'età esatta alla data di candidatura con `age_at(birth_date, applied_at.date())`.
   - `BetaAdapter`: gestisce chiavi annidate (`contact.email_address`), timestamp Unix in secondi ed effettua lo split del nome `full_name.split(maxsplit=1)`.
3. **Registry esplicito (`registry.py`)**:
   - Mappa `dict[source_name -> AdapterClass]`.
   - Funzione `build_adapter(source)` che recupera l'URL dal setting di configurazione. Aggiungere un nuovo ATS richiede solo un nuovo modulo adapter e una riga nel registry.
4. **Validazione di Business centralizzata (`candidate_rules.py`)**:
   - Gli adapter traducono i dati ma non decidono l'ammissibilità. Le regole comuni (presenza del nome, email valida, presenza del numero di telefono per l'AI e maggiore età `age >= 18`) sono applicate a valle nel manager.

---

## 5. Event Bus: Redis Streams & Transactional Outbox

### Perché Redis Streams:
A differenza del classico Redis Pub/Sub (che è volatile: se il consumer è giù durante l'invio, i messaggi vengono persi), Redis Streams implementa un log persistente append-only con:
- **Consumer Groups** (`event_logger`): tracciamento dell'offset di lettura.
- **Acknowledgment esplicito (`XACK`)**: il messaggio viene confermato solo a completamento della lavorazione. Se il worker fallisce, il messaggio rimane nella Pending Entries List e viene riconsegnato.

### Il Transactional Outbox Pattern:
Per eliminare il rischio di disallineamento tra database e broker (Dual-Write Problem):
1. Quando `TalentPool.UpsertCandidate` rileva una creazione o una modifica, scrive il record `Candidate` e contemporaneamente inserisce una riga nella tabella `OutboxEvent` all'interno della **stessa transazione SQL atomica** (`transaction.atomic()`).
2. Un thread daemon (`OutboxRelay`) fa il polling della tabella `OutboxEvent` per i record con `published_at IS NULL`.
3. Per ciascun evento invia il payload tramite `XADD` su Redis Streams e solo dopo l'esito positivo imposta `published_at = now()`.
4. In caso di crash intermedio, l'evento viene reinviato al riavvio (*at-least-once*), lasciando la gestione dei duplicati al vincolo UNIQUE sul consumer.
