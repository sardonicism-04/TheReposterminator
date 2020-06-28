import os
from io import BytesIO
from datetime import datetime
import logging
import sys
from collections import namedtuple

import praw
import psycopg2
from PIL import Image, ImageStat, UnidentifiedImageError
import requests

from .config import *
from .differencer import diff_hash

conn = None
subredditSettings = None
THRESHOLD = 88

SubData = namedtuple('SubData', 'subname indexed')
MediaData = namedtuple('MediaData', 'hash id subname')

logger = logging.getLogger(__name__)
formatting = "[%(asctime)s] [%(levelname)s:%(name)s] %(message)s"
logging.basicConfig(
    format=formatting,
    level=logging.INFO,
    handlers=[logging.FileHandler('rterm.log'), logging.StreamHandler()])


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
                f"dbname='{db_name}' user='{db_user}' host='{db_host}' password='{db_pass}'",
                connect_timeout=5)
            self.conn.autocommit = True
            self.reddit = praw.Reddit(
                client_id=reddit_id,
                client_secret=reddit_secret,
                password=reddit_pass,
                user_agent=reddit_agent,
                username=reddit_name)
        except Exception as e:
            logger.critical(f'Connection setup failed; exiting: {e}')
            sys.exit()
        else:
            logger.info('Reddit and database connections successfully established')

    def run(self):
        """Runs the bot"""
        while True:
            self._handle_dms()
            if self.subreddits:
                for sub in self.subreddits:
                    if sub.indexed is False:
                        self._scan_new_sub(sub)
                    if sub.indexed:
                        self._scan_submissions(sub)
                self._handle_dms()
            else:
                logger.error('Found no subreddits, exiting')
                sys.exit()

    def _update_subs(self):
        """Updates the list of subreddits"""
        self.subreddits.clear()
        with self.conn.cursor() as cur:
            cur.execute('SELECT * FROM subreddits')
            for sub, indexed in cur.fetchall():
                self.subreddits.append(SubData(sub, indexed))
        logger.info('Updated list of subreddits')

    def _show_subreddits(self):
        """Returns a list of all subreddits the bot is active in"""
        formatted_results = f'{len(self.subreddits)} Subreddits:\n\n' + '\n'.join(s.subname for s in self.subreddits)
        return formatted_results

    def _handle_submission(self, submission, should_report):
        if submission.is_self:
            return
        cur = self.conn.cursor()
        cur.execute(f"SELECT * FROM indexed_submissions WHERE id='{str(submission.id)}'")
        if results := cur.fetchall():
            return
        processed = False
        img_url = str(submission.url.replace('m.imgur.com', 'i.imgur.com')).lower()
        try:
            with requests.get(img_url) as resp:
                try:
                    media = Image.open(BytesIO(resp.content))
                except UnidentifiedImageError:
                    return
            hash_ = diff_hash(media)
            _media_data = (hash_, str(submission.id), submission.subreddit.display_name)
            as_meddata = MediaData(*_media_data)
            cur.execute(f"SELECT * FROM media_storage WHERE subname='{as_meddata.subname}'")
            matches = list()
            for item in cur.fetchall():
                post = MediaData(*item)
                compared = int(((64 - bin(hash_ ^ int(post.hash)).count('1'))*100.0)/64.0)
                if compared > THRESHOLD:
                    matches.append(post)
            if should_report:
                if matches and len(matches) <= 10:
                    logger.info(f'Found repost {as_meddata.id}; handling...')
                    self._do_report(submission, matches)
            cur.execute("INSERT INTO media_storage VALUES(%s, %s, %s)", _media_data)
            processed = True
        except Exception as e:
            logger.error(f'Error processing submission {submission.id}: {e}')
        is_deleted = True if submission.author == '[deleted]' else False
        _submission_data = (
            str(submission.id),
            str(submission.subreddit.display_name),
            float(submission.created),
            str(submission.author),
            str(submission.title),
            str(submission.url),
            int(submission.score),
            is_deleted,
            processed)
        cur.execute(f'INSERT INTO indexed_submissions VALUES(%s, %s, %s, %s, %s, %s, %s, %s, %s)', _submission_data)

    def _do_report(self, submission, matches):
        cur = self.conn.cursor()
        info_template = '**OP:** {0}\n\n**History:**\n\nUser | Date | Image | Title | Karma | Status\n:---|:---|:---|:---|:---|:---|:---|:---\n{1}'
        row_template = '/u/{0} | {1} | [URL]({2}) | [{3}](https://redd.it/{4}) | {5} | {6}\n'
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
            rows += row_template.format(
                match_original[3],
                datetime.fromtimestamp(match_original[2]),
                match_original[5],
                match_original[4],
                match_original[0],
                cur_score,
                cur_status)
        # submission.report(f'Possible repost ( {len(matches)} matches | {len(matches) - active} removed/deleted )')
        # _reply = submission.reply(info_template.format(submission.author, rows))
        # praw.models.reddit.comment.CommentModeration(_reply).remove(spam=False)
        logger.info(f'Finished handling and reporting repost {submission.id}')

    def _scan_submissions(self, sub):
        logger.info(f'Scanning r/{sub.subname} for new posts')
        for submission in self.reddit.subreddit(sub.subname).new():
            self._handle_submission(submission, True)

    def _scan_new_sub(self, sub):
        logging.info(f'Doing full scan for r/{sub.subname}')
        for _time in ('all', 'year', 'month'):
            for submission in self.reddit.subreddit(sub.subname).top(time_filter=_time):
                logger.info(f'Indexing {submission.fullname} from r/{sub.subname} top {_time}')
                self._handle_submission(submission, False)
        with self.conn.cursor() as cur:
            cur.execute(f"UPDATE subreddits SET indexed=TRUE WHERE name=%s", (sub.subname))

    def _handle_dms(self):
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
        msg.mark_read()
        msg.subreddit.mod.accept_invite()
        with self.conn.cursor() as cur:
            cur.execute("INSERT INTO subreddits VALUES(%s, FALSE) ON CONFLICT DO NOTHING", (str(msg.subreddit),))
        self._update_subs()
        logger.info(f"Accepted mod invite to r/{msg.subreddit}")

    def _handle_mod_removal(self, msg):
        msg.mark_read()
        with self.conn.cursor() as cur:
            cur.execute('DELETE FROM subreddits WHERE name=%s', (str(msg.subreddit),))
        self._update_subs()
        logger.info(f"Handled removal from r/{msg.subreddit}")

