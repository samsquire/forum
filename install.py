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
    title TEXT
);
drop table threads  cascade;
create table if not exists threads (
    id SERIAL PRIMARY KEY,
    title text,
    category INTEGER
);
drop table posts  cascade;
create table if not exists posts (
    id SERIAL PRIMARY KEY,
    body text,
    thread INTEGER,
    foreign key (thread) references threads (id)
);
""")

# close communication with the PostgreSQL database server
cur.close()
# commit the changes
conn.commit()
