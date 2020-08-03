DROP TABLE IF EXISTS subreddits;
DROP TABLE IF EXISTS indexed_submissions;
DROP TABLE IF EXISTS media_storage;
-- clear out any pre-existing relations

CREATE TABLE subreddits (
    name VARCHAR(21) PRIMARY KEY,
    indexed BOOLEAN
); -- store our subreddits and their indexed status

CREATE TABLE indexed_submissions (
    id VARCHAR(10) PRIMARY KEY,
    subname VARCHAR(21),
    timestamp DOUBLE PRECISION,
    author VARCHAR(50),
    title TEXT,
    url TEXT,
    score DOUBLE PRECISION,
    deleted BOOLEAN,
    processed BOOLEAN
); -- store our submissions (the actual posts)

CREATE TABLE media_storage (
    hash VARCHAR(32),
    submission_id VARCHAR(10),
    subname VARCHAR(21),
    PRIMARY KEY (submission_id, hash)
); -- store the media of our submissions
