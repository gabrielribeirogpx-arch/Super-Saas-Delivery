from __future__ import annotations

import logging
from collections import defaultdict
from typing import Any, Callable, DefaultDict, List


Handler = Callable[[dict[str, Any]], None]


class EventBus:
    def __init__(self) -> None:
        self._handlers: DefaultDict[str, List[Handler]] = defaultdict(list)
        self._logger = logging.getLogger(__name__)

    def emit(self, event_name: str, payload: dict[str, Any]) -> None:
        handlers = list(self._handlers.get(event_name, []))
        if not handlers:
            self._logger.debug("EventBus: no handlers for %s", event_name)
            return
        for handler in handlers:
            try:
                handler(payload)
            except Exception:
                self._logger.exception("EventBus handler failed for %s", event_name)

    def subscribe(self, event_name: str, handler: Handler) -> None:
        self._handlers[event_name].append(handler)


event_bus = EventBus()
