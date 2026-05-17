"""Standalone worker/receiver entrypoint.

Usage:
    python -m app.workers.run monitoring-policies
    python -m app.workers.run topology
    python -m app.workers.run reports
    python -m app.workers.run trap-receiver
    python -m app.workers.run syslog-receiver
    python -m app.workers.run telemetry-receiver
"""

from __future__ import annotations

import argparse
import asyncio
import signal

from loguru import logger

from app.database import init_db
from app.workers.supervisor import WorkerSupervisor


WORKER_METHODS = {
    "monitoring-policies": "_run_monitoring_policy_loop",
    "poller": "_run_monitoring_policy_loop",
    "topology": "_run_topology_rebuilder_loop",
    "reports": "_run_report_scheduler_loop",
    "trap-receiver": "_run_trap_receiver_loop",
    "syslog-receiver": "_run_syslog_receiver_loop",
    "telemetry-receiver": "_run_telemetry_receiver_loop",
}


async def run_worker(kind: str) -> None:
    """Run one long-lived worker loop until cancelled."""
    if kind not in WORKER_METHODS:
        raise ValueError(f"Unknown worker kind: {kind}")

    await init_db()
    supervisor = WorkerSupervisor()
    loop = asyncio.get_running_loop()

    def _stop() -> None:
        logger.info("Stop requested for {}", kind)
        supervisor._stop_event.set()  # noqa: SLF001 - intentional standalone runner bridge

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _stop)
        except NotImplementedError:
            pass

    method_name = WORKER_METHODS[kind]
    method = getattr(supervisor, method_name)
    logger.info("Starting standalone worker: {}", kind)
    await method()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run one NMS_Custom worker/receiver")
    parser.add_argument("kind", choices=sorted(WORKER_METHODS))
    args = parser.parse_args()
    asyncio.run(run_worker(args.kind))


if __name__ == "__main__":
    main()
