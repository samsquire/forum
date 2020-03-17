from flask import Flask
from flask import render_template, redirect, request, make_response
import psycopg2

try:
    conn = psycopg2.connect("dbname='forum' user='forum' host='localhost' password='forum'")
except Exception as e:
    print("I am unable to connect to the database")
    print(e)


app = Flask(__name__)

@app.route("/")
def forums():
    thread_list = {}
    cur = conn.cursor()
    categories = cur.execute("""
    select * from categories;
    """)
    categories = list(cur.fetchmany(20))
    threads = []
    for category in categories:
        cur.execute("""
        select * from threads where category = %s;
        """, (category[0],))
        threads = cur.fetchmany(20)
        thread_list[category[1]] = threads
    return render_template("categories.html", categories=categories, threads=thread_list)

@app.route("/", methods=["POST"])
def add_forum():
    cur = conn.cursor()
    cur.execute("""
    insert into categories (title) values (%s) returning id;
    """, (request.form["category"],))
    id = cur.fetchone()[0]
    conn.commit()
    return make_response(redirect("/", 302))



@app.route("/categories/<category>")
def threads(category):
    cur = conn.cursor()
    cur.execute("""
    select * from categories where id = %s;
    """, (category,))
    category = cur.fetchmany(1)[0]
    cur.execute("""
    select * from threads where category = %s;
    """, (category[0],))
    threads = cur.fetchmany(50)
    return render_template("threads.html", category=category, threads=threads)

@app.route("/thread/<thread>", methods=["GET"])
def get_thread(thread):
    cur = conn.cursor()
    cur.execute("""
    select * from threads inner join posts on posts.thread = threads.id where threads.id = %s;
    """, (thread,))
    posts = cur.fetchmany(50)
    import pprint
    pprint.pprint(posts)
    cur.execute("""
    select * from categories where id = %s;
    """, (posts[0][2],))
    category = cur.fetchmany(1)[0]

    cur.execute("""
    select * from threads where id = %s;
    """, (thread,))
    thread = cur.fetchmany(1)[0]
    return render_template("thread.html", thread=thread, category=category, posts=posts)


@app.route("/thread", methods=["POST"])
def add_thread():
    cur = conn.cursor()
    cur.execute("""
    select * from categories where id = %s
    """, (request.form["category"],))
    category_id = cur.fetchone()[0]

    cur.execute("""
    insert into threads (title, category) values (%s, %s) returning id;
    """, (request.form["title"], request.form["category"]))
    id = cur.fetchone()[0]
    conn.commit()
    cur.execute("""
    insert into posts (thread, body) values (%s, %s) returning id;
    """, (id, request.form["body"]))
    id = cur.fetchone()[0]
    conn.commit()
    target = "/"
    if request.form["category"]:
        target = "/categories/" + str(category_id)
    return make_response(redirect(target, 302))

@app.route("/post/<thread>", methods=["POST"])
def add_post(thread):
    cur = conn.cursor()
    cur.execute("""
    insert into posts (thread, body) values (%s, %s) returning id;
    """, (thread, request.form["body"]))
    id = cur.fetchone()[0]
    conn.commit()
    return make_response(redirect("/thread/" + thread, 302))


if __name__ == "__main__":
    app.run()
