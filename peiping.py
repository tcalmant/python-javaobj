import re
import peiping_http as http

uri_map = {
    "http": http.HttpEndpoint,
    "cui": http.ConsoleEndpoint,
    "file": http.FileEndpoint
}

routes = []


class Endpoint():
    def to(self, object):
        print type(object)
        if type(object) is str:
            endpoint = endpoint_factory(str)
        pass

def endpoint(object):
    return Endpoint()

def run():
    for route in routes:
        route.run()

def from_ascii(str):
    pat_endpoint = re.compile(r"\[(.+?)\]")
    # something like "[http:/serv]->(mymethod)->[file:~/serv]"
    res = pat_endpoint.findall(str)
    if res:
        print res#.group(1)
    pass

def route(destination):
  def wrap(function):
    def wrap_function(self, message):
      function(self, message)
    Stomping.add_route(destination, wrap_function)
    return wrap_function
  return wrap