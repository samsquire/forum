import os
import time
from pprint import pprint
import networkx as nx
from networkx.algorithms.dag import topological_sort
from component_scheduler.scheduler import parallelise_components
import psycopg2
import redis
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor
from threading import Thread
from flask import Flask
import requests
import pickle

app = Flask(__name__)
hostname = os.environ["WORKER_HOST"]


groups = {}
spans = {}
hosts = {}
resource_dependencies = defaultdict(list)
has_index = defaultdict(list)
resources = {}
methods = {}
ports = {}

class Resources():
    pass

class Outputs():
    pass


def register_host(name, host, port, has):
    hosts[name] = host
    for item in has:
        has_index[item].append(name)
    ports[name] = port

def register_span(group, span_name, requires, method):
    if group not in groups:
        print("New group, creating group")
        groups[group] = nx.DiGraph()
    G = groups[group]
    if span_name not in spans:
        G.add_node(span_name)
    for requirement in requires:
        if requirement[0] == "@":
            print("{} depending on resource {}".format(span_name, requirement))
            resource_dependencies[span_name].append(requirement[1:])
        else:
            if requirement not in spans:
                spans[requirement] = requirement
                G.add_node(requirement)
            G.add_edge(requirement, span_name)
            print("{} depending on requirement {}".format(span_name, requirement))

    methods[span_name] = method

class Worker(Thread):
    def __init__(self, threads, span, method, resources, outputs):
        super(Worker, self).__init__()
        self.threads = threads
        self.span = span
        self.method = method
        self.resources = resources
        self.outputs = outputs

    def run(self):
        print(self.span["name"])
        for ancestor in self.span["ancestors"]:
            if ancestor in self.threads:
                print("Assuming other process did the work already")
                self.threads[ancestor].join()
        self.method(self.resources, self.outputs)

def initialize_group(group):
    # topologically sort
    component_data = []
    for node in topological_sort(groups[group]):
        component_data.append({
            "name": node,
            "ancestors": list(groups[group].predecessors(node)),
            "successors": list(groups[group].successors(node))
        })

    spans, orderings = parallelise_components(component_data=component_data)
    pprint(spans)
    previous_picked_host = ""
    # allocate spans to hosts
    for span in spans:
        span_name = span["name"]

        picked_host = ""
        for dependency in resource_dependencies[span_name]:
            print("Span '{}' would prefer to be on a host with fast access to '{}'".format(span_name, dependency))
            print("Hosts that have fast access to {}: {}".format(dependency, has_index[dependency]))
            for host in has_index[dependency]:
                picked_host = host
                break

        preferred_host_components = span_name.split(".")
        print(preferred_host_components)
        if len(preferred_host_components) == 2:
            preferred_host = preferred_host_components[0]
            picked_host = preferred_host

        if picked_host == "" and previous_picked_host != "":
            # no dependencies, can pick any host
            # faster to pick the previous host
            picked_host = previous_picked_host
        previous_picked_host = picked_host
        print(picked_host)
        print("Assigning {} to host {} which is {}".format(span_name, picked_host, hosts[picked_host]))
        span["host"] = picked_host
    return spans

def run_group(spans, host_name, group_name, start_task=None):
    interops = []
    # begin execution
    r = Resources()

    if host_name in hosts:
        host = hosts[host_name]
        for resource_name, resource in resources.items():
            resource(r, host)
    outputs = Outputs()
    threads = {}

    previous_host = ""

    running = False
    if start_task == None:
        running = True
    for span in spans:
        if start_task == span["name"]:
            running = True
        if not running:
            continue

        if (previous_host != "" and previous_host == span["host"]) or span["host"] == host_name:
            print("Can run here")

            span_name = span["name"]
            if span_name[0] == "@":
                continue # pseudo span
            method = methods[span["name"]]

            threads[span_name] = Worker(threads, span, method, resources, outputs)
        else:
            print("Need to interop")
            interops.append(span)
            break
        previous_host = span["host"]

    for thread_name, thread in threads.items():
        print("Starting thread {}".format(thread_name))
        thread.start()
    for thread in threads.values():
        thread.join()
    previous_host = span["host"]

    for interop in interops:
        data = pickle.dumps(outputs)
        response = requests.post("http://{}:{}/dispatch/{}/{}".format(hosts[span["host"]], ports[span["host"]], group_name, span["name"]), data=data)
        new_outputs = pickle.loads(response.content)
        print(new_outputs.__dict__.items())
        for new_key, new_value in new_outputs.__dict__.items():
            setattr(outputs, new_key, new_value)

    return outputs



def register_resource(name, implementation):
    resources[name] = implementation


def connect_to_database(resources, host):
    resources.conn = psycopg2.connect("dbname='forum' user='forum' host='" + host + "' password='forum'")
    print(resources.conn)

def connect_to_redis(resources, host):
    resources.r = r = redis.Redis(host=host, port=6379, db=0)
    print(resources.r)


register_resource("communities database", connect_to_database)
register_resource("redis cache", connect_to_database)

register_host(name="app", port=9005, host="localhost", has=[])
register_host(name="database", port=9006, host="localhost", has=["communities database", "redis cache"])

def get_community(r, o):
    print("Getting community query from database")
    o.community = 6

def get_exact_posts(r, o):
    print("Getting exact posts from database")
    o.exact_posts = ["blah"]

def get_partial_posts(r, o):
    print("Getting partial posts from database")
    o.partial_posts = ["yes"]

def combine_work(r, o):
    o.combine = o.partial_posts + o.exact_posts

register_span("get communities",
    "get community",
    ["@communities database"],
    get_community)
register_span("get communities",
    "app.get exact posts",
    ["get community"],
    get_exact_posts)
register_span("get communities",
    "app.get partial posts",
    ["get community"],
    get_partial_posts)
register_span("get communities",
    "app.combine work",
    ["app.get exact posts", "app.get partial posts"],
    combine_work)

spans = initialize_group("get communities")

@app.route("/dispatch/<group_name>/<start_task>", methods=["POST"])
def run_task(group_name, start_task):
    print("Received interop request {} {}".format(group_name, start_task))
    outputs = run_group(spans, hostname, group_name, start_task)
    return pickle.dumps(outputs)

if __name__ == "__main__":
    t0 = time.time()
    outputs = run_group(spans, "client", "get communities")
    print(outputs.exact_posts)
    print(outputs.partial_posts)
    print(outputs.community)
    print(outputs.combine)
    t1 = time.time()
    print(t1-t0)
