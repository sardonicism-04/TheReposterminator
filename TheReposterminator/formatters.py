from enum import Enum
from logging import Formatter, LogRecord


class Color(Enum):
    RESET = "0"
    PURPLE = "38;2;162;155;254"
    GREEN = "38;2;186;230;126"
    CYAN = "38;2;92;207;230"
    GREY = "38;2;112;122;140"
    SILVER = "38;2;92;103;115"
    TAN = "38;2;255;230;179"
    ORANGE = "38;2;255;167;89"
    RED = "38;2;255;51;51"

    def __new__(cls, value):
        obj = object.__new__(cls)
        obj._value_ = f"\033[{value}m"
        return obj

    def __call__(self, string: str):
        return f"{self.value}{string}{Color.RESET.value}"


class ColoredLoggingFormatter(Formatter):
    COLORS = {
        "DEBUG": Color.SILVER,
        "INFO": Color.GREEN,
        "WARNING": Color.TAN,
        "ERROR": Color.ORANGE,
        "CRITICAL": Color.RED,
    }

    def __init__(self, **kwargs):
        kwargs["style"] = "{"
        kwargs["datefmt"] = Color.CYAN("%d-%m-%Y %H:%M:%S")
        super().__init__(**kwargs)

    def format(self, record: LogRecord):
        record.asctime = Color.CYAN(self.formatTime(record, self.datefmt))
        record.msg = Color.GREY(record.msg)
        record.name = Color.PURPLE(record.name)
        record.levelname = self.COLORS[record.levelname](record.levelname)
        return super().format(record)
