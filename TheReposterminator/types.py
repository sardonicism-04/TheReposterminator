from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, NamedTuple, TypedDict

if TYPE_CHECKING:
    from praw.models.reddit.message import Message


class SubredditConfig(TypedDict):
    respond_to_mentioned: bool
    mentioned_threshold: int
    sentry_threshold: int
    remove_sentry_comments: bool


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
