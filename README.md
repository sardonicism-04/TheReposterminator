# TheReposterminator
TheReposterminator is a reddit bot made to detect reposts, and help make moderating a whole lot easier.
* Indexed submission media as soon as it joins a subreddit
* Retains indexed media even after being removed from a subreddit, so if readded, it can start working again without a problem
* Reports possible reposts, and leaves a comment with more detail, listing all detected duplicates

Plus, TheReposterminator is *fast*. Due to its asynchronous codebase, it is able to handle submissions concurrently, meaning that it can take down multiple reposts at the same time. This is a significant step up from other repost bots, since it can quickly monitor posts.
# How does it work?
Once you add it to a subreddit, TheReposterminator will index posts from the top of the subreddit initially, and then it will start scanning /new/ regularly. If it finds a submission that matches other stored submissions for the subreddit, it will flag it.

![An example of TheReposterminator reporting a post and leaving a comment with details](https://i.imgur.com/VnjYWv2.png)

TheReposterminator keeps track of submission media by storing a hash generated by the pixels in the image. Whenever it scans media, it uses an algorithm to compare the hashes of the images, and if the similarity is above a certain threshold, it will report it.
# Sounds great, how do I use it?
Using TheReposterminator is simple; simply invite /u/TheReposterminator to moderate a subreddit of your choice, and within a few minutes, the subreddit will be indexed, and it'll be scanned for reposts constantly. 

While TheReposterminator can work with any permissions, it requires at least `posts` permissions in order to auto-remove its own comments. Once TheReposterminator has indexed your subreddit, you will begin to see its reports in the mod queue, and that's it!

If you don't want TheReposterminator helping out anymore, it's as simple as removing it as a moderator of the subreddit. TheReposterminator will retain media processed on your subreddit in the event that you want to add it back, so it can seamlessly integrate back into the subreddit.
# What if I want to run my own instance?
I'd prefer that you don't run an instance of the bot, but I can't stop you, so here's a quick guide.

1. Install **Python3.8** or above, as it is required to run the bot at all.

2. Install the bot's dependencies, that is, `pip install -U -r requirements.txt`

3. Have a database set up, and with the `psql` tool, run:

`\i db_code.sql`

This will create all necessary tables required to store the bot's data.

4. Create the `config.py` file in the same directory as `__main__.py` and `bot.py`. The format for this is as follows:

```py
__all__ = ['db_name', 'db_user', 'db_host', 'db_pass', 'reddit_id', 'reddit_secret', 'reddit_pass', 'reddit_agent', 'reddit_name']

db_name = '' # The name of the database used
db_user = '' # The name of the database user
db_host = '' # The database host
db_pass = '' # The password of the database

reddit_id = '' # The Reddit application's client ID
reddit_secret = '' # The Reddit application's client secret
reddit_pass = '' # The password of the Reddit account the bot uses
reddit_agent = '' # The user agent the bot will use
reddit_name = '' # The username of the Reddit account the bot uses
```

5. Run the bot

To run the bot, simply navigate to the directory that `db_code.sql` and `requirements.txt` installed themselves to, and run TheReposterminator as a Python module.

`python3 -m TheReposterminator [arguments]`

Available arguments for running TheReposterminator can be found by running `python3 -m TheReposterminator -h`
