import logging

from infrastructure.logging_config import configure_logging


def test_pika_is_quiet_so_a_reconnection_prints_no_info_lines():
    logging.getLogger("pika").setLevel(logging.NOTSET)

    configure_logging("INFO")

    assert logging.getLogger("pika").getEffectiveLevel() == logging.WARNING
