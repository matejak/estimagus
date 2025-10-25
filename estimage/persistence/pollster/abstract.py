import collections
import contextlib
import abc
import typing

from ... import data
from .. import abstract


class PollsterBase:
    WHAT_IS_THIS = "pollster"

    def _keyname(self, ns, name):
        keyname = f"{ns}-{name}"
        return keyname


class PollsterLoader(abstract.Loader, PollsterBase):
    def load_points(self, ns, name):
        keyname = self._keyname(ns, name)

        ret = data.EstimInput()
        ret.most_likely = float(self._get_items_attribute(keyname, "most_likely"))
        ret.optimistic = float(self._get_items_attribute(keyname, "optimistic"))
        ret.pessimistic = float(self._get_items_attribute(keyname, "pessimistic"))
        return ret

    def have_points(self, ns, name, config=None):
        keyname = self._keyname(ns, name)

        if keyname in self._loaded_data:
            return True
        return False


class PollsterSaver(abstract.Saver, PollsterBase):
    def _save(self, all_data_to_save):
        super()._save(all_data_to_save)

    def forget_points(self, ns, name):
        keyname = self._keyname(ns, name)
        self._data_to_forget.add(keyname)

    def save_points(self, ns, name, points: data.EstimInput):
        keyname = self._keyname(ns, name)

        self._store_item_attribute(keyname, "most_likely", str(points.most_likely))
        self._store_item_attribute(keyname, "optimistic", str(points.optimistic))
        self._store_item_attribute(keyname, "pessimistic", str(points.pessimistic))
