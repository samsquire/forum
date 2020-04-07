from flask import Flask
from flask import Response, render_template, redirect, request, make_response
import psycopg2
import os, smtplib, ssl, time
import yaml
import random
import re
import uuid
import hashlib
from pprint import pprint
import collections
from datetime import datetime
import operator
import json

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
    insert into categories (title, published_date) values (%s, %s) returning id;
    """, (request.form["category"], datetime.now()))
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
    select posts.body, posts.author, threads.category, posts.published_date from threads inner join posts on posts.thread = threads.id where threads.id = %s;
    """, (thread,))
    posts = cur.fetchmany(50)
    pprint(cur.description)

    signed_in, username, user_email, email_token, login_token = check_signed_in()
    cur = conn.cursor()
    cur.execute("""
    select threads.id, threads.author, threads.title, threads.category, threads.published_date from threads where category = %s;
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
    insert into threads (title, category, author, published_date) values (%s, %s, %s, %s) returning id;
    """, (request.form["title"], request.form["category"], user_email, datetime.now()))
    id = cur.fetchone()[0]
    conn.commit()

    dt = datetime.now()
    cur.execute("""
    insert into posts (thread, body, author, published_date) values (%s, %s, %s, %s) returning id;
    """, (id, request.form["body"], user_email, dt))
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

class Element():
    def __init__(self, name, className, children=None, attrs={}):
        self.name = name
        self.className = className
        self.attrs = attrs
        if children != None:
            self.children = children

    def root_serialize(self):
        for child in self.children:
            if isinstance(child, str):
                yield child
            else:
                yield from child.serialize()

    def renderAttrs(self):
        html = ""
        for k, v in self.attrs.items():
            html += "{}=\"{}\" ".format(k, v)
        return html

    def serialize(self):
        yield "<" + self.name + " class=\"" + self.className + "\" " + self.renderAttrs() + ">"
        for child in self.children:
            if isinstance(child, str):
                yield child
            else:
                yield from child.serialize()
        yield "</" + self.name + ">"

def createAttrs(element):
    fields = {}
    sides = element.split("(")
    if len(sides) == 2:

        kvs = sides[1].split(")")[0].split(",")

        for kv in kvs:
            splitted = kv.split(":")
            field = splitted[0]
            value = ":".join(splitted[1:])
            fields[field] = value
    return sides[0].replace("-", "").replace("+", "").replace("^", ""), fields

def unflatten(flat_html):
    childrenLookups = {}
    rootChildren = []
    root = Element("div", "", rootChildren)

    done = {}
    parents = {}
    dones = {}
    finished = {}

    for line in flat_html:
        print("------->\"{}\",".format(line))
        textNodes = line.split("=")
        components = textNodes[0].split(" ")
        if components[len(components) - 1] == "":
            components.pop()
        text = None
        if len(textNodes) > 1:
            text = textNodes[1]


        for place, component in enumerate(components):
            subpath = ""
            last_subpath = ""
            for subindex, subcomponent in enumerate(components):
                subpath += components[subindex].replace("-", "").replace("+", "").replace("^", "") + " "
                parents[subpath] = last_subpath
                last_subpath = subpath
                if subpath not in childrenLookups:
                    childrenLookups[subpath] = []
                    done[subpath] = False


        sharedNode = False

        for place, component in enumerate(components):

            path = ""
            nextPath = ""
            previousPath = ""
            for subindex in range(0, place + 1):
                path += components[subindex].replace("-", "").replace("+", "").replace("^", "") + " "
            for subindex in range(0, place + 2):
                if subindex < len(components):
                    nextPath += components[subindex].replace("-", "").replace("+", "").replace("^", "") + " "
            for subindex in range(0, place):
                previousPath += components[subindex].replace("-", "").replace("+", "").replace("^", "") + " "

            subpath = ""

            freshNode = component[0] == "-"
            sharedNode = component[0] == "+"
            parentNode = component[0] == "^"
            if sharedNode:
                childrenLookups[path] = []
                sofar = ""
                found = False
                for subpath in line.split("=")[0].split(" "):
                    corrected = subpath.replace("+", "").replace("-", "").replace("^", "")
                    sofar += corrected + " "
                    if "+" in subpath:
                        found = True
                    if found:
                        childrenLookups[sofar] = []
                        done[sofar] = False
                        print("Emptying ", sofar)

            if parentNode:

                for k, v in childrenLookups.items():
                    if len(k.split(" ")) >= 3:

                        childrenLookups[k] = []

                        # done[k] = False
            if freshNode:
                yield from root.root_serialize()
                finished = {}
                rootChildren.clear()
                subpath = ""
                for k, v in childrenLookups.items():
                    childrenLookups[k] = []
                    done[k] = False


            splitted = component.split("(")
            attrs = splitted[0].split(".")
            element = attrs[0]
            className = ""



            if len(attrs) == 2:
                className = " ".join(attrs[1:])
            end = False
            if path == nextPath:
                end = True

            if end == True:
                component, attrs = createAttrs(component)
                splitted = component.split(".")

                element = splitted[0]
                if len(splitted) > 1:
                    className = " ".join(splitted[1:])
                print(path)
                if text != None:
                    if not done[path]:
                        print(text)
                        print("Filling text @" + path + "]", text)
                        childrenLookups[path].append(text)
                        print(childrenLookups[path])
                        print(element)
                        textNode = Element(element, className, childrenLookups[path], attrs)
                        print(childrenLookups[previousPath])
                        print(previousPath)
                        if previousPath != "":
                            childrenLookups[previousPath].append(textNode)
                        done[path] = True

                        dones[component] = True
                        done[text] = True
                        if place == 0:
                            pass
                            # root.children.append(textNode)
                    else:
                        childrenLookups[path].append(text)
                elif not done[path]:
                    textNode = Element(element, className, childrenLookups[path], attrs)
                    childrenLookups[previousPath].append(textNode)
                    done[path] = True
            elif place == 0 and freshNode:
                # childrenLookups[nextPath] = []

                node = Element(element.replace("-", "").replace("^", "").replace("+", ""), className, childrenLookups[path], {})
                root.children.append(node)
                # childrenLookups[previousPath].append(node)
                done[path] = True
                dones[component] = True
                finished[line] = True
            elif parentNode:
                if done[path] == False:
                    childrenLookups[path] = []
                    root.children.append(Element(element.replace("-", "").replace("+", "").replace("^", ""), className, childrenLookups[path], {}))
                    done[path] = True
                    dones[component] = True
                    childrenLookups[""] = childrenLookups[path]
                    finished[line] = True
            elif sharedNode:
                childrenLookups[path] = []
                childrenLookups[previousPath].append(Element(element.replace("-", "").replace("+", "").replace("^", ""), className, childrenLookups[path], {}))
                done[path] = True
                finished[line] = True

            elif done[path]:

                pass

            else:
                component, attrs = createAttrs(component)

                splitted = component.split(".")
                if len(splitted) > 1:
                    className = " ".join(splitted[1:])
                element = splitted[0]
                childrenLookups[previousPath].append(Element(element, className, childrenLookups[path], attrs))
                done[path] = True
                dones[component] = True
                finished[line] = True



    yield from root.root_serialize()





class User():
    def __init__(self, name):
        self.name = name

    def books(self):
        return [Book("A long journey")]

class Book():
    def __init__(self, name):
        self.name = name
        pass


    def reviews(self):
        return [Review("Review1", 5), Review("Review2", 10)]

class Review():
    def __init__(self, name, score):
        self.title = name
        self.score = score

@app.route("/flat")
def flat():
    def generate():

        users = [User("sam"), User("root")]

        yield "^div.users h1 =Books"
        for user in users:
            yield "div.users h1 =" + user.name
            for book in user.books():
                yield "div.users +div.books h2 =" + book.name
                yield "div.users div.books h3 = Reviews"
                for review in book.reviews():
                    yield "div.users div.books +div.review li =" + review.title
                    yield "div.users div.books div.review li =" + str(review.score)
    return Response(unflatten(generate()), mimetype='text/html')


forms = {
    "people": {
        "fields": [
            {"name": "firstname", "label": "First Name"},
            {"name": "lastname", "label": "Last Name"},
            {"name": "nickname", "label": "Nickname"}
        ]
    }
}

def index_fields(form):
    for index, field in enumerate(form["fields"]):
        field["index"] = index


for k, v in forms.items():
    index_fields(v)


def columns(form, forms):
    column_list = map(operator.itemgetter("name"), forms[form]["fields"])
    return ",".join(column_list)

def placeholders(form, forms):
    text = []
    for item in range(len(forms[form]["fields"])):
        text.append("%s")
    return ",".join(text)


@app.route("/make", methods=["GET"])
def make():
    def generate():
        yield "-div"
        yield "div form(action:/make,method:post) input(type:text,name:name)"
        yield "div form(action:/make,method:post) p = Place a list of fields, space separated"
        yield "div form(action:/make,method:post) textarea(name:fields)"
        yield "div form(action:/make,method:post) button(type:submit) = Submit"
    return Response(unflatten(generate()), mimetype='text/html')


@app.route("/make", methods=["POST"])
def save_form():
    r = re.compile("^[a-zA-Z0-9_\,\s]*$")
    safe_name = r.match(request.form["name"]).group(0)
    safe_fields = r.match(request.form["fields"]).group(0)
    create_statement = """
    create table if not exists {} (
        id SERIAL PRIMARY KEY,
        {}
    );""".format(safe_name, safe_fields)
    fields = list(map(lambda x: x.strip().split(" ")[0], safe_fields.split(",")))
    forms[safe_name] = { "fields": list(map(lambda x: {"name": x, "label": x}, fields)) }
    for k, v in forms.items():
        index_fields(v)

    open("forms.json", "w").write(json.dumps(forms))
    print(fields)
    print(create_statement)
    cur = conn.cursor()
    cur.execute(create_statement)
    return redirect("/make")

@app.route("/view", methods=["POST"])
def view_forms():
    pass

@app.route("/forms/<form>/<id>", methods=["GET"])
def render(form, id):
    forms = json.loads(open("forms.json").read())
    if form not in forms:
        return "Error"

    if id != "new":
        cur = conn.cursor()
        cur.execute("""
        select {} from {} where id = %s;
        """.format(columns(form, forms), form), (id,))
        person = cur.fetchone()



    def generate():
        yield "-div"
        yield "div form(action:/save,method:post) input(type:hidden,name:thing,value:{})".format(form)
        yield "div form(action:/save,method:post) input(type:hidden,name:id,value:{})".format(id)
        for field in forms[form]["fields"]:
            yield "div form(action:/save,method:post) +div label(for:{}) = {}".format(field["name"], field["label"])
            value = ""
            if id != "new":
                value = person[field["index"]]
            yield "div form(action:/save,method:post) div input(type:text,name:{},id:{},value:{})" \
            .format(field["name"], field["name"], value)
        yield "div form(action:/save,method:post) button(type:submit) = Submit"


    return Response(unflatten(generate()), mimetype='text/html')

@app.route("/save", methods=["POST"])
def save():
    forms = json.loads(open("forms.json").read())
    thing = request.form["thing"]
    if thing not in forms:
        return "Error in form"
    id = request.form["id"]
    saved_id = id
    cur = conn.cursor()
    if id == "new":
        values = []
        for field in forms[thing]["fields"]:
            values.append(request.form[field["name"]])
        cur.execute("""
        insert into {} ({}) values ({}) returning id;
        """.format(thing, columns(thing, forms), placeholders(thing, forms)), (*values,))
        saved_id = cur.fetchone()[0]
        conn.commit()
    else:
        values = []
        set_str = []
        for field in forms[thing]["fields"]:
            values.append(request.form[field["name"]])
            set_str.append("{} = %s".format(field["name"]))
        values.append(request.form["id"])
        sql = """
        update {} set {} where id = %s;
        """.format(thing, ",".join(set_str))
        print(sql)
        cur.execute(sql, (*values,))
        conn.commit()
    return redirect("forms/{}/{}".format(thing, saved_id))

class FeedItem():
    def __init__(self, text, link, score, author):
        self.text = text
        self.link = link
        self.score = score
        self.author = author
    def site(self):
        return self.link.replace("http://", "").replace("https://", "")

@app.route("/feed", methods=["GET"])
def feed():
    items = [
        FeedItem("A long story", link="http://google.com", score=50, author="sam"),
        FeedItem("A long story", link="http://yahoo.com", score=70, author="sam")
    ]
    def generate():

        yield "-html head link(rel:stylesheet,href:static/news.css,type:text/css)"
        yield "html body center table.itemlist(bgcolor:#f6f6ef)"
        yield "html body center table.itemlist(bgcolor:#f6f6ef) tbody"
        for index, feed_item in enumerate(items):
            yield "html body center table.itemlist(bgcolor:#f6f6ef) tbody +tr.athing td.title =" + str(index + 1)
            yield "html body center table.itemlist(bgcolor:#f6f6ef) tbody tr.athing +td.title a.storylink(href:{}) =".format(feed_item.link) + feed_item.text
            yield "html body center table.itemlist(bgcolor:#f6f6ef) tbody tr.athing +td.title span.sitebit.comhead = ("
            yield "html body center table.itemlist(bgcolor:#f6f6ef) tbody tr.athing td.title span.sitebit.comhead a(href:{}) = {}".format(feed_item.link, feed_item.site())
            yield "html body center table.itemlist(bgcolor:#f6f6ef) tbody tr.athing td.title span.sitebit.comhead = )"
            yield "html body center table.itemlist(bgcolor:#f6f6ef) tbody +tr td(colspan:1) = "
            yield "html body center table.itemlist(bgcolor:#f6f6ef) tbody tr +td.subtext span.score = " + str(feed_item.score)
            yield "html body center table.itemlist(bgcolor:#f6f6ef) tbody tr td.subtext span.score = points"
            yield "html body center table.itemlist(bgcolor:#f6f6ef) tbody tr td.subtext +span = by"
            yield "html body center table.itemlist(bgcolor:#f6f6ef) tbody tr td.subtext span = " + str(feed_item.author)

            # 260 points by tosh 1 hour ago | hide | 154 comments

    return Response(unflatten(generate()), mimetype='text/html')


if __name__ == "__main__":
    app.run()
