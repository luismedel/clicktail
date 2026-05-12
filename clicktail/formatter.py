# coding: utf-8
from __future__ import print_function, unicode_literals

import json
import logging
from typing import Any, Type

from .frame import create_frame
from .helpers import DEFAULT_CONTEXT, ClicktailContext


class ClicktailFormatter(logging.Formatter):
    def __init__(
        self,
        context: ClicktailContext = DEFAULT_CONTEXT,
        json_default: Any = None,
        json_encoder: Type[json.JSONEncoder] | None = None,
    ) -> None:
        self.context = context
        self.json_default = json_default
        self.json_encoder = json_encoder

    def format(self, record: logging.LogRecord) -> str:
        # Because the formatter does not have an underlying format string for
        # which `extra` may be used to substitute arguments (see
        # https://docs.python.org/2/library/logging.html#logging.debug ), we
        # augment the log frame with all of the entries in extra.
        frame = create_frame(
            record, record.getMessage(), self.context, include_extra_attributes=True
        )
        return json.dumps(frame, default=self.json_default, cls=self.json_encoder)
