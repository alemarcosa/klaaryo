#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
python -m grpc_tools.protoc \
  -I . \
  --python_out=. \
  --grpc_python_out=. \
  --pyi_out=. \
  klaaryo_contracts/talent_pool.proto
