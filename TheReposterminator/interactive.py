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
from __future__ import annotations

import logging
import operator
from datetime import datetime
from typing import TYPE_CHECKING, cast

from .common import get_matches
from .types import Match, MediaData, SubData

if TYPE_CHECKING:
    from praw.models.reddit.message import Message
    from praw.models.reddit.submission import Submission

    from TheReposterminator import BotClient

logger = logging.getLogger(__name__)


class Interactive:
    """
    Interactive module of TheReposterminator

    Receives u/ mentions, and acts accordingly. Performs many of the same
    tasks as the `Sentry` module, but with some functionality stripped.
    """

    def __init__(self, bot: BotClient):
        self.bot = bot

    def receive_mention(self, message: Message):
        """
        Receives a mention and handles it accordingly

        Un-indexed subreddits are ignored, as are messages that contain
        anything other than the bot's mention in their body.

        :param message: The message that is being received
        :type message: ``Message``
        """
        if not (sub := self.bot.get_sub(str(message.subreddit))):
            return
            # For the time being, ignore any subs that aren't indexed
            # Hopefully to prevent annoyance and stuff

        if not (  # TODO: Remove this? So that any bot mentions summon
            message.body.split("u/")[-1].lower()
            == self.bot.config["reddit"]["username"].lower()
        ):
            return

        self.handle_requested_submission(  # TODO: Remove kwarg necessity?
            message=message,  # Alternative TODO: argparse the mention
            sub=sub,
            submission=message.submission,
        )

    def handle_requested_submission(
        self, *, message: Message, sub: SubData, submission: Submission
    ):
        """
        Handles a submission in which the bot is mentioned

        Behaves similarly as if the post was encountered via automatic
        scanning, replying to the comment with a table of reposts.

        :param message: The message to respond to
        :type message: ``Message``

        :param sub: The subreddit in which the submission was posted
        :type sub: ``SubData``

        :param submission: The submission to process
        :type submission: ``Submission``
        """
        if submission.is_self:
            return

        # Depends upon the fact that any submission which is being requested has
        # already been scanned and indexed
        cur = self.bot.db.cursor()
        cur.execute(
            "SELECT * FROM media_storage WHERE submission_id=%s", (submission.id,)
        )
        if not (data := cur.fetchone()):
            return
            # TODO: Make this more informative on front end
        cur.close()
        self.bot.db.commit()

        parent_data = MediaData(*data)
        if matches := [
            *get_matches(self.bot, parent_data, submission, mode="mentioned")
        ]:
            matches = sorted(  # Sorts by confidence
                matches, key=operator.attrgetter("similarity"), reverse=True
            )[:25]
            self.do_response(message=message, submission=submission, matches=matches)

        else:
            self.bot.reply(
                "Couldn't find any matches - this post could be unique", target=message
            )
            logger.info(
                f"✅ https://redd.it/{submission.id} | "
                f"{('r/' + str(submission.subreddit)).center(24)} | "
                f"Unique - Requested by user"
            )

    def do_response(
        self, *, message: Message, submission: Submission, matches: list[Match]
    ):
        """
        Responds to a mentioning comment with repost details

        :param message: The message to respond to
        :type message: ``Message``

        :param submission: The submission which has been processed
        :type submission: ``Submission``

        :param matches: A list of processed matches
        :type matches: ``list[Match]``
        """
        rows = ""
        matches_posts: list[tuple[Match, Submission]] = []

        # Request the posts in bulk
        for post in self.bot.reddit.info(map(lambda m: f"t3_{m.id}", matches)):
            if TYPE_CHECKING:
                post = cast(Submission, post)
            match = next(filter(lambda m: m.id == post.id, matches))
            matches_posts.append((match, post))

        for match, post in matches_posts:
            if post.removed:
                cur_status = "Removed"
            elif getattr(post.author, "name", "[deleted]") == "[deleted]":
                cur_status = "Deleted"
            else:
                cur_status = "Active"

            created_at = datetime.fromtimestamp(post.created_utc)
            row = self.bot.config["templates"]["row_mentioned"].format(
                created_at.strftime("%a, %b %d, %Y at %H:%M:%S UTC"),
                f"[URL]({post.url})" if post.url else "No URL",
                post.title,
                post.id,
                cur_status,
                match.similarity,
            )

            if len(rows + row) > 2500:
                break
            rows += row

        self.bot.reply(
            self.bot.config["templates"]["info_mentioned"].format(rows), target=message
        )

        logger.info(
            f"✅ https://redd.it/{submission.id} | "
            f"{('r/' + str(submission.subreddit)).center(24)} | "
            f"{len(matches)} matches | "
            f"[Requested by user]"
        )
