import psycopg2

try:
    conn = psycopg2.connect("dbname='forum' user='forum' host='172.17.0.1' password='forum'")
except Exception as e:
    print("I am unable to connect to the database")
    print(e)

cur = conn.cursor()
# create table one by one
cur.execute("""
drop table categories cascade;
create table if not exists categories (
    id SERIAL PRIMARY KEY,
    title TEXT,
    published_date TIMESTAMP
);
drop table threads  cascade;
create table if not exists threads (
    id SERIAL PRIMARY KEY,
    title text,
    category INTEGER,
    author TEXT,
    published_date TIMESTAMP
);
drop table posts  cascade;
create table if not exists posts (
    id SERIAL PRIMARY KEY,
    body text,
    thread INTEGER,
    author TEXT,
    published_date TIMESTAMP,
    foreign key (thread) references threads (id)
);

create table if not exists people (
    id serial primary key,
    firstname text,
    lastname text,
    nickname text
);

create table if not exists scripts (
    id serial primary key,
    author text,
    javascript text,
    html text,
    css text,
    approved text
);

create table if not exists script_data (
    id serial primary key,
    data text
);

create table if not exists identikit_posts (
    id serial primary key,
    body text,
    name text,
    reply_depth integer,
    reply_to integer
);

create table if not exists identikit_community_posting (
    id serial primary key,
    post integer,
    community text
);

create table if not exists questions (
    id serial primary key,
    short text,
    question text
);

create table if not exists answers (
    id serial primary key,
    question integer,
    answer text
);

create table if not exists user_communities (
    id serial primary key,
    community text,
    user_name text
);
""")

# close communication with the PostgreSQL database server
cur.close()
# commit the changes
conn.commit()
