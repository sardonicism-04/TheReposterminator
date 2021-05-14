"""
TheReposterminator Reddit bot to detect reposts
Copyright (C) 2021 sardonicism-04

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
import logging
from collections import namedtuple

import praw
import psycopg2
import toml

from .sentry import Sentry
from .interactive import Interactive

# Define namedtuples
SubData = namedtuple("SubData", "subname indexed")

# Set up logging
logger = logging.getLogger(__name__)
formatting = "[%(asctime)s] [%(levelname)s:%(name)s] %(message)s"
logging.basicConfig(
    format=formatting,
    level=logging.INFO,
    handlers=[logging.FileHandler("rterm.log"),
              logging.StreamHandler()])


class BotClient:
    """The main Reposterminator object"""

    def __init__(self):
        self.sentry = Sentry(self)
        self.interactive = Interactive(self)

        self.subreddits = []

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

        self.handle_dms()  # In case there are no subs TODO handle in loop
        while True:
            for sub in self.subreddits:
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

    def handle_dms(self):
        """Checks direct messages for new subreddits and removals"""
        for msg in self.reddit.inbox.unread(mark_read=True):

            if "username mention" in msg.subject.lower():
                # TODO: Dispatch to self.interactive
                ...

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

    def handle_mod_removal(self, msg):
        """Handles removal from a subreddit"""
        self.insert_cursor.execute(
            "DELETE FROM subreddits WHERE name=%s",
            (str(msg.subreddit),)
        )
        self.update_subs()

        self.db.commit()
        logger.info(f"✅ Handled removal from r/{msg.subreddit}")
