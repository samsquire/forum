from flask import Flask
from flask import render_template, redirect, request, make_response
import psycopg2
import os, smtplib, ssl, time
import yaml
import random
import re
import uuid
import hashlib
import collections

try:
    conn = psycopg2.connect("dbname='forum' user='forum' host='localhost' password='forum'")
except Exception as e:
    print("I am unable to connect to the database")
    print(e)

try:
    os.makedirs("/home/{}/secrets/tokens".format(os.environ["USER"]))
except FileExistsError as e:
    pass

def check_signed_in(from_cookie=False):
    email = None
    login = None
    username = ""
    if "email" in request.cookies:
        email = request.cookies["email"]
    else:
        email = request.args.get('email')
    if "login" in request.cookies:
        login = request.cookies["login"]
    else:
        login = request.args.get('login')
    signed_in = False
    user_email = None
    if login and email:
        # email = re.sub('[^0-9a-zA-Z]+', '', email)
        # login = re.sub('[^0-9a-zA-Z]+', '', login)
        token_path = "/home/{}/secrets/tokens/{}/{}".format(os.environ["USER"], email, login)
        if os.path.isfile(token_path):
            signed_in = True
            user_email, username = open(token_path).read().split(" ")

    return signed_in, username, user_email, email, login


app = Flask(__name__)

@app.route('/signin', methods=["POST"])
def signin():

    email = request.form["email"]
    email_hashed = hashlib.sha256(email.encode('utf-8')).hexdigest()
    user = uuid.uuid1()
    token = uuid.uuid1()
    token_folder = "/home/{}/secrets/tokens/{}".format(os.environ["USER"], email_hashed)
    token_path = "/home/{}/secrets/tokens/{}/{}".format(os.environ["USER"], email_hashed, token)
    try:
        os.makedirs(token_folder)
    except FileExistsError as e:
        pass
    open(token_path, "w").write("{} {}".format(email, user))
    port = 465  # For SSL
    smtp_server = "smtp.gmail.com"
    sender_email = open("/home/{}/secrets/gmail-username".format(os.environ["USER"])).read()  # Enter your address
    receiver_email = email
    password = open("/home/{}/secrets/gmail-password".format(os.environ["USER"])).read()
    message = """\
Subject: Forum signin link

Follow the link below to signin
http://localhost:5000/?email={}&login={}""".format(email_hashed, token, user)

    context = ssl.create_default_context()

    with smtplib.SMTP_SSL(smtp_server, port, context=context) as server:
        server.login(sender_email, password)
        server.sendmail(sender_email, receiver_email, message)
    return render_template('signin.html')


@app.route("/")
def forums():
    signed_in, username, user_email, email_token, login_token = check_signed_in()

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
    response = make_response(render_template("categories.html", signed_in=signed_in, user_email=user_email, categories=categories, threads=thread_list))
    if email_token:
        response.set_cookie("email", email_token)
    if login_token:
        response.set_cookie("login", login_token)
    return response


@app.route("/", methods=["POST"])
def add_forum():
    signed_in, username, user_email, email_token, login_token = check_signed_in()
    cur = conn.cursor()
    cur.execute("""
    insert into categories (title) values (%s) returning id;
    """, (request.form["category"],))
    id = cur.fetchone()[0]
    conn.commit()
    return make_response(redirect("/categories/" + str(id), 302))



@app.route("/categories/<category>")
def threads(category):
    signed_in, username, user_email, email_token, login_token = check_signed_in()
    cur = conn.cursor()
    cur.execute("""
    select * from categories where id = %s;
    """, (category,))
    category_data = cur.fetchmany(1)[0]

    cur.execute("""
    select * from categories;
    """, (category,))
    categories = cur.fetchmany(20)

    cur.execute("""
    select * from threads where category = %s;
    """, (category[0],))
    threads = cur.fetchmany(50)
    return render_template("threads.html", active_category=category_data, signed_in=signed_in, categories=categories, user_email=user_email, category=category_data, threads=threads)

@app.route("/categories/<category>/thread/<thread>", methods=["GET"])
def get_thread(category, thread):
    signed_in, username, user_email, email_token, login_token = check_signed_in()
    cur = conn.cursor()
    cur.execute("""
    select posts.body, posts.author, threads.category from threads inner join posts on posts.thread = threads.id where threads.id = %s;
    """, (thread,))
    posts = cur.fetchmany(50)

    signed_in, username, user_email, email_token, login_token = check_signed_in()
    cur = conn.cursor()
    cur.execute("""
    select threads.id, threads.author, threads.title, threads.category from threads where category = %s;
    """, (category))
    threads = cur.fetchmany(50)

    cur.execute("""
    select * from categories;
    """, (category,))
    categories = cur.fetchmany(50)

    cur.execute("""
    select * from categories where id = %s;
    """, (posts[0][2],))
    category = cur.fetchmany(1)[0]

    cur.execute("""
    select * from threads where id = %s;
    """, (thread,))
    thread = cur.fetchmany(1)[0]
    return render_template("thread.html", active_thread=thread, active_category=category, signed_in=signed_in, categories=categories, user_email=user_email, thread=thread, category=category, posts=posts, threads=threads)


@app.route("/thread", methods=["POST"])
def add_thread():
    signed_in, username, user_email, email_token, login_token = check_signed_in()
    cur = conn.cursor()
    cur.execute("""
    select * from categories where id = %s
    """, (request.form["category"],))
    category_id = cur.fetchone()[0]

    cur.execute("""
    insert into threads (title, category, author) values (%s, %s, %s) returning id;
    """, (request.form["title"], request.form["category"], user_email))
    id = cur.fetchone()[0]
    conn.commit()
    cur.execute("""
    insert into posts (thread, body, author) values (%s, %s, %s) returning id;
    """, (id, request.form["body"], user_email))
    id = cur.fetchone()[0]
    conn.commit()
    target = "/"
    if request.form["category"]:
        target = "/categories/" + str(category_id)
    return redirect(target, 302)

@app.route("/post/<thread>", methods=["POST"])
def add_post(thread):
    signed_in, username, user_email, email_token, login_token = check_signed_in()
    cur = conn.cursor()
    cur.execute("""
    insert into posts (thread, body, author) values (%s, %s, %s) returning id;
    """, (thread, request.form["body"], user_email))
    category = request.form["category"]
    id = cur.fetchone()[0]
    conn.commit()
    return make_response(redirect("/categories/" + category + "/thread/" + thread, 302))


if __name__ == "__main__":
    app.run()
