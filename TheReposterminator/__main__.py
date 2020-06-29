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
    'critical': logging.CRITICAL,
    'notset': logging.NOTSET
}

parser = argparse.ArgumentParser(description='Provides tools to interact with and run the bot')
parser.add_argument('-r', '--run', action='store_true', help='Runs the bot')
parser.add_argument('-s', '--show', action='store_true', help='Lists all subreddits the bot is currently active on')
parser.add_argument('-l', '--level', nargs='?', choices=['info', 'debug', 'warning', 'error', 'notset', 'critical'],
                    help='Sets the logging level to use when running the bot')

args = parser.parse_args()

if args.show:
    subnames = '\n'.join(s.subname for s in client)
    print(f'{len(client):,} Total\n------------------\n{subnames}') 
    sys.exit()

if args.level:
    logger.setLevel(logging_level_mapping[args.level])
    logger.info(f"Set logging level to {logging_level_mapping[args.level]}")

if args.run:
    client.run()

