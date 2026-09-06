import logging
import re

from rpitv.logger import configure_logging


def test_configure_logging_writes_formatted_record(tmp_path, capsys):
    log_file = tmp_path / "rpitv.log"
    configure_logging(log_file)

    logging.getLogger("test.logging").info("test message")

    log_line = log_file.read_text().strip()
    command_line = capsys.readouterr().err.strip()

    assert log_line == "INFO test.logging: test message" 
    assert command_line == "INFO test.logging: test message" 



def test_configure_logging_discards_oldest_lines(tmp_path):
    log_file = tmp_path / "rpitv.log"
    configure_logging(log_file, max_lines=3)
    logger = logging.getLogger("test.logging.limit")

    for line_number in range(1, 5):
        logger.info("line %d", line_number)

    lines = log_file.read_text().splitlines()
    assert len(lines) == 3
    assert "line 1" not in lines
    assert "line 2" in lines[0]
    assert "line 4" in lines[-1]