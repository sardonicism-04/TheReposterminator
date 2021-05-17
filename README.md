# TheReposterminator

> TheReposterminator now has a userscript to make working with it even easer! [See here for more](#userscript-usage)

> [Install it here!](https://github.com/sardonicism-04/TheReposterminator/raw/master/popout-viewer.user.js)

TheReposterminator is a Reddit bot made to detect reposts, and help make moderating a whole lot easier.
* Indexes submission media as soon as it joins a subreddit
* Retains indexed media even after being removed from a subreddit, so if readded, it can start working again without a problem
* Reports possible reposts, and leaves a comment with more detail, listing all detected duplicates

# How does it work?
Once you add it to a subreddit, TheReposterminator will index posts from the top of the subreddit initially, and then it will start scanning /new/ regularly. If it finds a submission that matches other stored submissions for the subreddit, it will flag it.

![An example of TheReposterminator reporting a post and leaving a comment with details](https://i.imgur.com/VnjYWv2.png)

TheReposterminator keeps track of submission media by storing a hash generated by the pixels in the image. Whenever it scans media, it uses an algorithm to compare the hashes of the images, and if the similarity is above a certain threshold, it will report it.

# Sounds great, how do I use it?
Using TheReposterminator is simple; simply invite /u/TheReposterminator to moderate a subreddit of your choice, and within a few minutes, the subreddit will be indexed, and it'll be scanned for reposts constantly. 

While TheReposterminator can work with any permissions, it requires at least the `Manage Posts and Comments` permissions in order to auto-remove its own comments. Once TheReposterminator has indexed your subreddit, you will begin to see its reports in the mod queue, and that's it!

If you don't want TheReposterminator helping out anymore, it's as simple as removing it as a moderator of the subreddit. TheReposterminator will retain media processed on your subreddit in the event that you want to add it back, so it can seamlessly integrate back into the subreddit.

# Userscript usage
TheReposterminator also has a userscript that can be used with extensions such as [Greasemonkey](https://www.greasespot.net/) and [Tampermonkey](https://www.tampermonkey.net/). It adds a new button to flagged posts that launches a small popout that shows the chart provided by TheReposterminator's comment, saving the hassle of opening the comments section for each post.

The userscript can be installed by clicking [here](https://github.com/sardonicism-04/TheReposterminator/raw/master/popout-viewer.user.js) with a userscript engine (i.e. Grease/Tampermonkey) installed on your browser.

# What if I want to run my own instance?
I'd prefer that you don't run an instance of the bot, but I can't stop you, so here's a quick guide.

1. Install **Python3.9** or above, as it is required to run the bot at all.

2. Install the bot's dependencies, that is, `pip install -Ur requirements.txt`

3. Have a database set up, and with the `psql` tool, run:

`\i schema.sql`

This will create all necessary tables required to store the bot's data.

4. Create a copy of `example_config.toml`, and rename it to `config.toml`. Add the correct values to the file.

5. Have the Rust language installed on your system, and run `python setup.py install`. This will install the required cargo crates, and then build the Rust component of the project.

6. Run the bot

To run the bot, simply navigate to the directory that `schema.sql` and `requirements.txt` installed themselves to, and run TheReposterminator as a Python module.

`python3 -m TheReposterminator [arguments]`

Available arguments for running TheReposterminator can be found by running `python3 -m TheReposterminator -h`
