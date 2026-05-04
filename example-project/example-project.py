# This is an example project of clicktail python integration
# This project showcases how to use clicktail in your python projects
# For more information please visit the clicktail repository

# SETUP

# Import clicktail client library and default logging library
import logging
import os

from clicktail import ClickHouseHandler


def require_env(name):
    value = os.environ.get(name)
    if not value:
        raise RuntimeError("Missing required environment variable: {}".format(name))
    return value


host = require_env("CLICKTAIL_HOST")
database = require_env("CLICKTAIL_DATABASE")
table = require_env("CLICKTAIL_TABLE")
username = require_env("CLICKTAIL_USERNAME")
password = require_env("CLICKTAIL_PASSWORD")

# Create handler
handler = ClickHouseHandler(
    host=host,
    database=database,
    table=table,
    username=username,
    password=password,
)

# Create logger
logger = logging.getLogger(__name__)
logger.handlers = []
logger.setLevel(logging.DEBUG)  # Set minimal log level
logger.addHandler(handler)  # assign handler to logger

# LOGGING EXAMPLE
# Following code showcases logger usage

# Send debug log using the debug() method
logger.debug("I am using clicktail!")

# Send info level log about interesting events using the info() method
logger.info("I love clicktail!")

# Send warning level log about worrying events using the warning() method
# You can also add custom structured information to the log by passing it as a
# second argument
logger.warning(
    "Log structured data",
    extra={"item": {"url": "https://fictional-store.com/item-123", "price": 100.00}},
)

# Send error level log about errors in runtime using the error() method
logger.error("Oops! An error occurred!")

# Send critical level log about critical events in runtime using the critical() method
logger.critical("Its not working, needs to be fixed ASAP!")


def raise_example_error():
    raise NameError("example exception for logger.exception()")


# Send exception level log about errors in runtime using the exception() method
# Error level log will be sent. Exception info is added to the logging message.
# This method should only be called from an exception handler.
try:
    raise_example_error()
except Exception:
    logger.exception("Error occurred while calling non-existing function")
    # Additional info will be added
    # OUTPUT:
    # Error occurred while calling non-existing function
    # Traceback (most recent call last):
    #   File "logtail.py", line 48, in
    #       nonexisting_function()
    # NameError: name 'nonexisting_function' is not defined

print(f"""All done! You can check your logs now.

- Go to: {host}/play
- Run: select * from {database}.{table}
""")
