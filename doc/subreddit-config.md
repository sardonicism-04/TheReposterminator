# Subreddit Configuration
This document outlines the configuration options that TheReposterminator understands.

Configuration is (currently) done through the subreddit wiki. If TheReposterminator has the permissions to manage the wiki when you add it, it will create this page for you. If not, you'll need to create the page /thereposterminator_config.

Once you have created or updated a config page, send a message to the bot with the content (not implemented, do not send anything), and it will respond when it has updated your config. Alternatively, the config will automatically be updated every 24 hours on average (or when the bot restarts).

## Config Format
TheReposterminator config is written in the [TOML](https://toml.io/en/) format. Setting an option will look like:

`<option> = <value>`

## Options
`respond_to_mentions` 

**Default: false**

This option controls whether or not the bot will respond with a table when people u/ mention it on this subreddit.

`mentioned_threshold`

**Default: 85**

This option controls how similar (by percentage) 2 images have to be to be considered the same. This setting applies when the bot checks a post after being u/ mentioned, *not* when it automatically scans a post. It is recommended that this value is lower than the automatic threshold.

`sentry_threshold`

**Default: 90**

This option controls how similar (by percentage) 2 images have to be to be considered the same. This setting applies when the bot automatically scans a post, *not* when it is mentioned. 
