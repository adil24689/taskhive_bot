DROP TABLE IF EXISTS users;
DROP TABLE IF EXISTS tasks;
DROP TABLE IF EXISTS submissions;
DROP TABLE IF EXISTS recharges;
DROP TABLE IF EXISTS withdrawals;

CREATE TABLE users (
    user_id INTEGER PRIMARY KEY,
    username TEXT,
    name TEXT,
    points INTEGER DEFAULT 0,
    earnings INTEGER DEFAULT 0,
    referred_by INTEGER
);

CREATE TABLE tasks (
    task_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    task_type TEXT,
    title TEXT,
    description TEXT,
    proof_type TEXT,
    total_workers INTEGER,
    completed INTEGER DEFAULT 0,
    reward INTEGER,
    is_hidden INTEGER DEFAULT 0
);

CREATE TABLE submissions (
    submission_id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id INTEGER,
    worker_id INTEGER,
    proof TEXT,
    status TEXT DEFAULT 'pending'
);

CREATE TABLE recharges (
    recharge_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    amount INTEGER,
    method TEXT,
    trx_id TEXT,
    verified INTEGER DEFAULT 0
);

CREATE TABLE withdrawals (
    withdrawal_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    amount INTEGER,
    method TEXT,
    number TEXT,
    verified INTEGER DEFAULT 0
);
