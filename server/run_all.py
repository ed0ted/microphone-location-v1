from __future__ import annotations

import argparse
import asyncio
import logging
import threading

from .config import FusionConfig, load_config
from .fusion_receiver import run_receiver
from .localization import LocalizationEngine
from .state_store import FrameStore
from .web import app as web_app

LOGGER = logging.getLogger("server")


def _setup_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(level=level, format="%(asctime)s | %(levelname)s | %(name)s | %(message)s")


async def _async_main(config: FusionConfig, store: FrameStore) -> None:
    receiver_task = asyncio.create_task(run_receiver(config.listen_host, config.listen_port, store))
    try:
        await receiver_task
    except asyncio.CancelledError:
        pass


def run_services(config: FusionConfig, store: FrameStore) -> None:
    localization = LocalizationEngine(config, store)
    localization.start()

    def _run_web():
        web_app.init_app(store, config)
        web_app.run(host=config.web.host, port=config.web.port)

    web_thread = threading.Thread(target=_run_web, daemon=True)
    web_thread.start()

    asyncio.run(_async_main(config, store))


def main():
    parser = argparse.ArgumentParser(description="Fusion server runtime")
    parser.add_argument("--config", default="configs/server.yaml", help="Path to fusion server config")
    parser.add_argument("--verbose", action="store_true", help="Enable debug logging")
    args = parser.parse_args()
    _setup_logging(args.verbose)
    config = load_config(args.config)
    store = FrameStore()
    run_services(config, store)


if __name__ == "__main__":
    main()
