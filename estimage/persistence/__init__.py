import collections


LOADERS = collections.defaultdict(dict)
SAVERS = collections.defaultdict(dict)


def loader_of(loaded, backend):
    def decorator(loader):
        LOADERS[loaded][backend] = loader
        return loader
    return decorator


def saver_of(saved, backend):
    def decorator(saver):
        SAVERS[saved][backend] = saver
        return saver
    return decorator
