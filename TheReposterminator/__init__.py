"""
TheReposterminator Reddit bot to detect reposts
Copyright (C) 2021 sardonicism-04

TheReposterminator is free software: you can redistribute it and/or modify
it under the terms of the GNU Affero General Public License as published by the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

TheReposterminator is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU Affero General Public License for more details.

You should have received a copy of the GNU Affero General Public License
along with TheReposterminator.  If not, see <https://www.gnu.org/licenses/>.
"""
import logging
from collections import namedtuple

import praw
from prawcore import exceptions
import psycopg2
import toml

from .interactive import Interactive
from .sentry import Sentry

# Define namedtuples
SubData = namedtuple("SubData", "subname indexed")

# Set up logging
logger = logging.getLogger(__name__)
formatting = "[%(asctime)s] [%(levelname)s:%(name)s] %(message)s"
logging.basicConfig(
    format=formatting,
    level=logging.INFO,
    handlers=[logging.FileHandler("rterm.log", "w", "utf-8"),
              logging.StreamHandler()])


class BotClient:
    """The main Reposterminator object"""

    def __init__(self):
        self.sentry = Sentry(self)
        self.interactive = Interactive(self)

        self.subreddits = []
        self.subreddit_configs = {}

        self.config = self.load_config()
        self.setup_connections()
        self.update_subs()

    def load_config(self, fp="config.toml"):
        return toml.load(fp)

    def setup_connections(self):
        """Establishes a Reddit and database connection"""
        try:
            self.db = psycopg2.connect(
                connect_timeout=5,
                **self.config["database"]
            )  # If your server is slow to connect to, increase this value
            self.insert_cursor = self.db.cursor()

            self.reddit = praw.Reddit(**self.config["reddit"])

        except Exception as e:
            logger.critical(f"Connection setup failed; exiting: {e}")
            exit(1)

        else:
            logger.info(
                "✅ Reddit and database connections successfully established"
            )

    def run(self):
        """
        Runs the bot (this is blocking!)
        """

        while True:
            self.handle_dms()  # In case there are no subs

            for sub in self.subreddits:
                self.get_configs()
                self.handle_dms()

                if not sub.indexed:
                    # Needs to be full-scanned first
                    self.sentry.scan_new_sub(sub)
                if sub.indexed:
                    # Scanned with intention of reporting now
                    self.sentry.scan_submissions(sub)

    def update_subs(self):
        """Updates the list of subreddits"""

        self.subreddits.clear()

        with self.db.cursor() as cur:
            cur.execute("SELECT * FROM subreddits")
            for sub, indexed in cur.fetchall():
                self.subreddits.append(SubData(sub, indexed))
        self.db.commit()

        logger.debug("Updated list of subreddits")

    def get_configs(self):
        self.subreddit_configs.clear()

        for subname, indexed in self.subreddits:
            try:
                config_wiki = self.reddit.subreddit(subname) \
                    .wiki["thereposterminator_config"]

                sub_config = toml.loads(
                    config_wiki.content_md
                )
                template_config = toml.load(
                    "subreddit_config.toml"
                )
                for key, value in template_config.items():
                    if not sub_config.get(key):
                        sub_config.update({key: value})
                # ^ Update the value of the sub config with any
                # newly added keys, useful if a sub has an outdated
                # config

            except (exceptions.NotFound, exceptions.Forbidden):
                sub_config = toml.load(
                    "subreddit_config.toml"
                )

            self.subreddit_configs[subname] = sub_config

    def get_sub(self, subname):
        try:
            return next(filter(
                lambda sub: sub.subname == subname,
                self.subreddits
            ))
        except StopIteration:
            return None

    def reply(self, content, *, target):
        """An abstraction of PRAW's replying so that the content can
        be made uniform"""

        content += self.config["templates"]["bot_notice"]
        return target.reply(content)

    def handle_dms(self):
        """Checks direct messages for new subreddits and removals"""
        for msg in self.reddit.inbox.unread(mark_read=True):

            if "username mention" in msg.subject.lower():
                if (
                    self.subreddit_configs
                    [msg.subreddit.display_name]
                    ["respond_to_mentions"]
                ):
                    self.interactive.receive_mention(msg)

            if hasattr(msg, "subreddit"):
                # Confirm that the message is from a subreddit
                if msg.body.startswith(("**gadzooks!", "gadzooks!")) \
                        or "invitation to moderate" in msg.subject:
                    self.accept_invite(msg)
                elif "You have been removed as a moderator from " in msg.body:
                    self.handle_mod_removal(msg)

            msg.mark_read()

    def accept_invite(self, msg):
        """Accepts an invite to a new subreddit and adds it to the database"""
        msg.subreddit.mod.accept_invite()
        self.insert_cursor.execute(
            """
            INSERT INTO subreddits
            VALUES(
                %s,
                FALSE
            ) ON CONFLICT DO NOTHING""",
            (str(msg.subreddit),)
        )
        self.update_subs()

        self.db.commit()
        logger.info(f"✅ Accepted mod invite to r/{msg.subreddit}")

        try:
            msg.subreddit.wiki["thereposterminator_config"].content_md
            # Avoid overwriting an existing wiki

        except exceptions.NotFound:
            msg.subreddit.wiki.create(
                "thereposterminator_config",
                open("subreddit_config.toml", "r").read(),
                reason="Create TheReposterminator config"
            )

        except exceptions.Forbidden:
            return

    def handle_mod_removal(self, msg):
        """Handles removal from a subreddit"""
        self.insert_cursor.execute(
            "DELETE FROM subreddits WHERE name=%s",
            (str(msg.subreddit),)
        )
        self.update_subs()

        self.db.commit()
        logger.info(f"✅ Handled removal from r/{msg.subreddit}")

    @staticmethod
    def compare_hashes(hash1, hash2):
        hash1 = int(hash1)
        hash2 = int(hash2)
        return int(((64 - bin(hash1 ^ hash2).count("1")) * 100.0) / 64.0)
