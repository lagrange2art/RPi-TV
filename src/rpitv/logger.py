import logging
from pathlib import Path
from ansi2html import Ansi2HTMLConverter


LOG_FORMAT = "%(levelname)s %(name)s: %(message)s"
LOG_PATH = Path("logs/rpitv.log")
MAX_LOG_LINES = 1000


class LineLimitedFileHandler(logging.Handler):
    def __init__(self, log_path, max_lines):
        super().__init__()
        self.log_path = Path(log_path)
        self.max_lines = max_lines
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

    def emit(self, record):
        try:
            with self.log_path.open("a", encoding="utf-8") as log_file:
                log_file.write(self.format(record) + "\n")

            lines = self.log_path.read_text(encoding="utf-8").splitlines(keepends=True)
            if len(lines) > self.max_lines:
                self.log_path.write_text(
                    "".join(lines[-self.max_lines:]),
                    encoding="utf-8",
                )
        except Exception:
            self.handleError(record)


def ansi_to_html(log_content):
    converter = Ansi2HTMLConverter(inline=True)
    return converter.convert(log_content, full=False)


def configure_logging(log_file=None, max_lines=MAX_LOG_LINES):
    log_path = Path(log_file) if log_file is not None else LOG_PATH
    log_path.parent.mkdir(parents=True, exist_ok=True)

    logging.basicConfig(
        level=logging.INFO,
        format=LOG_FORMAT,
        handlers=[
            LineLimitedFileHandler(log_path, max_lines),
            logging.StreamHandler(),
        ],
        force=True,
    )