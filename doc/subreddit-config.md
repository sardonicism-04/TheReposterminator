# Subreddit Configuration
This document outlines the configuration options that TheReposterminator understands.

Configuration is (currently) done through the subreddit wiki. If TheReposterminator has the permissions to manage the wiki when you add it, it will create this page for you. If not, you'll need to create the page /thereposterminator_config.

Once you have created or updated a config page, invoke the bot's `update` command (see commands documentation for info), and it will respond when it has updated your config. Alternatively, the config will automatically be updated every 24 hours on average (or when the bot restarts).

## Config Format
TheReposterminator config is written in the [TOML](https://toml.io/en/) format. Setting an option will look like:  
`<option> = <value>`

## Invalid Values
Some configuration options have limits on values that can be provided to them (such as a minimum allowed value). Using an invalid value in your configuration will result in TheReposterminator rejecting your changes if you use the `update` command, or replacing the invalid value with the default value when it loads the configuration automatically.

It is obviously recommended that any invalid values be resolved as soon as possible.

## Missing Values
In the event that your subreddit's config is missing values (for example, if a new config option is added), then TheReposterminator will substitute the default value in for that option.

## Options
`respond_to_mentions`  
**Default: false**  
This option controls whether or not the bot will respond with a table when people u/ mention it on this subreddit.

`mentioned_threshold`  
**Default: 85**  
**Minimum Allowed Value: 80**  
This option controls how similar (by percentage) 2 images have to be to be considered the same. This setting applies when the bot checks a post after being u/ mentioned, *not* when it automatically scans a post. It is recommended that this value is lower than the automatic threshold.

`sentry_threshold`  
**Default: 90**  
**Minimum Allowed Value: 80**  
This option controls how similar (by percentage) 2 images have to be to be considered the same. This setting applies when the bot automatically scans a post, *not* when it is mentioned. 

`remove_sentry_comments`  
**Default: true**  
This option controls whether or not the bot will remove its automated comments after making them. Defaults to removing them, but disabling this can be useful in certain scenarios.

`max_post_age`  
**Default: -1**  
This option sets the maximum age **in days** for a post to be considered a repost.  
In other words, if:
- `max_post_age` is set to 60
- A post is caught as a repost, matching 3 other posts, with ages 35, 57, and 78 days

In this situation, the *first* two posts will be flagged a reposts, but the last post will *not*.  
This setting is useful for when your subreddit allows reposts after a certain length of time.

Any value less than 1 disables the maximum age check.

### Autoremoval
`autoremove`  
**Default: false**  
This option controls whether or not the bot will auto-remove submissions that meet certain criteria.

`autoremove_threshold`  
**Default: 90**  
**Minimum Allowed Value: 90**  
This option controls how similar (by percentage) the *least similar match* must be to a submission for it to be removed automatically. To elaborate, consider the following scenario:
- `autoremove_threshold` is set to `95`
- A post is caught as a repost, matching 3 other posts, with similarities 96, 99, 100

In this case, the post **will** be automatically removed. In contrast:
- `autoremove_threshold` is set to `95`
- A post is caught as a repost, matching 3 other posts, with similarities 96, 92, 100

In this case, the post will **not** be automatically removed, because the *least similar match* has a similarity rating that is below the configured threshold.