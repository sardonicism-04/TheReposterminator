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
import requests
from PIL import Image, UnidentifiedImageError

from .differencer import diff_hash

# Define namedtuples
MediaData = namedtuple("MediaData", "hash id subname")
Match = namedtuple("Match", "hash id subname similarity")

logger = logging.getLogger(__name__)


class Sentry:
    """
    Sentry module of TheReposterminator.

    Automatically scans /new/ of subreddits and leaves reports + comments.
    """

    def __init__(self, bot):
        self.bot = bot

        # Store problematic IDs in a cache to prevent recurring errors
        self.ignored_id_cache = set()

    @staticmethod
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

    def handle_submission(self, submission, *, report):
        """Handles the submissions, deciding whether to index or report them"""
        if submission.is_self or submission.id in self.ignored_id_cache:
            return

        cur = self.bot.db.cursor()

        cur.execute(
            "SELECT COUNT(*) FROM indexed_submissions WHERE id=%s",
            (submission.id,)
        )
        if cur.fetchone()[-1] >= 1:
            self.bot.db.commit()  # Avoids "idle in transaction"
            return

        img_url = submission.url.replace("m.imgur.com", "i.imgur.com")

        try:
            if (media := self.fetch_media(img_url)) is False:
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
                media_cursor = self.bot.db.cursor("fetch_media")
                media_cursor.execute(
                    "SELECT * FROM media_storage WHERE subname=%s",
                    (media_data.subname,)
                )

                for item in media_cursor:
                    post = MediaData(*item)
                    compared = int(((64 - bin(media_data.hash ^ int(post.hash)
                                              ).count("1")) * 100.0) / 64.0)
                    if compared > self.bot.config["default_threshold"]:
                        yield Match(*post, compared)
                media_cursor.close()
                self.bot.db.commit()

            if report:
                if (matches := [*get_matches()]):
                    matches = sorted(
                        matches,
                        key=operator.attrgetter("similarity"),
                        reverse=True
                    )[:10]
                    self.do_report(submission, matches)

            self.bot.insert_cursor.execute(
                "INSERT INTO media_storage VALUES(%s, %s, %s)",
                (*media_data,)
            )

        except Exception as e:
            logger.warn(f"Error processing submission {submission.id}: {e}")
            self.ignored_id_cache.add(submission.id)
            self.bot.db.commit()
            return

        self.bot.insert_cursor.execute(
            """INSERT INTO indexed_submissions (id) VALUES (%s)""",
            (submission.id,)
        )
        cur.close()
        self.bot.db.commit()

    def do_report(self, submission, matches):
        """Executes reporting from a processed submission"""
        active = 0
        rows = ""

        for match in matches:

            post = self.bot.reddit.submission(id=match.id)
            cur_score = int(post.score)

            if post.removed:
                cur_status = "Removed"
            elif getattr(post.author, "name", "[deleted]") == "[deleted]":
                cur_status = "Deleted"
            else:
                cur_status = "Active"
                active += 1

            created_at = datetime.fromtimestamp(post.created_utc)
            rows += self.bot.config["templates"]["row"].format(
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
        reply = submission.reply(
            self.bot.config["templates"]["info"].format(rows))

        with suppress(Exception):
            praw.models.reddit.comment.CommentModeration(
                reply).remove(spam=False)

        logger.info(f"✅ https://redd.it/{submission.id} | "
                    f"{('r/' + str(submission.subreddit)).center(24)} | "
                    f"{len(matches)} matches")

    def scan_submissions(self, sub):
        """Scans /new/ for an already indexed subreddit"""
        for submission in self.bot.reddit.subreddit(sub.subname).new():
            self.handle_submission(submission, report=True)

        logger.debug(f"Scanned r/{sub.subname} for new posts")

    def scan_new_sub(self, sub):
        """Performs initial indexing for a new subreddit"""
        for time in ("all", "year", "month"):
            for submission in self.bot.reddit.subreddit(sub.subname).top(
                time_filter=time
            ):
                logger.debug(
                    f"Indexing {submission.fullname} from r/{sub.subname}"
                )
                self.handle_submission(submission, report=False)

        with self.bot.db.cursor() as cur:
            cur.execute(
                "UPDATE subreddits SET indexed=TRUE WHERE name=%s",
                (sub.subname,)
            )

        self.bot.db.commit()
        logger.info(f"✅ Fully indexed r/{sub.subname}")
        self.bot.update_subs()