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


class Interactive:
    """
    Interactive module of TheReposterminator.

    Receives u/ mentions, and will act accordingly.
    """

    def __init__(self, bot):
        self.bot = bot

    # TODO: All of this
    #       - (TODO) Check values from wiki config before taking action
    #       - When mentioned, create a table if possible, otherwise mention
    #         that there are no scanned posts to check from
