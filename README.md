# TheReposterminator

> TheReposterminator has a userscript to make working with it even easer! [See here for more](#userscript)
    <br>
> [Install it here](https://github.com/sardonicism-04/TheReposterminator/raw/master/popout-viewer.user.js)

TheReposterminator is a Reddit bot made to detect reposts, and help make moderating a whole lot easier.
* Indexes submission media as soon as it joins a subreddit
* Retains indexed media even after being removed from a subreddit, so if readded, it can start working again without a problem
* Reports possible reposts, and leaves a comment with more detail, listing all detected duplicates

## Documentation
Documentation explaining everything about using and configuring TheReposterminator can be found [here](https://github.com/sardonicism-04/TheReposterminator/raw/master/doc).

## Userscript
TheReposterminator also has a userscript that can be used with extensions such as [Greasemonkey](https://www.greasespot.net/) or [Tampermonkey](https://www.tampermonkey.net/). It adds a new button to flagged posts that launches a small popout that shows the chart provided by TheReposterminator's comment, saving the hassle of opening the comments section for each post.

The userscript can be installed by clicking [here](https://github.com/sardonicism-04/TheReposterminator/raw/master/popout-viewer.user.js) with a userscript engine (i.e. Grease/Tampermonkey) installed on your browser.

## Self-hosting
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

    `python -m TheReposterminator [arguments]`

    Available arguments for running TheReposterminator can be found by running `python -m TheReposterminator -h`
