from .. import abstract


class StorageLoader(abstract.Loader):
    def populate(self, storage):
        pass


class StorageSaver(abstract.Saver):
    def supply(self, storage):
        pass
