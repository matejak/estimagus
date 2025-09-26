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


def get_persistence(cls, io_format):
    if cls not in LOADERS:
        msg = f"Unknown class to load: '{cls}'"
        raise RuntimeError(msg)
    if io_format not in LOADERS[cls]:
        msg = f"Unknown format to load '{cls}' with: '{io_format}'"
        raise RuntimeError(msg)

    if cls not in SAVERS:
        msg = f"Unknown class to save: '{cls}'"
        raise RuntimeError(msg)
    if io_format not in SAVERS[cls]:
        msg = f"Unknown format to save '{cls}' with: '{io_format}'"
        raise RuntimeError(msg)

    io_name = f"{cls.__name__}__{io_format}__{io_format}"
    io_class = type(io_name, (SAVERS[cls][io_format], LOADERS[cls][io_format]), dict())
    return io_class
