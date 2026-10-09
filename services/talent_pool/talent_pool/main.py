"""Composition root for the talent_pool gRPC service."""
from __future__ import annotations

import logging
import os
import sys
from concurrent import futures

import django
import grpc
from grpc_reflection.v1alpha import reflection

# Django setup must happen before importing models/managers
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from klaaryo_bus import publisher_from_env
from klaaryo_contracts import talent_pool_pb2, talent_pool_pb2_grpc
from talent_pool.grpc_handlers.servicer import TalentPoolServicer
from talent_pool.managers.candidate_manager import CandidateManager
from talent_pool.managers.outbox_relay import OutboxRelay

logger = logging.getLogger(__name__)


def serve() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        stream=sys.stdout,
    )

    # Wiring
    publisher = publisher_from_env()
    relay = OutboxRelay(publisher)
    relay.start_daemon(interval=0.5)

    manager = CandidateManager()
    servicer = TalentPoolServicer(manager)

    server = grpc.server(futures.ThreadPoolExecutor(max_workers=4))
    talent_pool_pb2_grpc.add_TalentPoolServicer_to_server(servicer, server)

    # Enable reflection
    service_names = (
        talent_pool_pb2.DESCRIPTOR.services_by_name["TalentPool"].full_name,
        reflection.SERVICE_NAME,
    )
    reflection.enable_server_reflection(service_names, server)

    port = os.environ.get("GRPC_PORT", "50051")
    server.add_insecure_port(f"[::]:{port}")
    logger.info("TalentPool gRPC server starting on port %s", port)
    server.start()
    server.wait_for_termination()


if __name__ == "__main__":
    serve()
