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

from collections.abc import Callable
from typing import NamedTuple, TypedDict

from praw.models.reddit.message import Message


class SubredditConfig(TypedDict):
    respond_to_mentioned: bool
    mentioned_threshold: int
    sentry_threshold: int
    remove_sentry_comments: bool
    max_post_age: int

    # autoremoval
    autoremove: bool
    autoremove_threshold: int
    autoremove_reply: bool


class MediaData(NamedTuple):
    hash: str
    id: str
    subname: str


class Match(NamedTuple):
    hash: str
    id: str
    subname: str
    similarity: float


class SubData(NamedTuple):
    subname: str
    indexed: bool


Command = Callable[[str, Message], None]
