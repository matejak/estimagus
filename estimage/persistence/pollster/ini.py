from ... import data, inidata


class IniPollsterBase:
    def __init__(self, * args, ** kwargs):
        super().__init__(* args, ** kwargs)

    def _keyname(self, ns, name):
        keyname = f"{ns}-{name}"
        return keyname


class IniPollsterSaver(inidata.IniSaverBase, IniPollsterBase):
    def __init__(self, * args, ** kwargs):
        super().__init__(* args, ** kwargs)
        self._to_forget = set()

    def _store_our(self, t, attribute, value=None):
        if value is None and hasattr(t, attribute):
            value = getattr(t, attribute)
        return self._write_items_attribute(t.name, attribute, value)

    def save_points(self, ns, name, points: data.EstimInput):
        keyname = self._keyname(ns, name)

        self._write_items_attribute(keyname, "most_likely", str(points.most_likely))
        self._write_items_attribute(keyname, "optimistic", str(points.optimistic))
        self._write_items_attribute(keyname, "pessimistic", str(points.pessimistic))

    def _save(self, all_data_to_save):
        super()._save(all_data_to_save)
        for key_to_forget in self._to_forget:
            all_data_to_save.pop(key_to_forget)

    def forget_points(self, ns, name):
        keyname = self._keyname(ns, name)
        self._to_forget.add(keyname)


class IniPollsterLoader(inidata.IniLoaderBase, IniPollsterBase):
    def _get_value(self, keyname, attribute):
        return float(self._read_items_attribute(keyname, attribute, 0))

    def load_points(self, ns, name, config=None):
        keyname = self._keyname(ns, name)

        ret = data.EstimInput()
        ret.most_likely = self._get_value(keyname, "most_likely")
        ret.optimistic = self._get_value(keyname, "optimistic")
        ret.pessimistic = self._get_value(keyname, "pessimistic")
        return ret

    def have_points(self, ns, name, config=None):
        keyname = self._keyname(ns, name)

        if keyname in self._loaded_data:
            return True
        return False


class IniPollsterIO(IniPollsterLoader, IniPollsterSaver):
    def __init__(self, * args, ** kwargs):
        super().__init__(* args, ** kwargs)
