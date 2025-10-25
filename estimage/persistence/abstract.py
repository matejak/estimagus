import abc
import collections
import contextlib


class Loader(abc.ABC):
    WHAT_IS_THIS = ""
    def __init__(self, ** kwargs):
        super().__init__(** kwargs)
        self._loaded_data = dict()

    @classmethod
    @contextlib.contextmanager
    def get_loader(cls):
        loader = cls()
        loader._loaded_data = loader.load()
        yield loader

    @abc.abstractmethod
    def load(self):
        """
        Return loaded data, whatever that means, as a dict
        """
        raise NotImplementedError()

    def _get_our(self, item, attribute, fallback=None):
        if fallback is None and hasattr(item, attribute):
            fallback = getattr(item, attribute)
        if item.name not in self._loaded_data:
            msg = f"Couldn't find {self.WHAT_IS_THIS} '{item.name}'"
            raise RuntimeError(msg)
        return self._get_items_attribute(item.name, attribute, fallback)

    def _get_items_attribute(self, storage_key, attribute, fallback=None):
        if storage_key not in self._loaded_data:
            return fallback
        return self._loaded_data[storage_key].get(attribute, fallback)


class FileBased:
    @classmethod
    def stem_to_filename(cls, stem):
        """
        Given a stem of a filename, return the filename.
        Typically, append an appropriate file extension
        """
        return stem


class FileBasedLoader(Loader, FileBased):
    LOAD_FILENAME = ""
    def _read_items_attribute(self, item_id, attribute_id, fallback):
        if item_id not in self._loaded_data:
            msg = f"Couldn't load {self.WHAT_IS_THIS} '{item_id}' from '{self.LOAD_FILENAME}'"
            raise RuntimeError(msg)
        return self._loaded_data.get(item_id, attribute_id, fallback=fallback)

    @abc.abstractclassmethod
    def _load_existing_file(cls, filename):
        raise NotImplementedError()

    def load(self):
        return self._load_existing_file(self.LOAD_FILENAME)


class Saver(abc.ABC):
    WHAT_IS_THIS = ""
    def __init__(self, ** kwargs):
        super().__init__(** kwargs)
        self._data_to_save = collections.defaultdict(dict)
        self._data_to_forget = set()

    @abc.abstractclassmethod
    def forget_all(cls):
        raise NotImplementedError()

    @abc.abstractmethod
    def save(self):
        raise NotImplementedError()

    @classmethod
    @contextlib.contextmanager
    def get_saver(cls):
        saver = cls()
        yield saver
        saver.save()

    def _store_our(self, item, attribute, value=None):
        if not item.name:
            msg = f"Coudln't save {self.WHAT_IS_THIS}, because the name is blank."
            raise RuntimeError(msg)
        if value is None and hasattr(item, attribute):
            value = getattr(item, attribute)
        self._store_item_attribute(item.name, attribute, value)

    def _store_item_attribute(self, storage_key, attribute, value):
        self._data_to_save[storage_key][attribute] = value


class FileBasedSaver(Saver):
    SAVE_FILENAME = ""
    def __init__(self, ** kwargs):
        super().__init__(** kwargs)
        self.save_filename = None

    def save(self):
        with self._manipulate_existing_file(self.SAVE_FILENAME) as data_in_dict:
            self._update_existing_data_with_fresh(data_in_dict)

    @classmethod
    def forget_all(cls):
        with cls._manipulate_existing_file(cls.SAVE_FILENAME) as data_in_dict:
            data_in_dict.clear()

    def _update_existing_data_with_fresh(self, all_data_to_save):
        for name, data_to_save in self._data_to_save.items():
            if name not in all_data_to_save:
                all_data_to_save[name] = dict()
            all_data_to_save[name].update(data_to_save)
        for name in self._data_to_forget:
            all_data_to_save.pop(name, None)

    @abc.abstractclassmethod
    def _manipulate_existing_file(cls):
        raise NotImplementedError()
