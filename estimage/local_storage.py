


class Storage:
    def __init__(self):
        self.storage = dict()
        self.requests = set()
        self.ns_requests = set()

    def feed_key(self, key, value, namespace=tuple()):
        if namespace:
            ns = namespace[0]
            if ns not in self.storage:
                self.storage[ns] = dict()
            self.storage[ns][key] = value
        else:
            self.storage[key] = value

    def get_key(self, key):
        return self.storage[key]

    def get_namespace(self, namespace):
        ns = namespace[0]
        return self.storage[ns]

    def request_key(self, key):
        return self.requests.add(key)

    def request_namespace(self, namespace):
        ns = namespace[0]
        return self.ns_requests.add(ns)

    def save(self, io):
        io.save_dict(self.storage)

    def load(self, io):
        data = io.load_to_dict(self.requests)
        for nsreq in self.ns_requests:
            try:
                more = io.load_to_dict((nsreq,))
            except KeyError:
                more = {nsreq: dict()}
            data.update(more)
        self.storage.update(data)
