import os
from io import BytesIO
import time
import logging
import sys
from collections import namedtuple
from math import prod

import praw
import psycopg2
from PIL import Image, ImageStat, UnidentifiedImageError
import requests
from imagehash import average_hash

from .config import *
from .differencer import Differencer

conn = None
subredditSettings = None
SubData = namedtuple('SubData', 'subname indexed')

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
                password=reddit_secret,
                user_agent=reddit_agent,
                username=reddit_name)
        except Exception as e:
            logger.critical(f'Connection setup failed; exiting: {e}')
            sys.exit()
        else:
            logger.info('Reddit and database connections successfully established')

    def _update_subs(self):
        """Updates the list of subreddits"""
        self.subreddits.clear()
        with self.conn.cursor() as cur:
            cur.execute('SELECT * FROM subreddits')
            for sub, indexed in cur.fetchall():
                self.subreddits.append(sub, indexed)
        logger.info('Updated list of subreddits')

    def _show_subreddits(self):
        """Returns a list of all subreddits the bot is active in"""
        formatted_results = f'{len(results)} Subreddits:\n\n' + '\n'.join(s.subname for s in self.subreddits)
        return formatted_results

    def _index_submission(self, submission):
        if submission.is_self:
            return
        cur = self.conn.cursor()
        cur.execute(f"SELECT * FROM indexed_submissions WHERE id='{str(submission.id)}'")
        if results := cur.fetchall():
            return
        processed = False
        img_url = str(submission.url.replace('m.imgur.com', 'i.imgur.com')).lower()
        with requests.get(img_url) as resp:
            try:
                _media = Image(BytesIO(resp.content))
            except UnidentifiedImageError:
                return
        width, height, pixels = _media.size, prod(_media.size)
        img_differ = Differencer(_media)
        _hash = img_differ._diff_hash
        _media_data = (_hash, str(submission.id), submission.subreddit.display_name, width, height, pixels)
        self._do_report(submission, _media_data)
        

BotClient()

def Main():

    r = None
    global subredditSettings

    # ----------- MAIN LOOP ----------- #
    while True:

        try:
            checkMail(r)

            loadSubredditSettings()

            if subredditSettings:

                for settings in subredditSettings:

                    if settings[1] is False:

                        ingestFull(r, settings)
                        loadSubredditSettings()

                    if settings[1]:

                        ingestNew(r, settings)

                checkMail(r)

            else:

                return

        except (Exception) as e:

            logger.error('Error on main loop - {0}'.format(e))

    return


# Import new submissions
def ingestNew(r, settings):

    logger.info('Scanning new for /r/{0}'.format(settings[0]))

    try:

        for submission in r.subreddit(settings[0]).new():

            try:

                indexSubmission(r, submission, settings, True)

            except (Exception) as e:

                logger.error('Error ingesting new {0} - {1} - {2}'.format(
                    settings[0], submission.id, e))

    except (Exception) as e:

        logger.error('Error ingesting new {0} - {1}'.format(settings[0], e))

    return


# Import all submissions from all time within a sub
def ingestFull(r, settings):
    logging.info("ingest for /r/{0}".format(settings[0]))

    for topall in r.subreddit(settings[0]).top(time_filter="all"):
        logger.info(f"ingestfull of topall found submission {topall.fullname}"
                " for r/{settings[0]}")
        indexSubmission(r, topall, settings, False)
    for topyear in r.subreddit(settings[0]).top(time_filter="year"):
        logger.info(f"ingestfull of topyear found submission {topyear.fullname}"
                " for r/{settings[0]}")
        indexSubmission(r, topyear, settings, False)
    for topmonth in r.subreddit(settings[0]).top(time_filter="month"):
        logger.info(f"ingestfull of topmonth found submission {topmonth.fullname}"
                " for r/{settings[0]}")
        indexSubmission(r, topmonth, settings, False)

    # Update DB
    global conn
    cur = conn.cursor()
    cur.execute(
        "UPDATE SubredditSettings SET imported=TRUE WHERE subname='{0}'".format(
            settings[0]
        )
    )


def indexSubmission(r, submission, settings, enforce):

    try:

        # Skip self posts
        if submission.is_self:
            return

        global conn
        cur = conn.cursor()

        # Check for an existing entry so we don't make a duplicate
        cur.execute(
            'SELECT * FROM Submissions WHERE id=\'{0}\''.format(submission.id))
        results = cur.fetchall()

        if results:
            return

        # Download and process the media
        submissionProcessed = False

        media = str(submission.url.replace(
            "m.imgur.com", "i.imgur.com")).lower()

        # Check url
        if (
            (media.endswith(".jpg") or media.endswith(".jpg?1")
                or media.endswith(".png") or media.endswith("png?1")
                or media.endswith(".jpeg"))
            or "reddituploads.com" in media or "reutersmedia.net" in media
            or "500px.org" in media or "redditmedia.com" in media
            ):

            try:

                # Download it
                req = urllib.request.Request(media, headers={
                             'User-Agent': ('Mozilla/5.0'
                                            '(Macintosh; Intel Mac'
                                            ' OS X 10_5_8)'
                                            'AppleWebKit/534.50.2 '
                                            '(KHTML, like'
                                            'Gecko) Version/5.0.6 '
                                            'Safari 533.22.3')})
                mediaContent = urllib.request.urlopen(req).read()

                try:

                    img = Image.open(BytesIO(mediaContent))

                    width, height = img.size
                    pixels = width*height

                    imgHash = DifferenceHash(img)

                    mediaData = (
                        imgHash,
                        str(submission.id),
                        settings[0],
                        1,
                        1,
                        width,
                        height,
                        pixels,
                    )

                    if enforce:

                        enforceSubmission(r, submission, settings, mediaData)

                    # Add to DB
                    cur.execute(
                        ('INSERT INTO Media(hash, submission_id, subreddit, frame_number, frame_count, frame_width, frame_height, total_pixels) VALUES(%s, %s, %s, %s, %s, %s, %s, %s)'), mediaData)

                    submissionProcessed = True

                except (Exception) as e:

                    logger.warning('Error processing {0} - {1}'.format(submission.id, e))

            except (Exception) as e:

                logger.warning('Failed to download {0} - {1}'.format(submission.id, e))

        # Add submission to DB
        submissionDeleted = False
        if submission.author == '[deleted]':
            submissionDeleted = True

        submissionValues = (
            str(submission.id),
            settings[0],
            float(submission.created),
            str(submission.author),
            str(submission.title),
            str(submission.url),
            int(submission.num_comments),
            int(submission.score),
            submissionDeleted,
            submission.removed,
            str(submission.removal_reason),
            False,
            submissionProcessed
        )

        try:
            cur.execute('INSERT INTO Submissions(id, subreddit, timestamp, author, title, url, comments, score, deleted, removed, removal_reason, blacklist, processed) VALUES(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)', submissionValues)
        except Exception as e:
            logger.error('Error adding {0} - {1}'.format(submission.id, e))

    except (Exception) as e:

        logger.error('Failed to ingest {0} - {1}'.format(submission.id, e))

    return


def enforceSubmission(r, submission, settings, mediaData):

    try:

        if submission.removed:
            return

        global conn
        cur = conn.cursor()

        # Check if it's the generic 'deleted image' from imgur
        if mediaData[0] == '9925021303884596990':

            submission.report('Image removed from imgur.')

            return

        # Handle single images
        if mediaData[4] == 1:

            cur.execute(
                'SELECT * FROM Media WHERE frame_count=1 AND subreddit=\'{0}\''.format(settings[0]))
            mediaHashes = cur.fetchall()

            matchInfoTemplate = '**OP:** {0}\n\n**Image Stats:**\n\n* Width: {1}\n\n* Height: {2}\n\n* Pixels: {3}\n\n**History:**\n\nUser | Date | Match % | Image | Title | Karma | Comments | Status\n:---|:---|:---|:---|:---|:---|:---|:---\n{4}'
            matchRowTemplate = '/u/{0} | {1} | {2}% | [{3} x {4}]({5}) | [{6}](https://redd.it/{7}) | {8} | {9} | {10}\n'
            matchCount = 0
            matchCountActive = 0
            matchRows = ''
            reportSubmission = False
            removeSubmission = False
            blacklisted = False

            # Find matches
            for mediaHash in mediaHashes:

                mediaSimilarity = int(
                    ((64 - bin(mediaData[0] ^ int(mediaHash[0])).count('1'))*100.0)/64.0)

                parentBlacklist = False

                # Report threshold
                if mediaSimilarity > settings[6]:

                    cur.execute(
                        'SELECT * FROM Submissions WHERE id=\'{0}\''.format(mediaHash[1]))
                    mediaParent = cur.fetchone()
                    parentBlacklist = mediaParent[11]

                    originalSubmission = r.submission(id=mediaParent[0])

                    currentScore = int(originalSubmission.score)
                    currentComments = int(originalSubmission.num_comments)
                    currentStatus = 'Active'
                    if originalSubmission.removed:
                        currentStatus = 'Removed'
                    elif originalSubmission.author == '[deleted]':
                        currentStatus = 'Deleted'

                    matchRows = matchRows + matchRowTemplate.format(mediaParent[3], convertDateFormat(mediaParent[2]), str(mediaSimilarity), str(
                        mediaData[5]), str(mediaData[6]), mediaParent[5], mediaParent[4], mediaParent[0], currentScore, currentComments, currentStatus)

                    matchCount = matchCount + 1

                    if currentStatus == 'Active':
                        matchCountActive = matchCountActive + 1

                    if matchCount <= 10:
                        reportSubmission = True
                    else:
                        return

                # Remove threshold
                if mediaSimilarity > settings[8]:

                    removeSubmission = True

                    # TODO: Add comment count and karma as thresholds

                # Blacklist
                if mediaSimilarity == 100 and parentBlacklist:

                    blacklisted = True

            if reportSubmission:

                matchesRemoved = matchCount - matchCountActive
                submission.report('Possible repost ( {0} matches | {1} removed )'.format(
                    matchCount, matchesRemoved))
                replyInfo = submission.reply(matchInfoTemplate.format(
                    submission.author, mediaData[5], mediaData[6], mediaData[7], matchRows))
                praw.models.reddit.comment.CommentModeration(
                    replyInfo).remove(spam=False)
                logger.info(f'Repost found and reported - {submission.id}')

            if blacklisted:

                submission.remove(spam=False)
                replyRemove = submission.reply(settings[9])
                replyRemove.distinguish(how='yes', sticky=True)

            if removeSubmission:

                submission.remove(spam=False)
                replyRemove = submission.reply(settings[9])
                replyRemove.distinguish(how='yes', sticky=True)

    except (Exception) as e:

        logger.warning('Failed to enforce {0} - {1}'.format(submission.id, e))

    return


# Get settings of all subreddits from DB
def loadSubredditSettings():

    global conn
    global subredditSettings

    cur = conn.cursor()
    cur.execute('SELECT * FROM SubredditSettings')
    subredditSettings = cur.fetchall()

    return


# Check messages for blacklist requests
def checkMail(r):

    try:

        for msg in r.inbox.unread(mark_read=True):
            if not isinstance(msg, praw.models.Message):
                msg.mark_read()
                continue

            if (
                msg.body.startswith("**gadzooks!")
                or msg.body.startswith("gadzooks!")
                or msg.subject.startswith("invitation to moderate")
            ):
                acceptModInvite(msg)

            if msg.subject.strip().lower().startswith("moderator message from"):
                msg.mark_read()
                continue

            if "You have been removed as a moderator from " in msg.body:
                removeModStatus(msg)
                continue

            if msg.subject == 'blacklist':

                submissionId = ''

                if len(msg.body) == 6:
                    submissionId = msg.body
                elif 'reddit.com' in msg.body and '/comments/' in msg.body:
                    submissionId = msg.body[msg.body.find(
                        '/comments/') + len('/comments/'):6]
                elif 'redd.it' in msg.body:
                    submissionId = msg.body[msg.body.find(
                        'redd.it/') + len('redd.it/'):6]

                if len(submissionId) == 6:

                    blacklistSubmission = r.submission(id=submissionId)

                    for settings in subredditSettings:

                        if settings[0] == blacklistSubmission.subreddit:

                            for moderator in r.subreddit(settings[0]).moderator():

                                if msg.author == moderator:

                                    indexSubmission(
                                        r, blacklistSubmission, settings, False)

                                    global conn
                                    cur = conn.cursor()
                                    cur.execute(
                                        'UPDATE Submissions SET blacklist=TRUE WHERE id=\'{0}\''.format(submissionId))

    except (Exception) as e:

        logger.warning('Failed to check messages - {0}'.format(e))

    return


def acceptModInvite(message):
    try:
        global conn
        cur = conn.cursor()
        message.mark_read()
        message.subreddit.mod.accept_invite()

        cur.execute(
            "SELECT * FROM subredditsettings WHERE subname=%s",
            (str(message.subreddit),),
        )
        results = cur.fetchall()
        if results:
            cur.execute(
                "UPDATE subredditsettings SET enabled=True WHERE subname=%s",
                (str(message.subreddit),),
            )
        else:
            cur.execute(
                "INSERT INTO subredditsettings (subname, imported, min_width, min_height, min_pixels, min_size, report_match_threshold, report_match_message, remove_match_threshold, remove_match_message, report_indirect, remove_indirect, remove_indirect_message) VALUES(%s, False, 450, 450, 360000, 1, 88, '', 100, '', True, False, '')",
                (str(message.subreddit),),
            )
        logger.info("Accepted mod invite for /r/{}".format(message.subreddit))
    except Exception:
        pass


def removeModStatus(message):
    try:
        global conn
        cur = conn.cursor()
        message.mark_read()
        cur.execute(
            "DELETE from subredditsettings WHERE subname=%s",
            (str(message.subreddit),),
        )
        logger.info(f"Removed as mod in /r/{message.subreddit}")
    except Exception:
        logger.error("Unable to update set sub settings removed status for r/{}. ID: {}".format(
                message.subreddit, message.fullname))
# Hashing function


def DifferenceHash(theImage):

    theImage = theImage.convert("L")
    theImage = theImage.resize((8, 8), Image.ANTIALIAS)
    previousPixel = theImage.getpixel((0, 7))
    differenceHash = 0

    for row in range(0, 8, 2):

        for col in range(8):
            differenceHash <<= 1
            pixel = theImage.getpixel((col, row))
            differenceHash |= 1 * (pixel >= previousPixel)
            previousPixel = pixel

        row += 1

        for col in range(7, -1, -1):
            differenceHash <<= 1
            pixel = theImage.getpixel((col, row))
            differenceHash |= 1 * (pixel >= previousPixel)
            previousPixel = pixel

    return differenceHash


def convertDateFormat(timestamp):

    return str(time.strftime('%B %d, %Y - %H:%M:%S', time.localtime(timestamp)))
