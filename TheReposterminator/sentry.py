"""
TheReposterminator Reddit bot to detect reposts
Copyright (C) 2022 sardonicism-04

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
from __future__ import annotations

import logging
import math
import operator
from contextlib import suppress
from datetime import datetime
from typing import TYPE_CHECKING, Optional

import requests
from image_hash import generate_hash
from praw.models.reddit.comment import CommentModeration
from praw.models.reddit.submission import SubmissionModeration
from prawcore import exceptions

from .common import get_matches
from .types import Match, MediaData, SubData

if TYPE_CHECKING:
    from praw.models.reddit.submission import Submission
    from praw.models.reddit.subreddit import Subreddit

    from TheReposterminator import BotClient


logger = logging.getLogger(__name__)


class Sentry:
    """
    Sentry module of TheReposterminator

    Automatically scans /new/ of subreddits and leaves reports + comments.
    """

    def __init__(self, bot: BotClient):
        self.bot = bot

        # Store problematic IDs in a cache to prevent recurring errors
        self.ignored_id_cache: set[str] = set()

    @staticmethod
    def fetch_media(img_url: str) -> Optional[bytes]:
        """
        Fetches submission media and returns the image bytes

        First verifies that the image extension is one of "jpg", "png", or "jpeg",
        returning `None` if not.

        Then performs a GET request to the URL. If the response code is 404,
        returns `None`. If the image size is less than ~90 million bytes, the
        image bytes are returned. Otherwise, `None` is returned.

        :param img_url: The image URL to fetch
        :type img_url: ``str``

        :return: The bytes if the response is valid, otherwise `None`
        :rtype: ``Optional[bytes]``
        """
        if not any(ext in img_url for ext in (".jpg", ".png", ".jpeg")):
            return None

        with requests.get(img_url) as resp:
            if resp.status_code == 404:
                logger.debug("Ignoring 404 on fetch_media")
                return None

            image_bytes = resp.content

            if len(image_bytes) < 89_478_485:
                return image_bytes
            else:
                logger.debug("Ignoring excessively large image")
                return None

    def handle_submission(self, submission: Submission, *, report: bool):
        """
        Handles a submission, indexing or reporting it

        First checks if the submission ID has already been indexed, and returns
        if so (submissions only need to be indexed once). Also exits if the
        submission is a self post, or if the submission ID is already being
        ignored due to errors.

        Then, fetches the media from the submission URL, and generates a hash
        of the image, returning if hash generation fails. Calls `get_matches` to
        find indexed posts for which the compared similarity is greater than the
        configured threshold.

        If matches are found, `self.do_report` is called, reporting and commenting
        under the parent submission.

        Alternatively, if `report` is `False`, the submission will also not be
        reported (used when initially indexing a subreddit).

        Regardless of whether a match is found, the submission is added
        to the `indexed_submissions` and `media_storage` tables.

        :param submission: The parent submission to handle
        :type submission: ``Submission``

        :param report: Whether the submission is allowed to be reported
        :type report: ``bool``
        """
        if submission.is_self or submission.id in self.ignored_id_cache:
            return

        # Checks that the submission has not already been indexed
        cur = self.bot.db.cursor()
        cur.execute(
            "SELECT COUNT(*) FROM indexed_submissions WHERE id=%s",
            (submission.id,),
        )
        if (cur.fetchone() or [])[-1] >= 1:
            self.bot.db.commit()  # Avoids "idle in transaction"
            return

        img_url: str = submission.url.replace("m.imgur.com", "i.imgur.com")

        try:
            if (media := self.fetch_media(img_url)) is None:
                return

            image_hash = generate_hash(media)
            if image_hash == 0:
                return  # This image couldn't be opened

            parent = MediaData(
                str(image_hash), submission.id, str(submission.subreddit)
            )
            if report and (
                matches := [
                    *get_matches(self.bot, parent, submission, mode="sentry")
                ]
            ):
                matches = sorted(
                    matches, key=operator.attrgetter("similarity"), reverse=True
                )[:25]
                self.do_report(submission, matches)

            self.bot.insert_cursor.execute(
                "INSERT INTO media_storage VALUES(%s, %s, %s)", (*parent,)
            )
            logger.debug(f"{submission.id} processed, added to media_storage")

        except Exception as e:

            logger.warn(f"Error processing submission {submission.id}: {e}")
            self.ignored_id_cache.add(submission.id)
            self.bot.db.commit()
            return

        finally:
            self.bot.insert_cursor.execute(
                "INSERT INTO indexed_submissions (id) VALUES (%s)",
                (submission.id,),
            )
            logger.debug(f"Added {submission.id} to indexed_submissions")
            cur.close()
            self.bot.db.commit()

    def do_report(self, submission: Submission, matches: list[Match]):
        """
        Reports a processed submission

        If the subreddit has configured a max age, and no posts fall within
        that range, then the function returns immediately.

        Generates a formatted table of data based on the parent submission and
        the matches found. Reports the submission and replies to it with the
        table.

        Suppressing exceptions (for in case a server-side error occurs), the
        comment is then removed based on the subreddit's configuration.

        :param submission: The parent submission to reply to and report
        :type submission: ``Submission``

        :param matches: The processed list of matching submissions
        :type matches: ``list[Match]``
        """
        sub_config = self.bot.subreddit_configs[str(submission.subreddit)]

        active = 0
        rows = ""
        matches_posts: list[tuple[Match, Submission]] = []

        # Request the posts in bulk
        for post in self.bot.reddit.info(map(lambda m: f"t3_{m.id}", matches)):
            match = next(filter(lambda m: m.id == post.id, matches))

            # check if the post is older than the max age, and skip if it is
            age_delta_days = math.ceil(
                (submission.created_utc - post.created_utc) / 86_400
            )
            if (
                sub_config["max_post_age"] > 0
                and age_delta_days > sub_config["max_post_age"]
            ):
                continue

            matches_posts.append((match, post))

        # if there are no matches within the max age, return
        if not matches_posts:
            return

        for match, post in matches_posts:
            cur_score = int(post.score)

            if post.removed:
                cur_status = "Removed"
            elif getattr(post.author, "name", "[deleted]") == "[deleted]":
                cur_status = "Deleted"
            else:
                cur_status = "Active"
                active += 1

            created_at = datetime.fromtimestamp(post.created_utc)
            row = self.bot.config["templates"]["row_auto"].format(
                getattr(post.author, "name", "[deleted]"),
                created_at.strftime("%a, %b %d, %Y at %H:%M:%S UTC"),
                f"[URL]({post.url})" if post.url else "No URL",
                post.title,
                post.id,
                cur_score,
                cur_status,
                match.similarity,
            )

            if len(rows + row) < 5000:
                rows += row

        submission.report(
            f"Possible repost ( {len(matches)} matches |"
            f" {len(matches) - active} removed/deleted )"
        )
        reply = self.bot.reply(
            self.bot.config["templates"]["info_auto"].format(rows),
            target=submission,
        )

        with suppress(Exception):
            if sub_config["remove_sentry_comments"]:
                CommentModeration(reply).remove(spam=False)

            # if auto removal enabled, call `self.auto_remove`
            if sub_config["autoremove"]:
                self.auto_remove(submission, matches_posts)

        logger.info(
            f"✅ https://redd.it/{submission.id} | "
            f"{('r/' + str(submission.subreddit)).center(24)} | "
            f"{len(matches)} matches"
        )

    def auto_remove(
        self, submission: Submission, matches: list[tuple[Match, Submission]]
    ):
        """
        Depending on configuration, handles automatic removal of submissions
        that have exceeded a minimum similarity rating.

        Submissions are auto-removed if the following conditions are met:
        - The lowest match similarity is greater than the configured minimum
        similarity

        If any condition is not met, no removal is performed.

        :param submission: The parent submission to remove
        :type submission: ``Submission``

        :param matches: The processed matches and their corresponding submissions
        :type matches: ``list[tuple[Match, Submission]]``
        """
        sub_config = self.bot.subreddit_configs[str(submission.subreddit)]

        lowest_similarity = min(matches, key=lambda pair: pair[0].similarity)
        if lowest_similarity[0].similarity < sub_config["autoremove_threshold"]:
            return

        if sub_config["autoremove_reply"] is True:
            with suppress(Exception):
                reply = self.bot.reply(
                    self.bot.config["templates"]["autoremove_message"],
                    target=submission,
                )
                CommentModeration(reply).distinguish(how="yes", sticky=True)

        try:
            SubmissionModeration(submission).remove(
                mod_note="Repost auto-removal (lowest similarity > configured minimum)",
                spam=False,
            )
            logger.info(
                f"✅ Successfully auto-removed https://redd.it/{submission.id}"
            )
        except Exception as e:
            logger.info(
                f"❌ Failed to auto-remove https://redd.it/{submission.id}: {e}"
            )

    def scan_submissions(self, sub: SubData):
        """
        Scans /new/ for an already indexed subreddit

        Iterates the posts in a subreddit's /new/ listing, and calls
        `self.handle_submission` for each, with `report` set to `True`.

        :param sub: The subreddit to scan
        :type sub: ``SubData``
        """
        try:
            subreddit: Subreddit = self.bot.reddit.subreddit(sub.subname)
            for submission in subreddit.new():  # TODO: Maximize the limit?
                self.handle_submission(submission, report=True)

            logger.debug(f"Scanned r/{sub.subname} for new posts")

        except exceptions.PrawcoreException as e:
            logger.debug(f"Failed to scan r/{sub.subname}: {e}")

    def scan_new_sub(self, sub: SubData):
        """
        Performs initial indexing for a new subreddit

        Iterates the posts in a subreddit's /top/ of all time, the last year,
        and the last month, and calls `self.handle_submission` for each, with
        `report` set to `False`.

        :param sub: The subreddit to index
        :type sub: ``SubData``
        """
        try:
            for time in ("all", "year", "month"):
                subreddit: Subreddit = self.bot.reddit.subreddit(sub.subname)
                for submission in subreddit.top(
                    time_filter=time
                ):  # TODO: Maximize the limit?
                    logger.debug(
                        f"Indexing {submission.fullname} from r/{sub.subname}"
                    )
                    self.handle_submission(submission, report=False)

        except exceptions.PrawcoreException as e:
            logger.error(f"Failed to initially index r/{sub.subname}: {e}")

        with self.bot.db.cursor() as cur:
            cur.execute(
                "UPDATE subreddits SET indexed=TRUE WHERE name=%s",
                (sub.subname,),
            )

        self.bot.db.commit()
        logger.info(f"✅ Fully indexed r/{sub.subname}")
        self.bot.update_subs()
