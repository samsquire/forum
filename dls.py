import sys
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
from flask import Flask, request
import requests
import pickle
from opentracing.propagation import Format
import json

app = Flask(__name__)
hostname = os.environ["WORKER_HOST"]

from jaeger_client import Config


config = Config(
        config={ # usually read from some yaml config
            'sampler': {
                'type': 'const',
                'param': 1,
            },
            'logging': True,
        },
        service_name='dls',
        validate=True
)

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

class WorkOutput():
    pass


def register_host(name, host, port, has):
    hosts[name] = host
    for item in has:
        has_index[item].append(name)
    ports[name] = port

def register_span(group, span_name, requires, method):
    if group not in groups:
        groups[group] = nx.DiGraph()
    G = groups[group]
    if span_name not in spans:
        G.add_node(span_name)
    for requirement in requires:
        if requirement[0] == "@":
            # print("{} depending on resource {}".format(span_name, requirement))
            resource_dependencies[span_name].append(requirement[1:])
        else:
            if requirement not in spans:
                spans[requirement] = requirement
                G.add_node(requirement)
            G.add_edge(requirement, span_name)
            # print("{} depending on requirement {}".format(span_name, requirement))

    methods[span_name] = method

class Worker(Thread):
    def __init__(self, tracer, threads, span, method, resources, outputs, tracer_context):
        super(Worker, self).__init__()
        self.tracer = tracer
        self.threads = threads
        self.span = span
        self.method = method
        self.resources = resources
        self.outputs = outputs
        self.tracer_context = tracer_context

    def run(self):
        for ancestor in self.span["ancestors"]:
            if ancestor in self.threads:
                # print("Assuming other process did the work already")
                self.threads[ancestor].join()

        span_context = self.tracer.extract(
           format=Format.HTTP_HEADERS,
           carrier=self.tracer_context
        )
        span = self.tracer.start_span(
           operation_name=self.span["name"],
           child_of=span_context)

        with self.tracer.scope_manager.activate(span, True) as scope:
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
    # pprint(spans)
    previous_picked_host = ""
    # allocate spans to hosts
    for span in spans:
        span_name = span["name"]

        picked_host = ""
        for dependency in resource_dependencies[span_name]:
            print("Span '{}' would prefer to be on a host with fast access to '{}'".format(span_name, dependency))
            print(" - Hosts that have fast access to {}: {}".format(dependency, has_index[dependency]))
            for host in has_index[dependency]:
                picked_host = host
                break

        preferred_host_components = span_name.split(".")

        if len(preferred_host_components) == 2:
            preferred_host = preferred_host_components[0]
            picked_host = preferred_host

        if picked_host == "" and previous_picked_host != "":
            # no dependencies, can pick any host
            # faster to pick the previous host
            picked_host = previous_picked_host
        previous_picked_host = picked_host

        print(" - Assigning {} to host {} which is at {}:{}".format(span_name, picked_host, hosts[picked_host], ports[picked_host]))
        span["host"] = picked_host
    return spans

tracer = config.initialize_tracer()
print("twice")

def run_group(propagate, spans, host_name, group_name, start_task=None, span_context=None, originator=None):
    unstarted_threads = []
    if not span_context:
        outbound_span = tracer.start_span(
           operation_name=host_name
       )
    else:
        span_context = tracer.extract(
           format=Format.HTTP_HEADERS,
           carrier=span_context
        )
        outbound_span = tracer.start_span(
           operation_name=host_name,
           child_of=span_context)


    tasks = []
    # begin execution
    r = Resources()

    if host_name in hosts:
        host = hosts[host_name]
        for resource_name, resource in resources.items():
            resource(r, host)
    outputs = WorkOutput()
    threads = {}

    previous_host = ""

    running = False
    if start_task == None:
        running = True

    with tracer.scope_manager.activate(outbound_span, True) as scope:
        for span in spans:
            span_name = span["name"]
            span["task"] = "skip"
            if start_task == span["name"]:
                running = True
            if not running:
                continue


            if span["host"] == host_name:
                print("We can run {} on this host".format(span_name, host_name))

                span_name = span["name"]
                if span_name[0] == "@":
                    continue # pseudo span
                method = methods[span["name"]]

                http_header_carrier = {}
                tracer.inject(
                    span_context=outbound_span,
                    format=Format.HTTP_HEADERS,
                    carrier=http_header_carrier)

                threads[span_name] = Worker(tracer, threads, span, method, resources, outputs, http_header_carrier)
                unstarted_threads.append(span_name)
                span["task"] = "thread"

            if span["host"] == originator:
                running = False
                continue
            elif span["host"] != host_name:
                print("Need to interop")
                if previous_host != span["host"]:
                    span["task"] = "interop"

            previous_host = span["host"]

        pending_threads = []
        for span in spans:
            span_name = span["name"]

            if span["task"] == "thread":
                print("Starting thread {}".format(span_name))
                threads[span_name].start()
                unstarted_threads.remove(span_name)
                pending_threads.append(span_name)
            if span["task"] == "interop":

                # wait for pending work before making request
                for pending_thread in pending_threads:
                    threads[pending_thread].join()

                headers = {}
                interop_span = tracer.start_span(
                   operation_name=span_name,
                   child_of=span_context)
                tracer.inject(
                   span_context=outbound_span,
                   format=Format.HTTP_HEADERS,
                   carrier=headers)

                with tracer.scope_manager.activate(interop_span, True) as scope:
                    print("Interop to {}:{} for {}".format(hosts[span["host"]],
                        ports[span["host"]],
                        span["name"]))
                    data = json.dumps(outputs.__dict__)
                    host_counter = 0

                    response = requests.post("http://{}:{}/dispatch/{}/{}/{}".format(hosts[span["host"]],
                       ports[span["host"]],
                       group_name, span["name"], host_name), data=data, headers=headers)

                    new_outputs = json.loads(response.text)
                    for new_key, new_value in new_outputs.items():
                        setattr(outputs, new_key, new_value)
                    print("Received interop from {}".format(span["name"]))
                if not propagate:
                    break


        #for thread_name, thread in threads.items():
        for thread in pending_threads:
            threads[thread].join()

    return outputs



def register_resource(name, implementation):
    resources[name] = implementation


def connect_to_database(resources, host):
    resources.conn = psycopg2.connect("dbname='forum' user='forum' host='" + host + "' password='forum'")
    print(resources.conn)

def connect_to_redis(resources, host):
    resources.r = redis.Redis(host=host, port=6379, db=0)
    print(resources.r)


register_resource("communities database", connect_to_database)
register_resource("redis cache", connect_to_redis)

register_host(name="app", port=9005, host="localhost", has=[])
register_host(name="database", port=9006, host="localhost", has=["communities database", "redis cache"])

def get_community(r, o):
    print("Getting community query from database")
    o.community = 6


def get_exact_posts(r, o):
    print("Getting exact posts from database")
    o.exact_posts = ["An exact post"]


def get_partial_posts(r, o):
    print("Getting partial posts from database")
    o.partial_posts = ["A partial search result"]


def combine_work(r, o):
    print("Combining work")
    o.combine = o.partial_posts + o.exact_posts


def get_parent_communities(r, o):
    o.parent_posts = ["one"]

register_span("get communities",
    "app.get community",
    [],
    get_community)
register_span("get communities",
    "database.get exact posts",
    ["app.get community", "@communities database"],
    get_exact_posts)
register_span("get communities",
    "database.get partial posts",
    ["app.get community", "@communities database"],
    get_partial_posts)
register_span("get communities",
    "app.combine work",
    ["database.get exact posts", "database.get partial posts"],
    combine_work)
register_span("get communities",
    "get parent communities",
    ["@communities database",
    "app.combine work"],
    get_parent_communities)

spans = initialize_group("get communities")

@app.route("/dispatch/<group_name>/<start_task>/<originator>", methods=["POST"])
def run_task(group_name, start_task, originator):
    print("Received interop request {} {}".format(group_name, start_task))
    outputs = run_group(True, spans, hostname, group_name, start_task, span_context=request.headers, originator=originator)
    return json.dumps(outputs.__dict__)

if __name__ == "__main__":
    t0 = time.time()
    outputs = run_group(False, spans, "client", "get communities")
    print(outputs.exact_posts)
    print(outputs.partial_posts)
    print(outputs.community)
    print(outputs.combine)
    print(outputs.parent_posts)
    t1 = time.time()
    print(t1-t0)
