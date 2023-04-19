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
from typing import TYPE_CHECKING, cast

import toml
from praw import exceptions as praw_exceptions
from prawcore import exceptions

from .types import Command, SubredditConfig

if TYPE_CHECKING:
    from praw.models.reddit.message import Message

    from TheReposterminator import BotClient

logger = logging.getLogger(__name__)


class MessageHandler:
    """
    Handles direct messages to the bot

    Username mentions, subreddit moderation invites/removals, and commands are
    all received and delegated appropriately here.
    """

    def __init__(self, bot: BotClient):
        self.bot = bot

        self.commands: dict[str, Command] = {
            "update": self.command_update,
            "defaults": self.command_defaults,
        }

    def handle(self):
        """
        Iterates over all unread messages and dispatches actions accordingly

        | Message Type                 | Action                                     |
        | :--------------------------- | :----------------------------------------- |
        | Username Mention             | Delegates to `Interactive.receive_mention` |
        | Subreddit Moderation Invite  | Delegates to `self.accept_invite`          |
        | Subreddit Moderation Removal | Delegates to `self.handle_mod_removal`     |
        | Command                      | Delegates to `self.run_command`            |
        | Anything else                | Ignored                                    |

        All messages are then marked as read, regardless of action.
        """
        for message in self.bot.reddit.inbox.unread(mark_read=True):
            if TYPE_CHECKING:
                message = cast(Message, message)

            if "username mention" in message.subject.lower():
                if self.bot.subreddit_configs.get(
                    str(message.subreddit), {}
                ).get("respond_to_mentions"):
                    self.bot.interactive.receive_mention(message)

            if getattr(message, "subreddit", None):
                if (  # Confirm that the message is from a subreddit
                    message.body.startswith(("**gadzooks!", "gadzooks!"))
                    or "invitation to moderate" in message.subject
                ):
                    self.accept_invite(message)
                elif (
                    "You have been removed as a moderator from " in message.body
                ):
                    self.handle_mod_removal(message)

            else:
                if command := self.commands.get(message.body.lower()):
                    subname = message.subject.split("r/")[-1]
                    if self.bot.get_sub(subname):
                        self.run_command(command, subname, message)
                    else:
                        message.reply(
                            "❌ I don't currently moderate this subreddit!"
                        )

            message.mark_read()

    # Mod invite handlers

    def accept_invite(self, message: Message):
        """
        Accepts an invite to a new subreddit and adds it to the database

        First accepts the invitation to the subreddit, and then inserts a
        fresh entry into the `subreddits` table.

        After accepting and adding to the database, the subreddit's config is
        processed. If there is already content in the subreddit's
        `thereposterminator_config` wiki page, then nothing is done. If not the
        bot is forbidden from accessing the wiki, the function returns. If possible,
        a new config wiki page is created automatically.

        Regardless, `BotClient.get_config` is then called on the subreddit,
        loading the subreddit's config.

        :param message: The invitation message
        :type message: ``Message``
        """
        try:
            message.subreddit.mod.accept_invite()
        except praw_exceptions.RedditAPIException:
            logger.warning(
                f"⚠️ Failed to accept invite to r/{message.subreddit}, ignoring"
            )
            return

        self.bot.insert_cursor.execute(
            """
            INSERT INTO subreddits
            VALUES(
                %s,
                FALSE
            ) ON CONFLICT DO NOTHING""",
            (str(message.subreddit),),
        )
        self.bot.update_subs()

        self.bot.db.commit()
        logger.info(f"✅ Accepted mod invite to r/{message.subreddit}")

        try:
            message.subreddit.wiki["thereposterminator_config"].content_md
            # Avoid overwriting an existing wiki

        except exceptions.NotFound:
            message.subreddit.wiki.create(
                "thereposterminator_config",
                self.bot.default_sub_config,
                reason="Create TheReposterminator config",
            )

        except exceptions.Forbidden:
            return  # Not allowed to access the wiki

        finally:
            self.bot.get_config(str(message.subreddit))

    def handle_mod_removal(self, message: Message):
        """
        Handles removal from a subreddit

        Deletes the subreddit's associated entry in the `subreddits` table and
        then calls `BotClient.update_subs`. Note that associated submission data
        is **not** deleted, as it may be needed again if the bot is re-added.

        :param message: The subreddit removal message
        :type message: ``Message``
        """
        self.bot.insert_cursor.execute(
            "DELETE FROM subreddits WHERE name=%s", (str(message.subreddit),)
        )
        self.bot.update_subs()
        self.bot.db.commit()
        logger.info(f"✅ Handled removal from r/{message.subreddit}")

    # DM commands

    def run_command(self, command: Command, subname: str, message: Message):
        """
        Runs a command callback

        If the user is not a moderator of the subreddit in the command's subject
        line, then they will receive an error message instead of the command
        being executed.

        :param command: The command to execute
        :type command: ``Command``

        :param subname: The subreddit to execute the command for
        :type subname: ``str``

        :param message: The message from which the command was executed
        :type message: ``Message``
        """
        # Check that the user actually mods the subreddit
        if subname not in [*map(str, message.author.moderated())]:
            message.reply("❌ You don't mod this subreddit!")
            return

        command(subname, message)

    def command_update(self, subname: str, message: Message):
        """
        Attempts to update the cached config for a subreddit

        :param subname: The subreddit to update
        :type subname: ``str``

        :param message: THe message from which the command was executed
        :type message: ``Message``
        """
        try:
            self.bot.get_config(subname, ignore_errors=False)
            message.reply("👍 Successfully updated your subreddit's config!")
            logger.info(f"✅ Config updated for r/{subname}")

        except exceptions.Forbidden:
            message.reply(
                "❌ Didn't have the permissions to access the wiki, "
                "no changes have been made"
            )

        except exceptions.NotFound:
            message.reply(
                "❌ No wiki page currently exists, no changes have been made"
            )

        except ValueError as error:
            message.reply(
                "❌ `{0}` was set to lower than its minimum allowed value of {1}, "
                "using its default value".format(
                    str(error),
                    self.bot.config["limits"]["minimum_threshold_allowed"],
                )
            )

        except Exception as e:
            message.reply("❌ Something went wrong, it'll be investigated")
            logger.error(f"Error in command update: {e}")

    def command_defaults(self, subname: str, message: Message):
        """
        Attempts to reset a subreddit's config to default

        :param subname: The subreddit to reset
        :type subname: ``str``

        :param message: The message from which the command was executed
        :type message: ``Message``
        """
        try:
            self.bot.reddit.subreddit(subname).wiki.create(
                "thereposterminator_config",
                self.bot.default_sub_config,
                reason="Create/reset TheReposterminator config",
            )
            self.bot.subreddit_configs[subname] = cast(
                SubredditConfig, toml.loads(self.bot.default_sub_config)
            )
            message.reply(
                "👍 Successfully created/reset your subreddit's config!"
            )
            logger.info(f"✅ Config successfully created/reset for r/{subname}")

        except exceptions.Forbidden:
            message.reply(
                "❌ Didn't have the permissions to access the wiki, "
                "no changes have been made"
            )

        except Exception as e:
            message.reply("❌ Something went wrong, it'll be investigated")
            logger.error(f"Error in command defaults: {e}")
