# Klaaryo ATS Integration

Sistema di integrazione multi-ATS che normalizza candidature da sorgenti eterogenee, le centralizza in un talent pool e traccia ogni modifica con un event log idempotente.

## Prerequisiti

- Docker e Docker Compose
- `curl` (per il demo)
- `jq` (opzionale, per formattare l'output JSON)

## Quick Start

```bash
make up        # Avvia tutto lo stack
make test      # Esegue i test unitari + lint-imports
make e2e       # Reset + test end-to-end
./demo.sh      # Demo interattivo narrato
make reset     # Pulisce tutto (volumi + var/)
```

## Servizi e porte

| Servizio | Porta | Descrizione |
|---|---|---|
| `fake_ats_alpha` | 8001 | ATS fake con API REST (format ISO) |
| `fake_ats_beta` | 8002 | ATS fake con API REST (format Unix timestamp) |
| `push_data_manager` | 8000 | Orchestratore sync, espone API REST |
| `talent_pool` | 50051 | Servizio gRPC per il talent pool |
| `event_logger` | - | Consumer eventi da Redis Streams |
| `redis` | 6379 | Event bus (Redis Streams) |

## API

### Sync
```bash
# Avvia sync per un ATS
curl -X POST http://localhost:8000/api/v1/sync/alpha
curl -X POST http://localhost:8000/api/v1/sync/beta

# Stato dell'ultima sync
curl http://localhost:8000/api/v1/sync/alpha/status
```

### gRPC (con grpcurl)
```bash
# Lista candidati
docker compose run --rm grpcurl -plaintext -d '{"ats_source":"alpha"}' \
  talent_pool:50051 klaaryo.talent_pool.v1.TalentPool/ListCandidates

# Dettaglio candidato
docker compose run --rm grpcurl -plaintext -d '{"candidate_pk":1}' \
  talent_pool:50051 klaaryo.talent_pool.v1.TalentPool/GetCandidate
```

## Modifica manuale delle fixture

È possibile modificare direttamente i file delle fixture degli ATS:

```bash
# Tramite tool
docker compose exec fake_ats_alpha python tools/set_field.py alpha-1004 application_status HIRED

# Oppure editando direttamente il file
vim var/ats_alpha/applications.json
```

Dopo la modifica, il `ChangeTracker` rileva il cambiamento al prossimo sync e aggiorna `updated_at`.

## Reset completo

```bash
make reset   # docker compose down -v + rm -rf var/
```

Questo elimina tutti i volumi Docker e le fixture persistite, riportando lo stack allo stato iniziale.
