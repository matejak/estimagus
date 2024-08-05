from ... import data, inidata, local_storage


class IniStorageBase:
    BASE_NS_STR = "-NONS-"
    NS_SEP = "*-*-*"
    BASE_NS = tuple()
    WHAT_IS_THIS = "Storage Item"


class IniStorageSaver(inidata.IniSaverBase, IniStorageBase):
    def _update_ns(self, ns_str, tosave):
        for key, val in tosave.items():
            self._write_items_attribute(ns_str, key, str(val))

    def save_dict(self, data):
        for ns, tosave in data.items():
            ns_str = self.NS_SEP.join(ns)
            if ns == self.BASE_NS:
                ns_str = self.BASE_NS_STR
            self._update_ns(ns_str, tosave)
        self.save()

    def set_ns(self, data):
        self._remove_namespaces(data.keys())
        for ns, tosave in data.items():
            ns_str = self.NS_SEP.join(ns)
            self._update_ns(ns_str, tosave)
        self.save()

    def _remove_namespaces(self, namespaces):
        with self._manipulate_existing_config(self.CONFIG_FILENAME) as config:
            for ns in namespaces:
                ns_str = self.NS_SEP.join(ns)
                if ns_str in config:
                    del config[ns_str]
                if ns_str in self._data_to_save:
                    del self._data_to_save[ns_str]


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
        ns_str = self.NS_SEP.join(ns)
        if ns_str not in self._loaded_data:
            msg = f"Failed to load '{ns}'"
            raise KeyError(msg)
        ret = dict()
        ret[ns] = self._loaded_data[ns_str]
        return ret


class IniStorageIO(IniStorageLoader, IniStorageSaver):
    pass
