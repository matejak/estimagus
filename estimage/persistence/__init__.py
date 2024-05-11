import collections


LOADERS = collections.defaultdict(dict)
SAVERS = collections.defaultdict(dict)


def register_loader_of(loaded, backend, loader):
    LOADERS[loaded][backend] = loader


def register_saver_of(saved, backend, saver):
    SAVERS[saved][backend] = saver


def loader_of(loaded, backend):
    def decorator(loader):
        register_loader_of(loaded, backend, loader)
        return loader
    return decorator


def saver_of(saved, backend):
    def decorator(saver):
        register_saver_of(saved, backend, saver)
        return saver
    return decorator
