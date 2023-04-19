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

from typing import TYPE_CHECKING, Literal

from image_hash import compare_hashes

from .types import Match, MediaData

if TYPE_CHECKING:
    from collections.abc import Generator

    from praw.models.reddit.submission import Submission

    from TheReposterminator import BotClient


def get_matches(
    bot: BotClient,
    parent: MediaData,
    submission: Submission,
    *,
    mode: Literal["sentry", "mentioned"],
) -> Generator[Match, None, None]:
    """
    Returns a generator of posts that match the provided parent submission

    Requests all stored media data from the relevant subreddit for which the post
    ID does not match the parent post ID, and yields all posts for which the hash
    comparison value is >= the configured minimum similarity.

    :param bot: The bot client to perform method calls to
    :type bot: ``BotClient``

    :param parent: The media data for the parent submission
    :type parent: ``MediaData``

    :param submission: The Reddit submission associated with the parent data
    :type submission: ``Submission``

    :param mode: The mode to use for determining the minimum threshold
    :type mode: ``Literal["sentry", "mentioned"]``

    :return: A generator which yields all matches that surpass the minimum threshold
    :rtype: ``Generator[Match, None, None]``
    """
    match mode:
        case "sentry":
            cursor_name = "fetch_media"
            threshold_key = "sentry_threshold"
        case "mentioned":
            cursor_name = "fetch_media_requested"
            threshold_key = "mentioned_threshold"

    # Use a named cursor because queries to the media_storage table are very
    # large in terms of data quantity, and will cause high amounts of memory to
    # be allocated if using a client-side cursor
    cursor = bot.db.cursor(cursor_name)
    cursor.execute(
        """
        SELECT * FROM
            media_storage
        WHERE
            subname=%s AND
            NOT submission_id=%s
        """,
        (parent.subname, submission.id),
    )

    for item in cursor:
        post = MediaData(*item)
        compared = compare_hashes(parent.hash, post.hash)
        if compared >= bot.subreddit_configs[parent.subname][threshold_key]:
            yield Match(*post, compared)

    cursor.close()
    bot.db.commit()
