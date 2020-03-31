import psycopg2

try:
    conn = psycopg2.connect("dbname='forum' user='forum' host='localhost' password='forum'")
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
""")

# close communication with the PostgreSQL database server
cur.close()
# commit the changes
conn.commit()
