


class Storage:
    def __init__(self):
        self.storage = dict()
        self.ns_to_set = dict()

        self.requests = set()
        self.ns_requests = set()

    def feed_key(self, key, value, namespace=tuple()):
        ns = namespace
        if ns not in self.storage:
            self.storage[ns] = dict()
        self.storage[ns][key] = value

    def get_key(self, key):
        return self.storage[tuple()][key]

    def get_namespace(self, namespace):
        ret = dict()
        ret.update(self.storage[namespace])
        return ret

    def set_namespace(self, namespace, with_what):
        self.ns_to_set[namespace] = with_what

    def request_key(self, key):
        return self.requests.add(key)

    def request_namespace(self, namespace):
        ns = namespace
        return self.ns_requests.add(ns)

    def save(self, io):
        io.save_dict(self.storage)
        io.set_ns(self.ns_to_set)

    def load(self, io):
        data = dict()
        data[tuple()] = io.load_keys_to_dict(self.requests)
        for nsreq in self.ns_requests:
            try:
                more = io.load_ns_to_dict(nsreq)
            except KeyError:
                more = {nsreq: dict()}
            data.update(more)
        self.storage.update(data)
