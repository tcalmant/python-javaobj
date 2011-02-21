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