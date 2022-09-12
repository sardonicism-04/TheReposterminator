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
import traceback
from typing import TYPE_CHECKING, cast

import praw
import psycopg2
import toml
from prawcore import exceptions

from .interactive import Interactive
from .messages import MessageHandler
from .sentry import Sentry
from .types import SubData, SubredditConfig

if TYPE_CHECKING:
    from praw.models import Comment
    from praw.models.reddit.mixins import ReplyableMixin


# Set up logging
logger = logging.getLogger(__name__)


class BotClient:
    """
    The main Reposterminator object

    This class acts as the controller for the entire Reposterminator
    functionality. It leverages other modules to manage all facets of the bot.
    """

    def __init__(self):
        self.sentry = Sentry(self)
        self.interactive = Interactive(self)
        self.message_handler = MessageHandler(self)

        self.subreddits: list[SubData] = []
        self.subreddit_configs: dict[str, SubredditConfig] = {}

        self.config = self.load_config()
        self.default_sub_config = open("subreddit_config.toml", "r").read()
        self.setup_connections()
        self.update_subs()

    def load_config(self, fp="config.toml"):
        """
        Loads the bot's config from a TOML file

        :param fp: The file path to load, defaults to `config.toml`
        :type fp: ``str``

        :return: The loaded TOML data
        :rtype: ``dict``
        """
        return toml.load(fp)

    def setup_connections(self):
        """
        Establishes a Reddit and database connection

        Attempts to connect to first the database, then to Reddit. The database
        connection will timeout after 5 seconds. Also creates a server-side
        database cursor for data insertion.

        If a timeout, or any other error is encountered, the exception will be
        logged, and the program will exit immediately. Otherwise, the
        connections have been successfully established.
        """
        try:
            self.db: psycopg2.connection = psycopg2.connect(
                **self.config["database"], connect_timeout=5
            )
            self.insert_cursor = self.db.cursor()

            self.reddit = praw.Reddit(**self.config["reddit"])

        except Exception as e:
            logger.critical(f"Connection setup failed; exiting: {e}")
            exit(1)

        else:
            logger.info("✅ Reddit and database connections successfully established")

    def run(self):
        """
        Runs the bot in an infinite, blocking loop

        Begins by calling `self.get_all_configs()`, which is rather slow.
        After the configs have been downloaded, an infinite loop is started,
        which does the following:
        - Attempts to handle messages
        - For each subreddit in `self.subreddits`:
            - Handles messages
            - If the sub isn't indexed, indexes the subreddit for the first time
            - Performs a standard scan of the subreddit

        If any of these steps fail and the error is a:
        - Reddit server error: The program terminates
        - SQL error: The program terminates
        - Another error: The exception is suppressed and logged
        """

        self.get_all_configs()  # This operation is very slow
        while True:
            try:
                if not self.subreddits:
                    self.message_handler.handle()  # In case there are no subs

                for sub in self.subreddits:
                    self.message_handler.handle()

                    if not sub.indexed:
                        # Needs to be full-scanned first
                        self.sentry.scan_new_sub(sub)
                    if sub.indexed:
                        # Scanned with intention of reporting now
                        self.sentry.scan_submissions(sub)

            except exceptions.ServerError as e:
                logger.critical(
                    f"Encountered server error, terminating loop"
                    f" [code {e.response.status_code}]: {e}"
                )
                break

            except psycopg2.Error as e:
                logger.critical(f"Encountered SQL error, terminating loop [{e}]")
                break

            except Exception as e:
                exc_info = (type(e), e, e.__traceback__)
                formatted = "".join(traceback.format_exception(*exc_info)).rstrip()
                logger.error(f"Suppressed unhandled exception\n{formatted}")

        logger.info("Main loop terminated")

    def update_subs(self):
        """
        Updates the list of subreddits

        Populates `self.subreddits` with `SubData` objects which are generated
        via selecting data from the database.
        """

        self.subreddits.clear()

        with self.db.cursor() as cur:
            cur.execute("SELECT * FROM subreddits")
            for sub, indexed in cur.fetchall():
                self.subreddits.append(SubData(sub, indexed))
        self.db.commit()

        logger.debug("Updated list of subreddits")

    def get_all_configs(self):
        """
        Downloads and processes all subreddit configs

        Makes a request to each indexed subreddit's wiki page under the
        appropriate page name, and attempts to parse and load its config.
        Uses the default config if no/an invalid wiki page is found.

        This operation is rather slow, and takes longer as more subreddits are
        indexed.
        """
        self.subreddit_configs.clear()

        for subname, _ in self.subreddits:
            self.get_config(subname)

        logger.info("Loaded all initial configs")

    def get_config(self, subname: str, ignore_errors=True):
        """
        Downloads a subreddit config, and stores it in `self.subreddit_configs`

        Makes a request to the specified subreddit's wiki, specifically the
        `thereposterminator_config` page, and attempts to load a config from
        the TOML on that page. If errors in key names are encountered, the keys
        are replaced with their default values. Finally, the data is stored in
        in `self.subreddit_configs`.

        If an error of any sort is encountered, the default config is loaded
        in place of a custom one for the specified subreddit.

        :param subname: The name of the subreddit to load a config for
        :type subname: ``str``

        :param ignore_errors: Whether or not to ignore errors, defaults to `True`
        :type ignore_errors: ``bool``
        """
        try:
            config_wiki = self.reddit.subreddit(subname).wiki[
                "thereposterminator_config"
            ]

            sub_config = cast(SubredditConfig, toml.loads(config_wiki.content_md))
            template_config = cast(SubredditConfig, toml.loads(self.default_sub_config))

            # Update the value of the sub config with any newly added keys,
            # useful if a sub has an outdated config
            for key, value in template_config.items():
                if sub_config.get(key) is None:
                    sub_config.update({key: value})  # type: ignore

            for key, value in map(
                lambda k: (k, sub_config[k]),
                ["mentioned_threshold", "sentry_threshold"],
            ):
                if value < self.config["limits"]["minimum_threshold_allowed"]:

                    if ignore_errors:
                        sub_config[key] = template_config[key]
                    else:
                        raise ValueError(key)

        except Exception as e:
            logger.debug(f"Failed to load config for r/{subname}, loading default: {e}")
            sub_config = cast(SubredditConfig, toml.loads(self.default_sub_config))

        logger.debug(f"Loaded config for r/{subname}: {sub_config}")
        self.subreddit_configs[subname] = sub_config

    def get_sub(self, subname: str) -> SubData | None:
        """
        Caselessly gets subreddit data by name

        Attempts to find a `SubData` item in `self.subreddits` for which the
        subreddit name matches the `subname`. Returns `None` if no match is
        found.

        :param subname: The subreddit to search for (case-insensitive)
        :type subname: ``str``

        :return: The subreddit data if found, `None` if not found
        :rtype: ``SubData | None``
        """
        try:
            return next(
                filter(
                    lambda sub: sub and sub.subname.lower() == subname.lower(),
                    self.subreddits,
                )
            )
        except StopIteration:
            return None

    def reply(self, content: str, *, target: ReplyableMixin) -> Comment | None:
        """
        Replies with the bot notice appended to the content

        :param content: The original content to reply with
        :type content: ``str``

        :param target: The target to reply to
        :type target: ``ReplyableMixin``

        :return: The comment if it was made, `None` if it was not
        :type: ``Comment | None``
        """
        content += self.config["templates"]["bot_notice"]
        return target.reply(content)
