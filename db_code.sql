DROP TABLE IF EXISTS subreddits;

CREATE TABLE subreddits (
    name VARCHAR(21) PRIMARY KEY,
    indexed BOOLEAN
);

DROP TABLE IF EXISTS indexed_submissions;

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
);

DROP TABLE IF EXISTS media_storage;

CREATE TABLE media_storage (
    hash VARCHAR(32),
    submission_id VARCHAR(10),
    subname VARCHAR(21),
    PRIMARY KEY (submission_id, hash)
);
