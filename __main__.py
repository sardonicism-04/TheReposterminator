import argparse
import sys
import logging

from .bot import BotClient, logger

client = BotClient()

logging_level_mapping = {
    'info': logging.INFO,
    'debug': logging.DEBUG,
    'warning': logging.WARNING,
    'error': logging.ERROR,
    'critical': logging.CRITICAL
}

parser = argparse.ArgumentParser()
parser.add_argument('-r', '--run', action='store_true', help='Runs the bot')
parser.add_argument('-s', '--show', action='store_true', help='Lists all subreddits the bot is currently active on')
parser.add_argument('-l', '--level', nargs='?', choices=['info', 'debug', 'warning', 'error', 'critical'])

args = parser.parse_args()

if args.show:
    print(client._show_subreddits())
    sys.exit()

if args.run:
    client.run()

if args.level:
    logger.setLevel(logging_level_mapping[args.level])
