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
import operator
from collections import namedtuple
from contextlib import suppress
from datetime import datetime
from io import BytesIO

import praw
import psycopg2
import requests
from PIL import Image, UnidentifiedImageError

from .config import (db_host, db_name, db_pass, db_user, reddit_agent,
                     reddit_id, reddit_name, reddit_pass, reddit_secret)
from .differencer import diff_hash

# Constant that sets the confidence threshold at which submissions are reported
THRESHOLD = 88

# Other constants
ROW_TEMPLATE = (
    "/u/\N{ZWSP}{0} | {1} | [URL]({2}) | [{3}](https://redd.it/{4})"
    " | {5} | {6} | {7}%\n"
)
INFO_TEMPLATE = (
    "User | Date | Image | Title | Karma | Status | "
    "Similarity\n:---|:---|:---|:---|:---|:---|:---|:---\n{0}"
)

# Define namedtuples
SubData = namedtuple("SubData", "subname indexed")
MediaData = namedtuple("MediaData", "hash id subname")
Match = namedtuple("Match", "hash id subname similarity")

# Set up logging
logger = logging.getLogger(__name__)
formatting = "[%(asctime)s] [%(levelname)s:%(name)s] %(message)s"
logging.basicConfig(
    format=formatting,
    level=logging.INFO,
    handlers=[logging.FileHandler("rterm.log"),
              logging.StreamHandler()])


def fetch_media(img_url):
    """Fetches submission media"""
    if not any(a in img_url for a in (".jpg", ".png", ".jpeg")):
        return False

    with requests.get(img_url) as resp:
        try:
            return Image.open(BytesIO(resp.content))
        except UnidentifiedImageError:
            logger.debug("Encountered unidentified image, ignoring")
            return False


class BotClient:
    """The main Reposterminator object"""

    def __init__(self):
        # Store problematic IDs in a cache to prevent recurring errors
        self.ignored_id_cache = set()
        self.setup_connections()
        self.subreddits = []
        self.update_subs()

    def setup_connections(self):
        """Establishes a Reddit and database connection"""
        try:
            self.conn = psycopg2.connect(
                dbname=db_name,
                user=db_user,
                host=db_host,
                password=db_pass,
                connect_timeout=5
            )  # If your server is slow to connect to, increase this value
            self.insert_cursor = self.conn.cursor()

            self.reddit = praw.Reddit(
                client_id=reddit_id,
                client_secret=reddit_secret,
                password=reddit_pass,
                user_agent=reddit_agent,
                username=reddit_name
            )

        except Exception as e:
            logger.critical(f"Connection setup failed; exiting: {e}")
            exit(1)

        else:
            logger.info(
                "✅ Reddit and database connections successfully established")

    def run(self):
        """Runs the bot
        This function is entirely blocking, so any calls to other functions
        must be made prior to calling this."""
        self.handle_dms()  # In case there are no subs
        while True:
            for sub in self.subreddits:
                self.handle_dms()
                if not sub.indexed:
                    self.scan_new_sub(sub)  # Needs to be full-scanned first
                if sub.indexed:
                    # Scanned with intention of reporting now
                    self.scan_submissions(sub)

    def update_subs(self):
        """Updates the list of subreddits"""
        self.subreddits.clear()
        with self.conn.cursor() as cur:
            cur.execute("SELECT * FROM subreddits")
            for sub, indexed in cur.fetchall():
                self.subreddits.append(SubData(sub, indexed))
        self.conn.commit()

        logger.debug("Updated list of subreddits")

    def handle_submission(self, submission, *, report):
        """Handles the submissions, deciding whether to index or report them"""
        if submission.is_self or submission.id in self.ignored_id_cache:
            return

        cur = self.conn.cursor()

        cur.execute(
            "SELECT COUNT(*) FROM indexed_submissions WHERE id=%s",
            (submission.id,)
        )
        if cur.fetchone()[-1] >= 1:
            self.conn.commit()  # Avoids "idle in transaction"
            return

        img_url = submission.url.replace("m.imgur.com", "i.imgur.com")

        try:
            if (media := fetch_media(img_url)) is False:
                return

            media_data = MediaData(
                diff_hash(media),
                str(submission.id),
                submission.subreddit.display_name)

            def get_matches():
                # We're using a named cursor here because queries to
                # the media_storage table get massive in size, and the
                # memory allocated by a client-side cursor becomes
                # proportionally high
                media_cursor = self.conn.cursor("fetch_media")
                media_cursor.execute(
                    "SELECT * FROM media_storage WHERE subname=%s",
                    (media_data.subname,)
                )

                for item in media_cursor:
                    post = MediaData(*item)
                    compared = int(((64 - bin(media_data.hash ^ int(post.hash)
                                              ).count("1")) * 100.0) / 64.0)
                    if compared > THRESHOLD:
                        yield Match(*post, compared)
                media_cursor.close()
                self.conn.commit()

            if report:
                if (matches := [*get_matches()]):
                    matches = sorted(
                        matches,
                        key=operator.attrgetter("similarity"),
                        reverse=True
                    )[:10]
                    self.do_report(submission, matches)

            self.insert_cursor.execute(
                "INSERT INTO media_storage VALUES(%s, %s, %s)",
                (*media_data,)
            )

        except Exception as e:
            logger.warn(f"Error processing submission {submission.id}: {e}")
            self.ignored_id_cache.add(submission.id)
            self.conn.commit()
            return

        self.insert_cursor.execute(
            """INSERT INTO indexed_submissions (id) VALUES (%s)""",
            (submission.id,)
        )
        cur.close()
        self.conn.commit()

    def do_report(self, submission, matches):
        """Executes reporting from a processed submission"""
        active = 0
        rows = ""

        for match in matches:

            post = self.reddit.submission(id=match.id)
            cur_score = int(post.score)

            if post.removed:
                cur_status = "Removed"
            elif getattr(post.author, "name", "[deleted]") == "[deleted]":
                cur_status = "Deleted"
            else:
                cur_status = "Active"
                active += 1

            created_at = datetime.fromtimestamp(post.created_utc)
            rows += ROW_TEMPLATE.format(
                getattr(post.author, "name", "[deleted]"),
                created_at.strftime("%a, %b %d, %Y at %H:%M:%S"),
                post.url,
                post.title,
                post.id,
                cur_score,
                cur_status,
                match.similarity
            )

        submission.report(f"Possible repost ( {len(matches)} matches |"
                          f" {len(matches) - active} removed/deleted )")
        reply = submission.reply(INFO_TEMPLATE.format(rows))

        with suppress(Exception):
            praw.models.reddit.comment.CommentModeration(
                reply).remove(spam=False)

        logger.info(f"✅ https://redd.it/{submission.id} | "
                    f"{('r/' + str(submission.subreddit)).center(24)} | "
                    f"{len(matches)} matches")

    def scan_submissions(self, sub):
        """Scans /new/ for an already indexed subreddit"""
        for submission in self.reddit.subreddit(sub.subname).new():
            self.handle_submission(submission, report=True)

        logger.debug(f"Scanned r/{sub.subname} for new posts")

    def scan_new_sub(self, sub):
        """Performs initial indexing for a new subreddit"""
        for time in ("all", "year", "month"):
            for submission in self.reddit.subreddit(sub.subname).top(
                time_filter=time
            ):

                logger.debug(
                    f"Indexing {submission.fullname} from r/{sub.subname}"
                )
                self.handle_submission(submission, report=False)

        with self.conn.cursor() as cur:
            cur.execute(
                "UPDATE subreddits SET indexed=TRUE WHERE name=%s",
                (sub.subname,)
            )

        self.conn.commit()
        logger.info(f"✅ Fully indexed r/{sub.subname}")
        self.update_subs()

    def handle_dms(self):
        """Checks direct messages for new subreddits and removals"""
        for msg in self.reddit.inbox.unread(mark_read=True):

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

        self.conn.commit()
        logger.info(f"✅ Accepted mod invite to r/{msg.subreddit}")

    def handle_mod_removal(self, msg):
        """Handles removal from a subreddit"""
        self.insert_cursor.execute(
            "DELETE FROM subreddits WHERE name=%s",
            (str(msg.subreddit),)
        )
        self.update_subs()

        self.conn.commit()
        logger.info(f"✅ Handled removal from r/{msg.subreddit}")
