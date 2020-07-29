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
import asyncio
from contextlib import suppress

import aiohttp
import yarl

class Submission:
    """Small class to make working with submission JSON easier"""
    def __init__(self, submission_json):
        data = submission_json['data']
        self.data = data
        self.id = data.get('id')
        self.fullname = data.get('name')
        self.subreddit_name = data.get('subreddit')
        self.created = data.get('created')
        self.author = data.get('author')
        self.title = data.get('title')
        self.url = data.get('url')
        self.score = data.get('score')
        self.removed = bool(data.get('removed_by'))
        self.is_self = data.get('is_self')

entity_base = yarl.URL.build(scheme='https', host='reddit.com')

class RedditClient:
    """A client that handles connection and interaction with Reddit's REST API"""
    def __init__(self, *,
                 username,
                 password,
                 client_id,
                 client_secret,
                 user_agent,
                 logger,
                 loop=None):
        self.loop = loop or asyncio.get_running_loop()
        self.user_agent = user_agent
        self.username = username
        self.password = password
        self.client_id = client_id
        self.client_secret = client_secret
        self.lock = asyncio.Lock()
        self.rbase = yarl.URL.build(scheme='https', host='oauth.reddit.com')
        self.logger = logger
        self.session = None

    def __await__(self):
        """We don't have to worry about loop timing thanks to this"""
        return self.generate_token().__await__()

    async def generate_token(self):
        """Generates a new Reddit access token with the provided credentials"""
        auth = aiohttp.BasicAuth(login=self.client_id, password=self.client_secret)
        async with aiohttp.ClientSession() as session:
            async with session.post(
                'https://www.reddit.com/api/v1/access_token',
                auth=auth,
                data={'grant_type': 'password', 'username': self.username, 'password': self.password},
                headers={'User-Agent': self.user_agent}) as resp:
                    token_data = await resp.json()
        self.token = token_data['access_token']
        if self.session is not None:
            await self.session.close()
        self.session = aiohttp.ClientSession(
            headers={'Authorization': f'bearer {self.token}', 'User-Agent': self.user_agent})
        self.logger.info(f'Generated new access token successfully:\n{token_data}')
        return self

    async def request(self, method, url, **kwargs):
        """Handles the client's API interaction
        If a 401 status is received, it will generate a new token and reattempt the request
        Also implements its own ratelimiter to prevent 429s"""
        async with self.lock:
            with suppress(aiohttp.client_exceptions.ClientOSError):
                resp = await self.session.request(method, url, **kwargs)
            if resp.status == 401:
                await self.generate_token()
                return await self.request(method, url, **kwargs)
            try:
                sleep_time = int(resp.headers['x-ratelimit-reset']) / float(resp.headers['x-ratelimit-remaining'])
            except KeyError:
                sleep_time = 1
            await asyncio.sleep(sleep_time)
            return resp

    async def report(self, *, reason, submission_fullname):
        """Reports an entity with the given fullname under the given reason"""
        await self.request(
            'POST',
            (self.rbase / 'api/report'),
            data={'api_type': 'json', 'reason': reason, 'thing_id': submission_fullname})

    async def iterate_subreddit(self, *, subreddit, sort, time_filter=''):
        """Iterates over submissions in a given subreddit by the given sort"""
        resp = await self.request('GET', entity_base / f'r/{subreddit}/{sort}.json', params={'t': time_filter})
        data = (raw := await resp.json()).get('data')
        if not data:
            if resp.status == 403:
                yield 403
            return
        for submission in data['children']:
           yield Submission(submission)

    async def get_arbitrary_submission(self, *, thing_id):
        """Fetches an arbitrary submission based on a given identifier"""
        resp = await self.request('GET', entity_base / f'comments/{thing_id}.json')
        data = await resp.json()
        return Submission(data[0]['data']['children'][0])

    async def comment_and_remove(self, *, content, submission_fullname):
        """Submits a comment on a given submission with the given content, and then removes it"""
        data_submit = {'api_type': 'json', 'thing_id': submission_fullname, 'text': content}
        resp = await self.request('POST', (self.rbase / 'api/comment'), data=data_submit)
        comment_json = await resp.json()
        comment_fullname = (comment := comment_json['json']['data']['things'][(- 1)]['data'])['name']
        await self.request('POST', (self.rbase / 'api/remove'), data={'id': comment_fullname, 'spam': 'false'})
        return comment['permalink']

