# coding: utf-8
from __future__ import print_function, unicode_literals

from types import TracebackType
from typing import Any, Generator


class ClicktailContext:
    def __init__(self) -> None:
        self.extras: list[dict[str, dict]] = []

    def context(self, *args: Any, **kwargs: dict) -> "ClicktailContext":
        if args:
            raise ValueError("All contexts must be passed by name as keyword arguments")
        for key, val in kwargs.items():
            if not isinstance(val, dict):
                raise ValueError("All contexts must be dictionaries: %s" % key)
        self.extras.append(kwargs)
        return self

    def __call__(self, *args: Any, **kwargs: Any) -> "ClicktailContext":
        return self.context(*args, **kwargs)

    def __enter__(self) -> Generator["ClicktailContext", None, None]:
        yield self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> "ClicktailContext | bool":
        if exc_type is not None:
            return False
        self.extras.pop()
        return self

    def exists(self) -> bool:
        return bool(self.extras)

    def collapse(self) -> dict[str, Any]:
        x: dict[str, Any] = {}
        for contexts in self.extras:
            for name, data in contexts.items():
                x.setdefault(name, {}).update(data)
        return x


LogtailContext = ClicktailContext

DEFAULT_CONTEXT = ClicktailContext()
