from ... import data, inidata, local_storage


class IniStorageBase:
    BASE_NS_STR = "-NONS-"
    BASE_NS = tuple()
    WHAT_IS_THIS = "Storage Item"


class IniStorageSaver(inidata.IniSaverBase, IniStorageBase):
    def save_dict(self, data):
        if self.BASE_NS not in data:
            return
        for key, val in data[self.BASE_NS].items():
            self._write_items_attribute(self.BASE_NS_STR, key, str(val))
        self.save()


class IniStorageLoader(inidata.IniLoaderBase, IniStorageBase):
    def load_keys_to_dict(self, keys):
        self._loaded_data = self._load_existing_config(self.CONFIG_FILENAME)

        ret = dict()
        for key in keys:
            ret[key] = self.load_key_to_dict(key)
        return ret

    def load_key_to_dict(self, key):
        try:
            return self._read_items_attribute(self.BASE_NS_STR, key, None)
        except RuntimeError:
            msg = f"Failed to load '{key}'"
            raise KeyError(msg)

    def load_ns_to_dict(self, ns):
        return {ns: dict()}


class IniStorageIO(IniStorageLoader, IniStorageSaver):
    pass
