import argparse
import sys

from .bot import BotClient

client = BotClient()

parser = argparse.ArgumentParser()
parser.add_argument('-r', '--run', action='store_true', help='Runs the bot')
parser.add_argument('-s', '--show', action='store_true', help='Lists all subreddits the bot is currently active on')

args = parser.parse_args()

if args.show:
    print(client._show_subreddits())
    sys.exit()

if args.run:
    client.run()
