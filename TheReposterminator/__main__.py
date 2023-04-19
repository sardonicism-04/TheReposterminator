"""
TheReposterminator Reddit bot to detect reposts
Copyright (C) 2023 sardonicism-04

TheReposterminator is free software: you can redistribute it and/or modify
it under the terms of the GNU Affero General Public License as published
by the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

TheReposterminator is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU Affero General Public License for more details.

You should have received a copy of the GNU Affero General Public License
along with TheReposterminator.  If not, see <https://www.gnu.org/licenses/>.
"""
import argparse
import logging
import os

from TheReposterminator import BotClient, formatters

# LOGGING

if os.name == "nt":
    os.system("color")

LOGGERS = [
    logging.getLogger("TheReposterminator"),
    logging.getLogger("prawcore"),
    logging.getLogger("praw"),
]

formatter = formatters.ColoredLoggingFormatter(
    fmt="[{asctime}] [{levelname} {name} {funcName}] {message}"
)
handler = logging.StreamHandler()
handler.setFormatter(formatter)

[
    (
        logger.setLevel(logging.INFO),
        logger.addHandler(handler),
        logger.addHandler(logging.FileHandler("rterm.log", "w", "utf-8")),
    )
    for logger in LOGGERS
]

# CLI

LOG_LEVEL_MAPPING = {
    "info": logging.INFO,
    "debug": logging.DEBUG,
    "warning": logging.WARNING,
    "error": logging.ERROR,
    "critical": logging.CRITICAL,
    "notset": logging.NOTSET,
}

parser = argparse.ArgumentParser(
    description="Provides tools to interact with and run the bot"
)
parser.add_argument("-r", "--run", action="store_true", help="Runs the bot")
parser.add_argument(
    "-l",
    "--level",
    nargs="?",
    choices=["info", "debug", "warning", "error", "notset", "critical"],
    help="Sets the logging level to use when running the bot",
)

# RUNNER


def main():
    args = parser.parse_args()

    if args.level:
        [logger.setLevel(LOG_LEVEL_MAPPING[args.level]) for logger in LOGGERS]

    if args.run:
        client = BotClient()
        client.run()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logging.getLogger("TheReposterminator").info("Exiting process")
