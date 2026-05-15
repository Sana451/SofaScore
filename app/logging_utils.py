from __future__ import annotations

import logging


def configure_logging(level_name: str) -> None:
    level = getattr(logging, level_name.upper(), logging.INFO)
    root = logging.getLogger()

    if not root.handlers:
        logging.basicConfig(
            level=level,
            format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        )
    else:
        root.setLevel(level)
        for handler in root.handlers:
            handler.setLevel(level)

    logging.getLogger("app").setLevel(level)
    logging.getLogger("app.poller").setLevel(level)
