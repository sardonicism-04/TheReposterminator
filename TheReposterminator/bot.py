"""
TheReposterminator Reddit bot to detect reposts
Copyright (C) 2020 sardonicism-04

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
import os
import logging
import asyncio
from io import BytesIO
from datetime import datetime
from contextlib import suppress
from collections import namedtuple

import asyncpg
import aiohttp
from PIL import UnidentifiedImageError

from .config import *
from .helpers import diff_hash, async_Image_open
from .reddit_client import RedditClient

#TODO: Clean up unnecessary type casts

# Constant that sets the confidence threshold at which submissions will be reported
THRESHOLD = 88

# Other constants
ROW_TEMPLATE = '/u/{0} | {1} | [URL]({2}) | [{3}](https://redd.it/{4}) | {5} | {6}\n'
INFO_TEMPLATE = 'User | Date | Image | Title | Karma | Status\n:---|:---|:---|:---|:---|:---|:---|:---\n{0}'
SubData = namedtuple('SubData', 'subname indexed')
MediaData = namedtuple('MediaData', 'hash id subname')

# Set up logging
logger = logging.getLogger(__name__)
formatting = "[%(asctime)s] [%(levelname)s:%(name)s] %(message)s"
logging.basicConfig(
    format=formatting,
    level=logging.INFO,
    handlers=[logging.FileHandler('rterm.log'),
              logging.StreamHandler()])


class BotClient:
    """The main Reposterminator object"""

    def __init__(self):
        self.loop = asyncio.get_running_loop()
        self.subreddits = []

    def __await__(self):
        return self.ainit().__await__()

    async def ainit(self):
        await self.setup_connections()
        await self.update_subs()
        self.auxiliary_session = aiohttp.ClientSession()
        return self

    async def setup_connections(self):
        """Establishes a Reddit and database connection"""
        try:
            self.pool = await asyncpg.create_pool(
                database=db_name,
                user=db_user,
                host=db_host,
                password=db_pass,
                timeout=5) # If your server is slow to connect to, increase this value
            self.reddit = await RedditClient(
                client_id=reddit_id,
                client_secret=reddit_secret,
                password=reddit_pass,
                user_agent=reddit_agent,
                username=reddit_name,
                loop=self.loop,
                logger=logger)
        except Exception as e:
            logger.critical(f'Connection setup failed; exiting: {e}')
            exit(1)
        else:
            logger.info('Reddit and database connections successfully established')

    async def run(self):
        """Runs the bot
        This function is entirely blocking, so any calls to other functions must
        be made prior to calling this."""
        while True:
            tasks = []
            if self.subreddits:
                for sub in self.subreddits:
                    tasks.append(self.handle_dms())
                    if not sub.indexed:
                        tasks.append(self.scan_new_sub(sub.subname)) # Needs to be full-scanned first
                    if sub.indexed:
                        tasks.append(self.scan_submissions(sub)) # Scanned with intention of reporting now
                await asyncio.gather(*tasks, return_exceptions=True)
            else:
                logger.error('Found no subreddits, exiting')
                exit(1)

    async def update_subs(self):
        """Updates the list of subreddits"""
        self.subreddits.clear()
        for sub, indexed in await self.pool.fetch('SELECT * FROM subreddits'):
            self.subreddits.append(SubData(sub, indexed))
        logger.info('Updated list of subreddits')

    async def check_submission_indexed(self, submission):
        if bool(await self.pool.fetch(
                "SELECT * FROM indexed_submissions WHERE id=$1",
                str(submission.id))):
            return False
            # Don't want to action if we've already indexed it
        return submission.url.replace('m.imgur.com', 'i.imgur.com').lower()

    async def fetch_media(self, img_url):
        resp = await self.auxiliary_session.request('GET', img_url)
        # We use the aux session here so as to not clog up the ratelimited reddit requestor
        try:
            return await async_Image_open(BytesIO(await resp.read()))
        except UnidentifiedImageError:
            logger.debug('Encountered unidentified image, ignoring')
            return False

    async def handle_submission(self, submission, should_report):
        """Handles the submissions, deciding whether to index or report them"""
        if submission.is_self is True or (img_url := await self.check_submission_indexed(
                submission=submission)) is False:
            return
        processed = False
        try:
            if (media := await self.fetch_media(img_url)) is False:
                return
            media_data = MediaData(
                str(await diff_hash(media)),
                str(submission.id),
                submission.subreddit_name)
            same_sub = await self.pool.fetch(
                "SELECT * FROM media_storage WHERE subname=$1",
                media_data.subname)
            def get_matches():
                for item in same_sub:
                    post = MediaData(*item)
                    compared = int(((64 - bin(int(media_data.hash) ^ int(post.hash)).count('1'))*100.0)/64.0)
                    if compared > THRESHOLD:
                        yield post

            if should_report:
                if (matches := [*get_matches()]) and len(matches) <= 10:
                    logger.info(f'Found repost {media_data.id}; handling... (matches: {len(matches)})')
                    logging.debug(f'Found matches {matches}')
                    await self.do_report(submission, matches)

            await self.pool.execute(
                "INSERT INTO media_storage VALUES($1, $2, $3)",
                *media_data)
            processed = True

        except Exception as e:
            logger.error(f'Error processing submission {submission.id}: {e}')

        is_deleted = submission.author == '[deleted]'
        submission_data = (
            str(submission.id),
            str(submission.subreddit_name),
            float(submission.created),
            str(submission.author),
            str(submission.title),
            str(submission.url),
            int(submission.score),
            is_deleted,
            processed)
        with suppress(asyncpg.UniqueViolationError):
            await self.pool.execute(
                'INSERT INTO indexed_submissions (id, subname, timestamp, author,'
                'title, url, score, deleted, processed) '
                'VALUES($1, $2, $3, $4, $5, $6, $7, $8, $9)', *submission_data)

    async def do_report(self, submission, matches):
        """Executes reporting based on the matches retrieved from a processed submission"""
        active = 0
        rows = ''
        for match in matches:
            match_original = (await self.pool.fetch("SELECT * FROM indexed_submissions WHERE id=$1", match.id))[-1]
            original_post = await self.reddit.get_arbitrary_submission(
                thing_id = match_original['id'])
            cur_score = int(original_post.score)
            if original_post.removed:
                cur_status = 'Removed'
            elif original_post.author == '[deleted]':
                cur_status = 'Deleted'
            else:
                cur_status = 'Active'
                active += 1
            created_at = datetime.fromtimestamp(match_original['timestamp'])
            rows += ROW_TEMPLATE.format(
                match_original['author'],
                created_at.strftime("%a, %b %d, %Y at %H:%M:%S"),
                match_original['url'],
                match_original['title'],
                match_original['id'],
                cur_score,
                cur_status)
        await self.reddit.report(
            reason=f'Possible repost ( {len(matches)} matches | {len(matches) - active} removed/deleted )',
            submission_fullname=submission.fullname)
        with suppress(Exception):
            await self.reddit.comment_and_remove(
                content=INFO_TEMPLATE.format(rows),
                submission_fullname=submission.fullname)
        logger.info(f'Finished handling and reporting repost https://redd.it/{submission.id}')

    async def scan_submissions(self, sub):
        """Scans /new/ for an already indexed subreddit"""
        async for submission in self.reddit.iterate_subreddit(
                subreddit=sub.subname,
                sort='new'):
            await self.handle_submission(submission, True)
        logger.debug(f'Finished scanning r/{sub.subname} for new posts')

    async def scan_new_sub(self, sub):
        """Performs initial indexing for a new subreddit"""
        logging.info(f'Performing full scan for r/{sub}')
        for _time in ('all', 'year', 'month'):
            async for submission in self.reddit.iterate_subreddit(
                    subreddit=sub,
                    sort='top', time_filter=_time):
                logger.debug(f'Indexing {submission.fullname} from r/{sub.subname} top {_time}')
                await self.handle_submission(submission, False)
        await self.pool.execute("UPDATE subreddits SET indexed=TRUE WHERE name=$1", sub)
        await self.update_subs()

    async def handle_dms(self):
        """Checks direct messages for new subreddits and removals"""
        to_mark = []
        with suppress(Exception):
            unreads = await(await self.reddit.request('GET', self.reddit.rbase / 'message/unread')).json()
            for item in unreads['data']['children']:
                data = item['data']
                if data['body'].startswith(('**gadzooks!', 'gadzooks!')) or data['subject'].startswith('invitation to moderate'):
                    await self.reddit.request('POST', self.reddit.rbase / f"r/{data['subreddit']}/api/accept_moderator_invite")
                    await self.handle_new_sub(data['subreddit'])
                elif 'You have been removed as a moderator from' in data['body']:
                    await self.handle_mod_removal(data['subreddit'])
                await self.reddit.request('POST', self.reddit.rbase / 'api/read_message', data={'id': data['name']})

    async def handle_new_sub(self, subreddit):
        """Accepts an invite to a new subreddit and adds it to the database"""
        await self.pool.execute(
            "INSERT INTO SUBREDDITS VALUES($1, FALSE) ON CONFLICT DO NOTHING",
            subreddit)
        await self.update_subs()
        await self.scan_new_sub(subreddit)
        logger.info(f"Accepted mod invite to r/{subreddit}")

    async def handle_mod_removal(self, subreddit):
        """Handles removal from a subreddit, clearing the sub's entry in the database"""
        await self.pool.execute(
            "DELETE FROM SUBREDDITS WHERE name=$1",
            subreddit)
        await self.update_subs()
        logger.info(f"Handled removal from r/{subreddit}")

async def main():
    client = await BotClient()
    await client.run()

