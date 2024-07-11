GLOBAL_STORAGE = dict()
GLOBAL_STORAGE[tuple()] = dict()


class GlobalMemoryIO:
    def save_dict(self, data):
        GLOBAL_STORAGE.update(data)

    def set_ns(self, data):
        for key, contents in data.items():
            GLOBAL_STORAGE[key] = contents

    def load_keys_to_dict(self, keys):
        return {key: GLOBAL_STORAGE[tuple()][key] for key in keys}

    def load_ns_to_dict(self, nsname):
        return {nsname: GLOBAL_STORAGE[nsname]}


class LocalMemoryIO:
    def __init__(self):
        self.storage = dict()
        self.storage[tuple()] = dict()

    def save_dict(self, data):
        self.storage.update(data)

    def set_ns(self, data):
        for key, contents in data.items():
            self.storage[key] = contents

    def load_keys_to_dict(self, keys):
        return {key: self.storage[tuple()][key] for key in keys}

    def load_ns_to_dict(self, nsname):
        return {nsname: self.storage[nsname]}
