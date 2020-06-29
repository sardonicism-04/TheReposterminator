import os
import logging
from io import BytesIO
from datetime import datetime
from contextlib import suppress
from collections import namedtuple

import praw
import psycopg2
import requests
from PIL import Image, ImageStat, UnidentifiedImageError

from .config import *
from .differencer import diff_hash

# Constant that sets the confidence threshold at which submissions will be reported
THRESHOLD = 88

# Other constants
ROW_TEMPLATE = '/u/{0} | {1} | [URL]({2}) | [{3}](https://redd.it/{4}) | {5} | {6}\n'
INFO_TEMPLATE = '**OP:** {0}\n\n**History:**\n\nUser | Date | Image | Title | Karma | Status\n:---|:---|:---|:---|:---|:---|:---|:---\n{1}'
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


def get_url(*, cursor, submission):
    """Checks if a submission URL has already been indexed, and if not, returns it"""
    cursor.execute("SELECT * FROM indexed_submissions WHERE id=%s", (str(submission.id),))
    if results := cursor.fetchall():
        return False
    return submission.url.replace('m.imgur.com', 'i.imgur.com').lower()


def fetch_media(img_url):
    """Fetches submission media"""
    with requests.get(img_url) as resp:
        try:
            return Image.open(BytesIO(resp.content))
        except UnidentifiedImageError:
            logger.debug('Encountered unidentified image, ignoring')
            return False


class BotClient:
    """The main Reposterminator object"""

    def __init__(self):
        self._setup_connections()
        self.subreddits = list()
        self._update_subs()

    def _setup_connections(self):
        """Establishes a Reddit and database connection"""
        try:
            self.conn = psycopg2.connect(
                dbname=db_name,
                user=db_user,
                host=db_host,
                password=db_pass,
                connect_timeout=5) # If your server is slow to connect to, increase this value
            self.conn.autocommit = True
            self.reddit = praw.Reddit(
                client_id=reddit_id,
                client_secret=reddit_secret,
                password=reddit_pass,
                user_agent=reddit_agent,
                username=reddit_name)
        except Exception as e:
            logger.critical(f'Connection setup failed; exiting: {e}')
            exit(1)
        else:
            logger.info('Reddit and database connections successfully established')

    def run(self):
        """Runs the bot
        This function is entirely blocking, so any calls to other functions must
        be made prior to calling this."""
        while True:
            self._handle_dms()
            if self.subreddits:
                for sub in self.subreddits:
                    if not sub.indexed:
                        self._scan_new_sub(sub) # Needs to be full-scanned first
                    if sub.indexed:
                        self._scan_submissions(sub) # Scanned with intention of reporting now
                self._handle_dms()
            else:
                logger.error('Found no subreddits, exiting')
                exit(1)

    def _update_subs(self):
        """Updates the list of subreddits"""
        self.subreddits.clear()
        with self.conn.cursor() as cur:
            cur.execute('SELECT * FROM subreddits')
            for sub, indexed in cur.fetchall():
                self.subreddits.append(SubData(sub, indexed))
        logger.info('Updated list of subreddits')

    def __len__(self):
        return len(self.subreddits)

    def __iter__(self):
        for sub in self.subreddits:
            yield sub

    def _handle_submission(self, submission, should_report):
        """Handles the submissions, deciding whether to index or report them"""
        if submission.is_self:
            return
        cur = self.conn.cursor()
        if (img_url := get_url(cursor=cur, submission=submission)) is False:
            return
        processed = False
        try:
            if (media := fetch_media(img_url)) is False:
                return
            hash_ = diff_hash(media)
            media_data = (hash_, str(submission.id), submission.subreddit.display_name)
            as_meddata = MediaData(*media_data)
            cur.execute("SELECT * FROM media_storage WHERE subname=%s", (as_meddata.subname,))
            def get_matches():
                for item in cur.fetchall():
                    post = MediaData(*item)
                    compared = int(((64 - bin(hash_ ^ int(post.hash)).count('1'))*100.0)/64.0)
                    if compared > THRESHOLD:
                        yield post

            if should_report:
                if (matches := [*get_matches()]) and len(matches) <= 10:
                    logger.info(f'Found repost {as_meddata.id}; handling...')
                    logging.debug(f'Found matches {matches}')
                    self._do_report(submission, matches)

            cur.execute("INSERT INTO media_storage VALUES(%s, %s, %s)", media_data)
            processed = True

        except Exception as e:
            logger.error(f'Error processing submission {submission.id}: {e}')

        is_deleted = submission.author == '[deleted]'
        submission_data = (
            str(submission.id),
            str(submission.subreddit.display_name),
            float(submission.created),
            str(submission.author),
            str(submission.title),
            str(submission.url),
            int(submission.score),
            is_deleted,
            processed)
        cur.execute('INSERT INTO indexed_submissions (id, subname, timestamp, author,'
                    'title, url, score, deleted, processed) '
                    'VALUES(%s, %s, %s, %s, %s, %s, %s, %s, %s)', submission_data)

    def _do_report(self, submission, matches):
        """Executes reporting based on the matches retrieved from a processed submission"""
        cur = self.conn.cursor()
        active = 0
        rows = str()
        for match in matches:
            cur.execute(f"SELECT * FROM indexed_submissions WHERE id='{match.id}'")
            match_original = cur.fetchone()
            original_post = self.reddit.submission(id=match_original[0])
            cur_score = int(original_post.score)
            if original_post.removed:
                cur_status = 'Removed'
            elif original_post.author == '[deleted]':
                cur_status = 'Deleted'
            else:
                cur_status = 'Active'
                active += 1
            rows += ROW_TEMPLATE.format(
                match_original[3],
                datetime.fromtimestamp(match_original[2]),
                match_original[5],
                match_original[4],
                match_original[0],
                cur_score,
                cur_status)
        # submission.report(f'Possible repost ( {len(matches)} matches | {len(matches) - active} removed/deleted )')
        # reply = submission.reply(INFO_TEMPLATE.format(submission.author, rows))
        # with suppress(Exception):
            # praw.models.reddit.comment.CommentModeration(reply).remove(spam=False)
        logger.info(f'Finished handling and reporting repost https://redd.it/{submission.id}')

    def _scan_submissions(self, sub):
        """Scans /new/ for an already indexed subreddit"""
        logger.debug(f'Scanning r/{sub.subname} for new posts')
        for submission in self.reddit.subreddit(sub.subname).new():
            self._handle_submission(submission, True)

    def _scan_new_sub(self, sub):
        """Performs initial indexing for a new subreddit"""
        logging.info(f'Performing full scan for r/{sub.subname}')
        for _time in ('all', 'year', 'month'):
            for submission in self.reddit.subreddit(sub.subname).top(time_filter=_time):
                logger.debug(f'Indexing {submission.fullname} from r/{sub.subname} top {_time}')
                self._handle_submission(submission, False)
        with self.conn.cursor() as cur:
            cur.execute("UPDATE subreddits SET indexed=TRUE WHERE name=%s", (sub.subname,))
        self._update_subs()

    def _handle_dms(self):
        """Checks direct messages for new subreddits and removals"""
        for msg in self.reddit.inbox.unread(mark_read=True):
            if not isinstance(msg, praw.models.Message):
                msg.mark_read()
                continue
            if msg.body.startswith(('**gadzooks!', 'gadzooks!')) or msg.subject.startswith('invitation to moderate'):
                self._accept_invite(msg)
                continue
            if "You have been removed as a moderator from " in msg.body:
                self._handle_mod_removal(msg)
                continue

    def _accept_invite(self, msg):
        """Accepts an invite to a new subreddit and adds it to the database"""
        msg.mark_read()
        msg.subreddit.mod.accept_invite()
        with self.conn.cursor() as cur:
            cur.execute("INSERT INTO subreddits VALUES(%s, FALSE) ON CONFLICT DO NOTHING", (str(msg.subreddit),))
        self._update_subs()
        logger.info(f"Accepted mod invite to r/{msg.subreddit}")

    def _handle_mod_removal(self, msg):
        """Handles removal from a subreddit, clearing the sub's entry in the database"""
        msg.mark_read()
        with self.conn.cursor() as cur:
            cur.execute('DELETE FROM subreddits WHERE name=%s', (str(msg.subreddit),))
        self._update_subs()
        logger.info(f"Handled removal from r/{msg.subreddit}")

