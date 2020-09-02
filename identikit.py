from flask import Flask
from flask import Response, render_template, redirect, request, make_response, jsonify, session
import psycopg2 # type: ignore
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
from collections import defaultdict
import redis
import pickle
import time
import asyncio
from threading import Thread
from subprocess import Popen
import random
from dls.dls_api import app, register_resource, register_host, register_span, initialize_group, configure_tracer, initialize_host, WorkOutput, resources # type: ignore
import uuid
from jaeger_client import Config # type: ignore


try:
    conn = psycopg2.connect("dbname='forum' user='forum' host='172.17.0.1' password='forum'")
    conn.autocommit = True
    print(conn)
except Exception as e:
    print("I am unable to connect to the database")
    print(e)

r = redis.Redis(host='localhost', port=6379, db=0)

def regenerate_site():
    path = os.path.abspath("identikit.py")
    regenerate = Popen(["python3.8", path], env={"admin_pass": "blah", "HOME": os.environ["HOME"], "USER": os.environ["USER"]})
    regenerate.communicate()
    regenerate.wait()

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
        email = re.sub('[^0-9a-zA-Z]+', '', email)
        login = re.sub('[^0-9a-zA-Z]+', '', login)
        token_path = "/home/{}/secrets/tokens/{}/{}".format(os.environ["USER"], email, login)
        if os.path.isfile(token_path):
            signed_in = True
            user_email, username = open(token_path).read().split(" ")

    return signed_in, username, user_email, email, login

from jaeger_client import Config

app = Flask(__name__)
app.jinja_env.cache = {}
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

def get_top_posts():
    print("Getting top posts")
    cur = conn.cursor()
    statement = """
    select identikit_posts.body, identikit_posts.name, identikit_posts.id, identikit_posts.reply_depth,
    identikit_community_posting.community,
    identikit_posts.reply_to, identikit_community_posting.cid, identikit_posts.votes, identikit_posts.parent, identikit_community_posting.cid
    from identikit_posts join identikit_community_posting on identikit_posts.id = identikit_community_posting.post
    where identikit_posts.votes >= 3
    order by identikit_posts.votes desc, identikit_posts.id desc
    """.format()

    cur.execute(statement, ())
    new_posts = list(cur.fetchmany(5000))
    seen = {}
    posts = []
    for post in new_posts:
        if seen.get(post[2]):
            continue
        posts.append(post)
        seen[post[2]] = True

    return posts

@app.route("/", methods=["GET"])
def get_root():
    return redirect("/identikit")

@app.route("/top", methods=["GET"])
def homepage():
    top_posts = get_top_posts()
    identikit = "#PoliticalSide:Left_wing #Government:Small #Taxes:Small #VoluntaryCollectivism:Yes #UniversalBasicIncome:yes"
    return render_template("top.html", community_lookup=identikit, posts=top_posts)

@app.route("/identikit", methods=["GET"])
def lookup():
    signed_in, username, user_email, email_token, login_token = check_signed_in()

    identikit = "#PoliticalSide:Left_wing #Government:Small #Taxes:Small #VoluntaryCollectivism:Yes #UniversalBasicIncome:yes"

    return render_template("lookup.html", signed_in=signed_in, user_email=user_email, community_lookup=identikit)

from functools import reduce
import hashlib

def identikit_to_hash(data):
    positions = data.split(" ")

    if positions == [""]:
        return ""
    positions.sort()
    hashed = list(map(lambda x: hashlib.sha256(x.encode('utf-8')).hexdigest(), positions))
    community_id = reduce(lambda previous, current: previous + ":" + current, hashed)
    return community_id

def get_parent_communities(data, exact_posts):
    communities = data.split(" ")
    communities.sort()
    exact_communities = set([])
    current_exact_community = []
    for community in communities:
        without = list(filter(lambda x: x != community, communities))
        exact_communities.add(identikit_to_hash(" ".join(without)))

    parent_community_posts = get_posts(data, exact_communities)

    exact_posts = exact_posts + parent_community_posts

    return exact_posts

def remove_position(source, identikit):
    raw_communities = []

    for record in identikit.split(" "):
        components = record.split(":")
        raw_name = components[0]
        if len(components) == 2:
            position = components[1]
        else:
            position = ""
        if raw_name in source:
            if position == source[raw_name]:
                raw_communities.append(record)
            else:
                return ()
        else:
            raw_communities.append(raw_name)
    return (identikit, raw_communities)

def jaccard_index(community_a, community_b):
    a = set(community_a)
    b = set(community_b)

    return float("{:.1f}".format(len(a.intersection(b)) / len(a.union(a))))

def compare(a, identikit):
    def do_compare(positions):
        original, raw = positions
        return (original, jaccard_index(a, raw))
    return do_compare

def get_similar_communities(identikit):

    if r.exists("all_communities"):
        community_string = r.get("all_communities")
        other_communities = pickle.loads(community_string)
    else:
        cur = conn.cursor()
        categories = cur.execute("""
        select community, user_name from user_communities
        """, ())
        other_communities = list(cur.fetchmany(5000))
        r.set("all_communities", pickle.dumps(other_communities))

    source_nodes = identikit.split(" ")
    positions = {}
    for node in source_nodes:
        components = node.split(":")
        community_name = components[0]
        if len(components) == 2:
            position = components[1]
        else:
            position = ""
        positions[community_name] = position


    without_positions = filter(lambda x: x != (), map(lambda x: remove_position(positions, x[0]), other_communities))
    identikit_community = identikit.split(" ")

    similarities = list(map(compare(identikit_community, identikit), without_positions))
    similarities.sort(key=lambda x: x[1], reverse=True)
    return similarities

#@app.route("/reply/<id>/<cid>/<community>", methods=["GET"])
def reply_post(id, cid, community):
    cur = conn.cursor()
    categories = cur.execute("""
    select id from user_communities where id = %s
    """, (cid, ))
    fetched_community = cur.fetchone()
    cid = fetched_community[0]

    cur = conn.cursor()
    categories = cur.execute("""
    select body, name, id from identikit_posts where id = %s
    """, (id, ))
    post = list(cur.fetchone())
    return render_template("reply.html", post=post, cid=cid, community=community)

@app.route("/reply/<pid>/<comment>", methods=["GET"])
def reply_comment(pid, comment):

    cur = conn.cursor()
    categories = cur.execute("""
    select body, name, id from post_comments where id = %s
    """, (comment, ))
    post = list(cur.fetchone())
    return render_template("reply.html", post=post, pid=pid, comment=post[2])


def get_parent_post(table, start):
    current = start
    parent = 0

    while parent is not None:
        cur = conn.cursor()
        cur.execute("""
        select id, parent from {} where id = %s
        """.format(table), (current, ))
        post = cur.fetchone()
        parent = post[1]
        current = parent

    return post[0]

@app.route("/reply/<id>/<cid>", methods=["POST"])
def submit_reply(id, cid, community):
    cur = conn.cursor()
    cur.execute("""
    select id from user_communities where id = %s
    """, (cid, ))
    community_fetched = cur.fetchone()
    cid = community_fetched[0]

    parent_post = get_parent_post("identikit_posts", id)
    print("Parent post is {}".format(parent_post))

    cur = conn.cursor()
    cur.execute("""
    select reply_depth from identikit_posts where id = %s
    """, (id, ))
    reply_post = list(cur.fetchone())
    reply_depth = reply_post[0] + 1

    cur = conn.cursor()
    cur.execute("""
    insert into identikit_posts (body, reply_depth, reply_to, name, votes, parent) values (%s, %s, %s, %s, %s, %s) returning id
    """, (request.form["message"], reply_depth, id, session.get("name", "Anonymous"), 0, parent_post))
    reply_post = list(cur.fetchone())

    cur = conn.cursor()
    cur.execute("""
    insert into post_replies (parent, post) values (%s, %s) returning id
    """, (parent_post, reply_post[0]))
    post_replies_response = list(cur.fetchone())

    cur = conn.cursor()
    cur.execute("""
    insert into identikit_community_posting (post, community, cid) values (%s, %s, %s) returning id;
    """, (reply_post[0], community, cid))
    community_post_id = cur.fetchone()
    print("Saved post as", reply_post[0])

    conn.commit()
    regenerate_site()

    return redirect("http://lonely-people.com/communities/{}".format(cid))

def get_sort_options():
    return [
    ("id-desc", "Newest first", False),
    ("id-asc", "Oldest first", False),
    ("votes-asc", "Lowest first", False),
    ("votes-desc", "Highest first", False)
    ]

#
#     if session.get("sort") and request.form.get("sort") == None:
    #     sort_mode = session["sort"]
    # else:
    #     sort_mode = request.form.get("sort", "id-asc")
    #     session["sort"] = sort_mode


def get_sort_mode(sort_mode):
    def update_sort(sort_option):
        if sort_option[0] == sort_mode:
            return (sort_option[0], sort_option[1], True)
        else:
            return (sort_option[0], sort_option[1], False)
    sort_options = map(update_sort, get_sort_options())
    return sort_mode, sort_options

@app.route("/identikit", methods=["POST"])
def find_communities():
    signed_in, username, user_email, email_token, login_token = check_signed_in()
    data = request.form["identikit"]
    if data == "":
        return redirect("/identikit")
    session["identikit"] = data
    community_id = identikit_to_hash(data)
    hashed = community_id.split(":")
    community_link, cid = get_or_create_community(data, community_id)

    return redirect("http://lonely-people.com/communities/" + str(cid))

def get_or_create_community(identikit, community_id):
    cur = conn.cursor()
    categories = cur.execute("""
    select user_name, id from user_communities where community = %s
    """, (identikit,))
    duplicate = cur.fetchone()

    if duplicate:
        cid = duplicate[1]
        community_link = "/communities/{}".format(cid)
    else:
        cur = conn.cursor()
        categories = cur.execute("""
        insert into user_communities (community, user_name) values (%s, %s) returning id
        """, (identikit, session.get("name", "Anonymous"), ))
        new_community = cur.fetchone()
        cid = new_community[0]
        community_link = "/communities/{}".format(cid)
        conn.commit()
        r.delete("all_communities")

        regenerate_site()

    return community_link, cid

def get_exact_posts(cid: str, community_id:str, sort="votes-desc"):
    redis_key = "community_posts_{}_{}".format(cid, sort)

    c = Cache(redis_key)
    if c.exists():
        new_posts = c.lookup()
        return new_posts
    else:
        sort_field, sort_order = sort.split("-")

        if sort_field == "votes":
            real_sort_field = "identikit_posts.votes"
        if sort_field == "id":
            real_sort_field = "identikit_posts.id"
        if sort_order == "desc":
            real_sort_order = "desc"
        elif sort_order == "asc":
            real_sort_order = "asc"

        print("Getting exact posts by " + community_id)
        cur = conn.cursor()
        statement = """
        select identikit_posts.body, identikit_posts.name, identikit_posts.id, identikit_posts.reply_depth, identikit_community_posting.community,
        identikit_posts.reply_to, identikit_community_posting.cid, identikit_posts.votes, identikit_posts.parent, post_comment_counts.count
        from identikit_posts join identikit_community_posting on identikit_posts.id = identikit_community_posting.post
        full outer join post_comment_counts on post_comment_counts.post = identikit_posts.id
        where identikit_community_posting.community = %s
        order by {} {}
        """.format(real_sort_field, real_sort_order)
        print(cur.mogrify(statement, (community_id,)).decode('utf-8'))
        cur.execute(statement, (community_id,))
        new_posts = list(cur.fetchmany(5000))

        print("Fresh fetch")
        new_posts = reorder_posts_by_reply(new_posts)
        c.save(new_posts)
        for post in new_posts:
            pid = post[2]
            print("Depending on {}".format(pid))
            c.add_dependency("posts_cache_{}".format(pid))
        redis_key = "community_posts_{}".format(cid)
        c.add_dependency(redis_key)

    return new_posts

ID = 2
REPLY_TO = 4

def append_children(post, added, index, child_posts):
    returned_posts = []
    for child_id in child_posts[post[ID]]:
        print("Found child post " + str(child_id))
        if child_id not in added:
            returned_posts.append(index[child_id])
            added.append(child_id)
            returned_posts = returned_posts + append_children(index[child_id], added, index, child_posts)
        else:
            print("Already seen")

    return returned_posts

def reorder_posts_by_reply(posts):

    returned_posts = []
    index = {}
    child_posts = defaultdict(list)
    for post in posts:
        index[post[ID]] = post
        child_posts[post[REPLY_TO]].append(post[ID])


    added = []
    returned_posts = []
    for post in posts:
        if post[ID] not in added:
            added.append(post[ID])
            returned_posts.append(index[post[ID]])
            returned_posts = returned_posts + append_children(post, added, index, child_posts)
    return returned_posts

class Cache():
    def __init__(self, key=None):
        self.key = key

    def exists(self):
        return r.exists(self.key)

    def lookup(self):
        posts_str = r.get(self.key)
        new_posts = pickle.loads(posts_str)
        return new_posts

    def save(self, item):
        posts_str = pickle.dumps(item)
        r.set(self.key, posts_str)

    def add_dependency(self, dependent):
        r.sadd(dependent, self.key)

    def invalidate_dependents(self, community):
        for member in r.smembers(community):
            print("Deleting " + str(member))
            r.delete(member)

def get_posts(community_id, communities):
    redis_key = "posts_" + community_id
    c = Cache(redis_key)
    if c.exists():
        return c.lookup()
    else:
        cur = conn.cursor()
        statement = """
        select distinct on (identikit_posts.id) body, identikit_posts.name, identikit_posts.id, identikit_posts.reply_depth, identikit_community_posting.community,
        identikit_posts.reply_to, identikit_community_posting.cid, identikit_posts.votes
        from identikit_posts join identikit_community_posting on identikit_posts.id = identikit_community_posting.post where identikit_community_posting.community in %s
        """
        print(cur.mogrify(statement, (tuple(communities),)).decode('utf-8'))
        cur.execute(statement, (tuple(communities),))
        new_posts = list(cur.fetchmany(5000))
        new_posts = reorder_posts_by_reply(new_posts)
        c.save(new_posts)

        # this is a cache index
        # if any of dependencies change, we have to invalidate the cache
        for community in communities:
            for subcommunity in community.split(":"):
                print("Adding community " + subcommunity)
                c.add_dependency(subcommunity)

    return new_posts

def get_comments(post_id, sort):
    sort_field, sort_order = sort.split("-")

    if sort_field == "votes":
        real_sort_field = "post_comments.votes"
    if sort_field == "id":
        real_sort_field = "post_comments.id"
    if sort_order == "desc":
        real_sort_order = "desc"
    elif sort_order == "asc":
        real_sort_order = "asc"


    cur = conn.cursor()
    cur.execute("""
    select body, post_comments.name, post_comments.id, post_comments.reply_depth,
    post_comments.reply_to, post_comments.votes
    from post_comments where post_comments.post = %s
    order by {} {}
    """.format(real_sort_field, real_sort_order), (post_id,))
    new_comments = list(cur.fetchmany(5000))

    print(new_comments)

    new_posts = reorder_posts_by_reply(new_comments)

    return new_posts

@app.route("/articles/<pid>", methods=["GET", "POST"])
def load_comments_nosort(pid):
    sort = request.form.get("sort", "id-asc")
    return redirect("http://lonely-people.com/articles/{}/{}".format(pid, sort))

@app.route("/articles/<pid>/<sort>/", methods=["GET", "POST"])
def load_comments(pid, sort):
    cur = conn.cursor()
    cur.execute("""
    select body, name, votes from identikit_posts where id = %s
    """, (pid,))
    post = cur.fetchone()

    sort_mode, sort_options = get_sort_mode(sort)

    posts = get_comments(pid, sort_mode)
    return render_template("comments.html", sort_options=sort_options, posts=posts, post=post, pid=pid)

@app.route("/comments/<pid>/<comment>", methods=["POST"])
def receive_comment(pid, comment):
    if comment == "new":
        parent_post = None
        reply_depth = 0
        reply_to = None
    else:
        parent_post = get_parent_post("post_comments", comment)
        cur = conn.cursor()
        cur.execute("""
        select reply_depth from post_comments where id = %s
        """, (comment, ))
        reply_post = list(cur.fetchone())
        reply_depth = reply_post[0] + 1
        reply_to = comment

    print("Parent post is {}".format(parent_post))

    cur = conn.cursor()
    cur.execute("""
    insert into post_comments (body, reply_depth, reply_to, name, votes, parent, post) values (%s, %s, %s, %s, %s, %s, %s) returning id
    """, (request.form["message"], reply_depth, reply_to, session.get("name", "Anonymous"), 0, parent_post, pid,))
    reply_post = list(cur.fetchone())
    conn.commit()

    cur = conn.cursor()
    cur.execute("""
    insert into comment_replies (parent, post) values (%s, %s) returning id
    """, (parent_post, reply_post[0]))
    post_replies_response = list(cur.fetchone())

    cur = conn.cursor()
    cur.execute("""
    select count from post_comment_counts where post = %s
    """, (pid,))
    count_response = cur.fetchone()

    if count_response == None:
        cur = conn.cursor()
        cur.execute("""
        insert into post_comment_counts (post, count) values (%s, 1)
        """, (pid,))

    else:
        count = count_response[0]
        cur = conn.cursor()
        cur.execute("""
        update post_comment_counts set count = %s where post = %s
        """, (count + 1, pid,))
    conn.commit()

    c = Cache()
    redis_key = "posts_cache_{}".format(pid)
    c.invalidate_dependents(redis_key)
    regenerate_site()


    return redirect("http://lonely-people.com/articles/{}".format(pid))

class Timer():
    def __init__(self):
        self.timers = []
        self.stack = []

    def reset(self):
        self.stack.clear()
        self.timers.clear()

    def start(self):
        self.stack.append(time.time())

    def stop(self, reason):
        duration = (time.time() - self.stack.pop()) * 1000
        self.timers.append((duration, reason))

config = Config(
        config={ # usually read from some yaml config
            'sampler': {
                'type': 'const',
                'param': 1,
            },
            'logging': True,
        },
        service_name='identikit',
        validate=True
    )
# this call also sets opentracing.tracer
configure_tracer(config)



def get_parents(r, outputs):

    if len(outputs.communities) > 1:
        outputs.exact_posts = get_parent_communities(outputs.identikit, outputs.exact_posts)


def get_c(r, outputs):

    conn = r.conn
    cur = conn.cursor()
    cur.execute("""
    select community from user_communities where id = %s
    """, (outputs.cid,))
    community = cur.fetchone()

    outputs.identikit = community[0]
    outputs.community_id = identikit_to_hash(community[0])
    outputs.communities = outputs.community_id.split(":")



def get_e(r, outputs):

    outputs.exact_posts = get_exact_posts(outputs.cid, outputs.community_id, outputs.sort)


def get_p(r, outputs):

    outputs.posts = get_posts(outputs.community_id, outputs.communities)


def get_similar(r, outputs):

    outputs.similar_communities = get_similar_communities(outputs.identikit)


def get_or_create(r, outputs):

    outputs.community_link, cid = get_or_create_community(outputs.identikit, outputs.community_id)


@app.route("/communities/<cid>/", methods=["GET", "POST"])
def get_community_nosort(cid):
    sort = request.form.get("sort", "id-asc")
    return redirect("http://lonely-people.com/communities/{}/{}".format(cid, sort))


def create_timer(resources, host):
    resources.t = Timer()

def connect_to_database(resources, host):
    resources.conn = psycopg2.connect("dbname='forum' user='forum' host='" + host + "' password='forum'")

def connect_to_redis(resources, host):
    resources.r = redis.Redis(host=host, port=6379, db=0)

register_host(name="app", port=9006, host="localhost", has=["communities database", "redis cache"])

register_resource("communities database", connect_to_database)
register_resource("redis cache", connect_to_redis)
register_resource("timer", create_timer)


register_span("get communities",
    "get exact posts",
    ["get community", "@communities database"],
    get_e)
register_span("get communities",
    "get partial posts",
    ["get community", "@communities database"],
    get_p)
register_span("get communities",
    "get parents",
    ["get community", "get exact posts", "@communities database"],
    get_parents)
register_span("get communities",
    "get or create",
    ["get community", "@communities database"],
    get_or_create)
register_span("get communities",
    "get_similar",
    ["get community", "@communities database"],
    get_similar)
register_span("get communities",
    "get community",
    ["@communities database"],
    get_c)

context = initialize_group("get communities", "app")

initialize_host(context)

@app.route("/communities/<cid>/<sort>/", methods=["GET", "POST"])
def get_community(cid, sort):
    work_output = WorkOutput()
    signed_in, username, user_email, email_token, login_token = check_signed_in()
    work_output.signed_in = signed_in
    work_output.user_email = user_email

    work_output.cid = cid
    work_output.sort = sort

    work_output, executed = context.run_group(work_output, None)
    print("\n".join(work_output.diagram))
    print(work_output.stats)
    work_output.receiver_list = work_output.identikit.split(" ")

    sort_mode, sort_options = get_sort_mode(sort)
    response = render_template("results.html", sort_options=sort_options, cid=work_output.cid, community_link=work_output.community_link,
    similar_communities=work_output.similar_communities, receiver_list=work_output.receiver_list, exact_posts=work_output.exact_posts,
    posts=work_output.posts, community_id=work_output.community_id, signed_in=work_output.signed_in, user_email=work_output.user_email,
    community_lookup=work_output.identikit, timers=context.r.t.timers)
    # context.r.t.reset()
    return response

admin_pass = os.environ["admin_pass"].strip()

def get_admin_posts():
    cur = conn.cursor()
    categories = cur.execute("""
    select distinct on (identikit_posts.id) identikit_posts.id, body, community, identikit_posts.name from identikit_posts
    join identikit_community_posting on identikit_posts.id = identikit_community_posting.post
    """, ())
    admin_posts = list(cur.fetchmany(5000))
    return admin_posts

@app.route("/adminlogout/" + admin_pass, methods=["GET"])
def admin_logout():
    session["admin"] = False
    return redirect("/identikit")

@app.route("/set_name/", methods=["GET"])
def set_name():
    return render_template("set_name.html", name=session.get("name", "Anonymous"))

@app.route("/set_name/", methods=["POST"])
def submit_name():
    session["name"] = request.form["name"]
    return redirect("/identikit")

@app.route("/posts/" + admin_pass, methods=["GET"])
def view_posts():
    signed_in, username, user_email, email_token, login_token = check_signed_in()
    admin_posts = get_admin_posts()
    session["admin"] = True
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

@app.route("/upvote/<id>/<cid>", methods=["POST"])
def upvote_post(id, cid):

    return_page = request.args.get("returnpage")

    cur = conn.cursor()
    statement = """
    select ip, post from post_votes where post = %s and ip = %s
    """
    print(cur.mogrify(statement, (id, request.remote_addr)))
    categories = cur.execute(statement, (id, request.remote_addr))
    voter_record = cur.fetchone()

    c = Cache()
    c.invalidate_dependents("community_posts_{}".format(cid))
    c.invalidate_dependents("posts_{}".format(cid))

    r.delete("posts_{}".format(cid))
    print(voter_record)
    if voter_record == None:
        cur = conn.cursor()
        categories = cur.execute("""
        select votes from identikit_posts where id = %s
        """, (id,))
        identikit_post = cur.fetchone()
        if identikit_post == None:
            new_vote_count = 1
        else:
            new_vote_count = identikit_post[0] + 1

        cur = conn.cursor()
        categories = cur.execute("""
        update identikit_posts set votes = %s where id = %s
        """, (new_vote_count, id,))

        cur = conn.cursor()
        categories = cur.execute("""
        insert into post_votes (ip, post) values (%s, %s)
        """, (request.remote_addr, id,))
        conn.commit()
        regenerate_site()
    if return_page == "top":
        return redirect("/")

    return redirect("http://lonely-people.com/communities/{}".format(cid))

@app.route("/comment-upvote/<pid>/<comment>", methods=["POST"])
def upvote_comment(pid, comment):

    cur = conn.cursor()
    categories = cur.execute("""
    select ip, post from comment_votes where post = %s and ip = %s
    """, (comment, request.remote_addr))
    voter_record = cur.fetchone()

    if voter_record == None:
        cur = conn.cursor()
        cur.execute("""
        select votes from post_comments where id = %s
        """, (comment,))
        identikit_post = cur.fetchone()
        if identikit_post == None:
            new_vote_count = 1
        else:
            new_vote_count = identikit_post[0] + 1

        cur = conn.cursor()
        categories = cur.execute("""
        update post_comments set votes = %s where id = %s
        """, (new_vote_count, comment,))

        cur = conn.cursor()
        categories = cur.execute("""
        insert into comment_votes (ip, post) values (%s, %s)
        """, (request.remote_addr, comment,))
        conn.commit()
        regenerate_site()
    return redirect("/articles/{}".format(pid))


@app.route("/post", methods=["POST"])
def post_message():
    signed_in, username, user_email, email_token, login_token = check_signed_in()

    receivers = request.form.getlist('receivers')
    print("Receivers is", receivers)
    identikit =  " ".join(receivers)
    print("identikit is [{}]".format(identikit))
    print("Message will also be received by " + identikit)
    community_id = identikit_to_hash(identikit)
    cid = request.form["cid"]

    # need to invalidate caches for each community that we are posting
    c = Cache()
    for community_hash in community_id.split(":"):
        c.invalidate_dependents(community_hash)

    redis_key = "posts_" + identikit
    c = Cache(redis_key)
    c.invalidate_dependents(redis_key)

    r.delete(redis_key)

    redis_key = "community_posts_" + cid
    c.invalidate_dependents(redis_key)

    print("Deleting key " + redis_key)
    r.delete(redis_key)

    hashed = community_id.split(":")
    if hashed == [""]:
        hashed = []

    if "name" in session:
        username = session["name"]
    else:
        username = "Anonymous"

    # author, html, javascript, css, id
    cur = conn.cursor()
    cur.execute("""
    insert into identikit_posts (body, name, reply_depth, reply_to, votes) values (%s, %s, %s, %s, %s) returning id;
    """, (request.form["message"], username, 0, None, 0))
    post_id = cur.fetchone()

    print("Hashed is", hashed)

    for receiver, community in zip(receivers, hashed):
        cur = conn.cursor()
        community_link, item_cid = get_or_create_community(receiver, community)
        cur.execute("""
        insert into identikit_community_posting (post, community, cid) values (%s, %s, %s) returning id;
        """, (post_id, community, item_cid))
        community_post_id = cur.fetchone()
        print("Saved post as", community_post_id)

    cur = conn.cursor()
    cur.execute("""
    insert into identikit_community_posting (post, community, cid) values (%s, %s, %s) returning id;
    """, (post_id, request.form["community_id"], cid))
    community_post_id = cur.fetchone()
    print("Saved exact post as", community_post_id)

    cur = conn.cursor()
    cur.execute("""
    insert into post_comment_counts (post, count) values (%s, 0)
    """, (post_id,))

    conn.commit()
    regenerate_site()

    return redirect("http://lonely-people.com/communities/{}/".format(request.form["cid"]))

class Question():
    def __init__(self, id, short, text, answers):
        self.text = text
        self.id = id
        self.short = short
        self.answers = answers

class Answer():
    def __init__(self, id, text):
        self.id = id
        self.text = text
        self.short = text.replace(" ", "_")


def get_questions():
    cur = conn.cursor()
    categories = cur.execute("""
    select questions.id, answers.id, answers.answer from questions inner join answers on questions.id = answers.question;
    """, ())
    answers = list(cur.fetchmany(5000))
    index = defaultdict(list)

    for answer in answers:
        index[answer[0]].append(Answer(answer[1], answer[2]))

    cur = conn.cursor()
    categories = cur.execute("""
    select questions.id, questions.short, questions.question from questions;
    """, ())
    questions = list(cur.fetchmany(5000))

    questions_list = []
    for question in questions:
        questions_list.append(Question(question[0], question[1], question[2], index[question[0]]))
    return questions_list

@app.route("/questionnaire", methods=["GET"])
def questionnaire():
    signed_in, username, user_email, email_token, login_token = check_signed_in()

    questions_list = get_questions()

    return render_template("questionnaire.html", questions=questions_list, signed_in=signed_in, user_email=user_email)

@app.route("/view", methods=["GET"])
def view_questions():
    signed_in, username, user_email, email_token, login_token = check_signed_in()

    cur = conn.cursor()
    cur.execute("""
    select questions.id, questions.question, questions.short from questions
    """, (id,))
    questions = cur.fetchmany(5000)

    question_list = []
    for question in questions:
        question_list.append(Question(question[0], question[2], question[1], []))

    if "admin" in session:
        deletable_questions = session["admin"]
    else:
        deletable_questions = False

    return render_template("create.html", deletable_questions=deletable_questions, questions=question_list, signed_in=signed_in, user_email=user_email)

@app.route("/delete/<id>", methods=["POST"])
def delete_question(id):
    cur = conn.cursor()
    cur.execute("""
    delete from answers where question = %s
    """, (id,))

    cur = conn.cursor()
    cur.execute("""
    delete from questions where id = %s
    """, (id,))

    conn.commit()
    return redirect("/view")

@app.route("/add/<id>", methods=["GET"])
def add_question(id):
    signed_in, username, user_email, email_token, login_token = check_signed_in()

    if id == "new":
        question_text = ""
        question_id = ""
        answer_list = []
        in_edit_mode = False
        question_number = "new"
    else:
        cur = conn.cursor()
        cur.execute("""
        select questions.id, questions.question, questions.short from questions where id = %s
        """, (id,))
        questions = cur.fetchone()

        question_text = questions[1]
        question_id = questions[2]

        cur = conn.cursor()
        cur.execute("""
        select id, answer from answers where question = %s
        """, (id,))
        answers = cur.fetchmany(5000)
        answer_list = []
        for answer in answers:
            answer_list.append(Answer(answer[0], answer[1]))
        in_edit_mode = True
        question_number = id

    return render_template("add.html", question_number=question_number, id=id, in_edit_mode=in_edit_mode, question_id=question_id, question_text=question_text, answers=answer_list, signed_in=signed_in, user_email=user_email)


@app.route("/add/<id>", methods=["POST"])
def submit_question(id):
    signed_in, username, user_email, email_token, login_token = check_signed_in()
    if id == "new":
        cur = conn.cursor()
        categories = cur.execute("""
        insert into questions (short, question) values (%s, %s) returning id
        """, (request.form["question_id"], request.form["question_text"],))
        created_id = list(cur.fetchone())
    else:
        cur = conn.cursor()
        categories = cur.execute("""
        update questions set short = %s, question = %s where id = %s returning id
        """, (request.form["question_id"], request.form["question_text"], id,))
        created_id = list(cur.fetchone())

    print(created_id)
    conn.commit()
    regenerate_site()
    return redirect("http://lonely-people.com/add/{}".format(created_id[0]))

@app.route("/questions/<qid>/<id>", methods=["GET"])
def view_question(qid, id):
    signed_in, username, user_email, email_token, login_token = check_signed_in()

    cur = conn.cursor()
    categories = cur.execute("""
    select id from questions where id = %s
    """, (qid,))
    question = cur.fetchone()
    question_id = question[0]

    if id == "new":
        answer_text = ""
        in_edit_mode = False
        answer_id = 0
        answer_number = "new"
    else:
        cur = conn.cursor()
        categories = cur.execute("""
        select answer, id from answers where question = %s and id = %s
        """, (qid, id,))
        answer = cur.fetchone()
        answer_text = answer[0]
        answer_id = answer[1]
        in_edit_mode = True
        answer_number = answer_id

    return render_template("answer.html", answer_number=answer_number, in_edit_mode=in_edit_mode, qid=question_id,
    id=answer_id, answer_text=answer_text, signed_in=signed_in, user_email=user_email)

@app.route("/questions/<qid>/<id>", methods=["POST"])
def save_question(qid, id):
    signed_in, username, user_email, email_token, login_token = check_signed_in()
    if id == "new":
        cur = conn.cursor()
        categories = cur.execute("""
        insert into answers (answer, question) values (%s, %s) returning id
        """, (request.form["answer_text"], qid))
        answer = list(cur.fetchone())
        answer_id = answer[0]
    else:
        cur = conn.cursor()
        categories = cur.execute("""
        update answers set answer = %s where id = %s returning id
        """, (request.form["answer_text"], id,))
        answer = list(cur.fetchone())
        answer_text = answer[0]

    conn.commit()
    regenerate_site()
    return redirect("http://lonely-people.com/add/{}".format(qid))

@app.route("/delete_answer/<qid>/<id>", methods=["POST"])
def delete_answer(qid, id):
    cur = conn.cursor()
    categories = cur.execute("""
    delete from answers where id = %s
    """, (id,))
    conn.commit()
    regenerate_site()
    return redirect("http://lonely-people.com/add/" + qid)

@app.route("/questionnaire", methods=["POST"])
def questionnaire_to_community():
    signed_in, username, user_email, email_token, login_token = check_signed_in()
    questions_list = get_questions()
    identikit = ""

    for question in questions_list:
        identikit += "#{}:{} ".format(question.short, request.form[question.short].replace(" ", "_"))
    identikit = identikit[:-1]
    session["identikit"] = identikit
    community_id = identikit_to_hash(identikit)
    hashed = community_id.split(":")

    sort_mode, sort_options = get_sort_mode("id-asc")


    community_link, cid = get_or_create_community(identikit, community_id)
    exact_posts = get_exact_posts(cid, community_id, sort_mode)
    posts = get_posts(community_id, hashed)

    if len(hashed) > 1:
        exact_posts = get_parent_communities(identikit, exact_posts)
    receiver_list = identikit.split(" ")

    similar_communities = get_similar_communities(identikit)
    regenerate_site()
    return redirect("http://lonely-people.com/communities/{}".format(cid))

@app.route("/login", methods=["GET"])
def login():
    return render_template("login.html")

def validate_session(session_id, user_id):
    static = os.environ.get("STATIC_MODE", "dynamic") == "static"
    if static:
        session_user = request.headers["Override-User"]
        if session_user != user_id:
            return redirect("http://lonely-people.com/login"), None
    else:
        print("Validating user's request")
        session_ip = r.get(session_id)
        if session_ip == None:
            # user has timed out or logged out already
            return redirect("http://lonely-people.com/login"), None
        session_ip = session_ip.decode('utf-8')
        session_user = r.get(session_id + "_user_id")
        if session_user == None:
            return redirect("http://lonely-people.com/login"), None
        session_user = session_user.decode('utf-8')
        if request.headers["X-Forwarded-For"] != session_ip or session_user != user_id:
            return redirect("http://lonely-people.com/login"), None

    return None, session_user


@app.route("/private/<session_id>/<user_id>/dashboard", methods=["GET"])
def dashboard(session_id, user_id):

    error, session_user = validate_session(session_id, user_id)
    if error:
        return error

    print(session_user)
    # Generate page as user

    return render_template("dashboard.html", user_id=session_user)

@app.route("/private/<session_id>/<user_id>/profile", methods=["GET"])
def profile(session_id, user_id):

    error, session_user = validate_session(session_id, user_id)
    if error:
        return error

    print(session_user)
    # Generate page as user

    return render_template("profile.html", user_id=session_user)


@app.route("/csrf", methods=["POST"])
def csrf():
    if "csrf_token" in session:
        csrf_token = session["csrf_token"]
    else:
        csrf_token = uuid.uuid4().hex
        session["csrf_token"] = csrf_token
    return csrf_token

@app.route("/login", methods=["POST"])
def login_request():
    if request.form["_csrf_token"] != session["csrf_token"]:
        print("Invalid csrf token")
        return redirect("http://lonely-people.com/login")
    elif request.form["_csrf_token"] == session["csrf_token"]:
        print("Generating new csrf token for user")
        csrf_token = uuid.uuid4().hex
        session["csrf_token"] = csrf_token

    if request.form["username"] == "hello" and request.form["password"] == "world":
        session_id = uuid.uuid4().hex
        user_id = "1"
        r.set(session_id, request.headers["X-Forwarded-For"])
        user_key = "{}_{}".format(session_id, "user_id")
        r.set(user_key, user_id)
        r.expire(session_id, 3600)
        r.expire(user_key, 3600)
        os.symlink(os.path.abspath("privatesite/".format()), os.path.abspath("site/private/{}".format(session_id)))
        return redirect("http://lonely-people.com/private/{}/{}/dashboard".format(session_id, user_id))
    else:
        return redirect("http://lonely-people.com/login")

@app.route("/private/<session_id>/<user_id>/logout", methods=["POST"])
def logout(session_id, user_id):
    error, session_user = validate_session(session_id, user_id)
    print(error)
    if error:
        return error
    print("Logging out user")
    r.delete(session_id)
    r.delete(session_id + "_user_id")

    return redirect("http://lonely-people.com/logout")

@app.route("/logout", methods=["GET"])
def logged_out():
    return render_template("logout.html")

@app.route("/auth", methods=["GET"])
def authorise_request():
    # headers_file = open("headers", "w")
    # headers_file.write(str(request.headers))
    request_uri = request.headers["X-Original-Uri"]
    components = request_uri.split("/")
    session_id = components[2]
    session_id = str(session_id)
    user_id = components[3]
    # headers_file.write(session_id + "\n")

    if r.exists(session_id):
        fetched_session_id = r.get(session_id).decode('utf-8')
        fetched_user_id = r.get(session_id + "_user_id").decode('utf-8')
        if request.headers["X-Request-Address"] == fetched_session_id and fetched_user_id == user_id:
            # headers_file.write("\nRequest address matches session")
            status_code = 200
        else:
            # headers_file.write(request.headers["X-Request-Address"] + "\n")
            # headers_file.write(fetched_session_id + "\n")
            # headers_file.write("\nRequest address does not match session")
            status_code = 401
    else:
        status_code = 401
    # headers_file.close()
    return make_response("", status_code)

import os, pwd, grp

def drop_privileges(uid_name='nobody', gid_name='nogroup'):
    if os.getuid() != 0:
        # We're not root so, like, whatever dude
        return

    # Get the uid/gid from the name
    running_uid = pwd.getpwnam(uid_name).pw_uid
    running_gid = grp.getgrnam(gid_name).gr_gid

    # Remove group privileges
    os.setgroups([])

    # Try setting the new uid/gid
    os.setgid(running_gid)
    os.setuid(running_uid)

    # Ensure a very conservative umask
    os.umask(0o22)

if __name__ == "__main__":
    import requests
    gen_user = os.environ.get("GEN_USER", "sam")
    print("Dropping rights to {}".format(gen_user))
    drop_privileges(uid_name=gen_user)

    for folder in ["communities", "articles", "questionnaire", "questions", "top", "view"]:
        delete = Popen(["rm", "-rf", "site/{}".format(folder)])
        delete.communicate()
        delete.wait()
    delete = Popen(["rm", "-rf", "privatesite"])
    delete.communicate()
    delete.wait()
    print(delete.returncode)

    def save_url(url: str, override_path:str=None):
        beginning, path = url.split("http://localhost:85/")
        print(path)
        try:
            os.makedirs("site/{}".format(path))
        except:
            pass
        print("Saving {}".format(path))
        response = requests.get(url)
        print(response.status_code)
        if response.status_code != 200 and response.status_code != 301:
            print("error")
        path = "site/{}/index.html".format(path)
        if override_path:
            path = "site/" + override_path + "/index.html"
        open(path, "w").write(response.content.decode('utf-8'))

    response = requests.get("http://localhost:85/static/jquery-3.5.1.min.js")
    path = "site/static/"
    try:
        os.makedirs(path)
    except:
        pass
    print("Saving {}".format(path))
    open(path + "jquery-3.5.1.min.js", "w").write(response.content.decode('utf-8'))

    response = requests.get("http://localhost:85/static/csrf.js")
    path = "site/static/"
    try:
        os.makedirs(path)
    except:
        pass
    print("Saving {}".format(path))
    open(path + "csrf.js", "w").write(response.content.decode('utf-8'))


    from argparse import ArgumentParser
    parser = ArgumentParser()
    parser.add_argument("--path")
    args = parser.parse_args()
    requested_url = args.path



    cur = conn.cursor()
    categories = cur.execute("""
    select id, community from user_communities
    """, (id))
    conn.commit()
    communities = cur.fetchmany(5000)

    try:
        os.makedirs("site/private".format())
    except:
        pass


    for cid, identikit in communities:
        sort_options = get_sort_options()
        url = 'http://localhost:85/communities/{}/id-asc/'.format(cid)

        save_url(url, override_path="communities/{}".format(cid))

        for sort_option in sort_options:
            response = requests.get('http://localhost:85/communities/{}/{}'.format(cid, sort_option[0]))
            try:
                os.makedirs("site/communities/{}/{}".format(cid, sort_option[0]))
            except:
                pass
            #print(response.content)
            open("site/communities/{}/{}/index.html".format(cid, sort_option[0]), "w").write(response.content.decode('utf-8'))

    cur = conn.cursor()
    categories = cur.execute("""
    select id from identikit_posts
    """, (id))
    conn.commit()
    posts = cur.fetchmany(5000)

    for post in posts:
        post_id = post[0]
        sort_options = get_sort_options()
        save_url('http://localhost:85/articles/{}/id-asc/'.format(post_id), override_path="articles/{}".format(post_id))

        for sort_option in sort_options:
            response = requests.get('http://localhost:85/articles/{}/{}'.format(post_id, sort_option[0]))
            try:
                os.makedirs("site/articles/{}/{}".format(post_id, sort_option[0]))
            except:
                pass
            #print(response.content)
            open("site/articles/{}/{}/index.html".format(post_id, sort_option[0]), "w").write(response.content.decode('utf-8'))


    response = requests.get('http://localhost:85/'.format())
    open("site/index.html", "w").write(response.content.decode('utf-8'))

    save_url('http://localhost:85/identikit'.format())
    save_url('http://localhost:85/top'.format())

    save_url('http://localhost:85/questionnaire')

    save_url('http://localhost:85/add/new'.format())

    save_url('http://localhost:85/view'.format())
    save_url('http://localhost:85/login'.format())
    save_url('http://localhost:85/logout'.format())


    cur = conn.cursor()
    categories = cur.execute("""
    select post, id from post_comments
    """, ())
    conn.commit()
    comments = cur.fetchmany(5000)
    for comment in comments:
        save_url('http://localhost:85/reply/{}/{}'.format(comment[0], comment[1]))


    cur = conn.cursor()
    categories = cur.execute("""
    select id from questions
    """, (id))
    conn.commit()
    questions = cur.fetchmany(5000)

    for question in questions:
        question_id = question[0]
        save_url('http://localhost:85/add/{}'.format(question_id))

        save_url('http://localhost:85/questions/{}/new'.format(question_id))

        cur = conn.cursor()
        categories = cur.execute("""
        select id from answers where question = %s
        """, (question_id,))
        conn.commit()
        answers = cur.fetchmany(5000)

        for answer in answers:
            answer_id = answer[0]
            save_url('http://localhost:85/questions/{}/{}'.format(question_id, answer_id))

    page = "dashboard"
    for user_id in ["1"]:
        response = requests.get("http://localhost:84/private/0/{}/{}".format(user_id, page), headers={
            "Override-User": user_id
        })
        try:
            os.makedirs("privatesite/{}/{}".format(user_id, page))
        except:
            pass
        open("privatesite/{}/{}/index.html".format(user_id, page), "w").write(response.text)

    page = "profile"
    for user_id in ["1"]:
        response = requests.get("http://localhost:84/private/0/{}/{}".format(user_id, page), headers={
            "Override-User": user_id
        })
        try:
            os.makedirs("privatesite/{}/{}".format(user_id, page))
        except:
            pass
        open("privatesite/{}/{}/index.html".format(user_id, page), "w").write(response.text)


    print("Site regen done")
