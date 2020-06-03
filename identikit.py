from flask import Flask
from flask import Response, render_template, redirect, request, make_response, jsonify, session
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
    conn = psycopg2.connect("dbname='forum' user='forum' host='172.17.0.1' password='forum'")
    print(conn)
except Exception as e:
    print("I am unable to connect to the database")
    print(e)


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
app.secret_key=os.environ["admin_pass"]

from flask import Markup

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
                            root.children.append(textNode)
                    else:
                        childrenLookups[path].append(text)
                elif not done[path]:
                    textNode = Element(element, className, childrenLookups[path], attrs)
                    if place == 0:
                        root.children.append(textNode)
                    if previousPath != "":
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
            yield "div.users +h1 =" + user.name
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

@app.route("/identikit", methods=["GET"])
def lookup():
    signed_in, username, user_email, email_token, login_token = check_signed_in()

    return render_template("lookup.html", signed_in=signed_in, user_email=user_email, community_lookup="#PoliticalSide:Left_wing #Government:Small #Taxes:Small #VoluntaryCollectivism:Yes #UniversalBasicIncome:yes")

from functools import reduce
import hashlib

@app.route("/identikit", methods=["POST"])
def find_communities():
    signed_in, username, user_email, email_token, login_token = check_signed_in()
    data = request.form["identikit"]
    session["identikit"] = data
    positions = data.split(" ")

    positions.sort()

    hashed = list(map(lambda x: hashlib.sha256(x.encode('utf-8')).hexdigest(), positions))

    community_id = reduce(lambda previous, current: previous + ":" + current, hashed)

    print(community_id)
    community_link = "communities/" + community_id
    exact_posts = get_exact_posts(community_id)
    posts = get_posts(hashed)

    return render_template("results.html", community_link=community_link, exact_posts=exact_posts, posts=posts, community_id=community_id, signed_in=signed_in, user_email=user_email, community_lookup=data)

def get_exact_posts(community_id):
    cur = conn.cursor()
    categories = cur.execute("""
    select distinct on (identikit_posts.id) body from identikit_posts join identikit_community_posting on identikit_posts.id = identikit_community_posting.post where identikit_community_posting.community = %s
    """, (community_id,))
    new_posts = list(cur.fetchmany(20))
    return new_posts

def get_posts(communities):
    cur = conn.cursor()
    categories = cur.execute("""
    select distinct on (identikit_posts.id) body from identikit_posts join identikit_community_posting on identikit_posts.id = identikit_community_posting.post where identikit_community_posting.community in %s
    """, (tuple(communities),))
    new_posts = list(cur.fetchmany(20))
    return new_posts

@app.route("/communities/<community_id>", methods=["GET"])
def get_community(community_id):
    signed_in, username, user_email, email_token, login_token = check_signed_in()

    communities = community_id.split(":")

    exact_posts = get_exact_posts(community_id)
    posts = get_posts(communities)
    return render_template("results.html", exact_posts=exact_posts, posts=posts, community_id=community_id, signed_in=signed_in, user_email=user_email, community_lookup=session["identikit"])

admin_pass = os.environ["admin_pass"].strip()

def get_admin_posts():
    cur = conn.cursor()
    categories = cur.execute("""
    select distinct on (identikit_posts.id) identikit_posts.id, body, community from identikit_posts join identikit_community_posting on identikit_posts.id = identikit_community_posting.post
    """, ())
    admin_posts = list(cur.fetchmany(5000))
    return admin_posts

@app.route("/posts/" + admin_pass, methods=["GET"])
def view_posts():
    signed_in, username, user_email, email_token, login_token = check_signed_in()
    admin_posts = get_admin_posts()

    return render_template("admin.html", admin_pass=admin_pass, admin_posts=admin_posts, signed_in=signed_in, user_email=user_email, community_lookup="")

@app.route("/delete/" + admin_pass + "/<id>", methods=["GET"])
def delete_post(id):
    signed_in, username, user_email, email_token, login_token = check_signed_in()
    print("Deleting " + id)
    cur = conn.cursor()
    categories = cur.execute("""
    delete from identikit_posts where id = %s
    """, (id,))

    cur = conn.cursor()
    categories = cur.execute("""
    delete from identikit_community_posting where post = %s
    """, (id,))
    conn.commit()
    return redirect("/posts/{}".format(admin_pass))


@app.route("/post", methods=["POST"])
def post_message():
    signed_in, username, user_email, email_token, login_token = check_signed_in()
    community_id = request.form["community_id"]
    print(community_id)

    hashed = community_id.split(":")

    # author, html, javascript, css, id
    cur = conn.cursor()
    cur.execute("""
    insert into identikit_posts (body) values (%s) returning id;
    """, (request.form["message"],))
    post_id = cur.fetchone()

    for community in hashed:
        cur = conn.cursor()
        cur.execute("""
        insert into identikit_community_posting (post, community) values (%s, %s) returning id;
        """, (post_id, community))
        community_post_id = cur.fetchone()
        print("Saved post as", community_post_id)

    cur = conn.cursor()
    cur.execute("""
    insert into identikit_community_posting (post, community) values (%s, %s) returning id;
    """, (post_id, community_id))
    community_post_id = cur.fetchone()
    print("Saved exact post as", community_post_id)

    conn.commit()

    return redirect("communities/{}".format(community_id))

if __name__ == "__main__":
    app.run(port=80)
