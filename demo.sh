#!/usr/bin/env bash
set -euo pipefail

# Colors
BOLD='\033[1m'
GREEN='\033[32m'
YELLOW='\033[33m'
RESET='\033[0m'

format_json() {
    if command -v jq &>/dev/null; then
        jq .
    else
        cat
    fi
}

wait_for() {
    local url=$1
    local max_attempts=${2:-30}
    local attempt=0
    while [ "$(curl -s -o /dev/null -w "%{http_code}" "$url" 2>/dev/null || echo "000")" = "000" ]; do
        attempt=$((attempt + 1))
        if [ $attempt -ge $max_attempts ]; then
            echo "Timeout waiting for $url"
            exit 1
        fi
        sleep 1
    done
}

echo -e "${BOLD}=== Klaaryo ATS Integration Demo ===${RESET}"
echo

# Reset
echo -e "${YELLOW}Resetting environment...${RESET}"
make reset 2>/dev/null || true
make up

echo -e "${YELLOW}Waiting for services to be ready...${RESET}"
wait_for "http://localhost:8001/api/applications"
wait_for "http://localhost:8002/v2/candidates"
wait_for "http://localhost:8000/api/v1/sync/alpha/status" 60
sleep 3

# Step 1: Sync Alpha
echo
echo -e "${BOLD}Step 1: Sync Alpha${RESET}"
echo "Expected: 13 pulled, 7 pushed, 6 skipped"
echo
curl -s -X POST http://localhost:8000/api/v1/sync/alpha | format_json
echo

sleep 2
echo -e "${GREEN}Candidates in talent pool (Alpha):${RESET}"
docker compose run --rm grpcurl -plaintext -d '{"ats_source":"alpha"}' talent_pool:50051 klaaryo.talent_pool.v1.TalentPool/ListCandidates 2>/dev/null | format_json
echo

echo -e "${GREEN}Created events (Alpha):${RESET}"
docker compose exec event_logger python -m event_logger.tools.show_events --type candidate.created --source alpha
echo

# Step 2: Sync Beta
echo -e "${BOLD}Step 2: Sync Beta${RESET}"
echo "Expected: 13 pulled, 7 pushed, 6 skipped"
echo
curl -s -X POST http://localhost:8000/api/v1/sync/beta | format_json
echo

sleep 2
echo -e "${GREEN}Candidates in talent pool (Beta):${RESET}"
docker compose run --rm grpcurl -plaintext -d '{"ats_source":"beta"}' talent_pool:50051 klaaryo.talent_pool.v1.TalentPool/ListCandidates 2>/dev/null | format_json
echo

# Step 3: Second sync Alpha (idempotent)
echo -e "${BOLD}Step 3: Second sync Alpha (idempotent)${RESET}"
echo "Expected: records re-pulled due to overlap, but 0 created, 0 updated"
echo
curl -s -X POST http://localhost:8000/api/v1/sync/alpha | format_json
echo

# Step 4: Modify alpha-1004 and sync
echo
echo -e "${BOLD}Step 4: Modify alpha-1004 (IN_REVIEW -> HIRED) and sync${RESET}"
echo "Expected: 1 updated, event candidate.updated with changed_fields=[\"internal_status\"]"
echo
docker compose exec fake_ats_alpha python tools/set_field.py alpha-1004 application_status HIRED
sleep 1
curl -s -X POST http://localhost:8000/api/v1/sync/alpha | format_json
echo

sleep 2
echo -e "${GREEN}Updated events:${RESET}"
docker compose exec event_logger python -m event_logger.tools.show_events --type candidate.updated --source alpha
echo

# Step 5: Simulate duplicate delivery
echo -e "${BOLD}Step 5: Simulate duplicate event delivery${RESET}"
echo "Expected: event_logger shows [SKIPPED] ... duplicate"
echo
docker compose exec talent_pool python -m talent_pool.tools.republish_event --last
sleep 2
echo -e "${GREEN}Event logger logs (last 5 lines):${RESET}"
docker compose logs event_logger --tail 5
echo

# Step 6: Status
echo -e "${BOLD}Step 6: Sync status${RESET}"
echo
curl -s http://localhost:8000/api/v1/sync/alpha/status | format_json
echo

echo -e "${BOLD}${GREEN}Demo completed!${RESET}"
