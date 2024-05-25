import flask
import flask_login

from .. import data, simpledata, persistence, utilities, history
from . import web_utils, CACHE


class Router:
    def __init__(self, ** kwargs):
        pass


class UserRouter(Router):
    def __init__(self, ** kwargs):
        super().__init__(** kwargs)

        self.user = flask_login.current_user
        self.user_id = self.user.get_id()


class IORouter(Router):
    IO_BACKEND = "ini"

    def __init__(self, ** kwargs):
        super().__init__(** kwargs)

        self.event_io = simpledata.IOs["events"][self.IO_BACKEND]

    def get_card_io(self, mode):
        try:
            flavor = simpledata.IOs[self.mode][self.IO_BACKEND]
            saver_type = persistence.SAVERS[self.card_class][self.IO_BACKEND]
            loader_type = persistence.LOADERS[self.card_class][self.IO_BACKEND]
            # in the special case of the ini backend, the registered loader doesn't call super()
            # when looking up CONFIG_FILENAME
            cards_io = type("cards_io", (flavor, saver_type, loader_type), dict())
        except KeyError as exc:
            msg = "Unknown specification of source: {self.mode}"
            raise KeyError(msg) from exc
        return cards_io

    def get_ios_by_target(self):
        ret = dict()
        ret["events"] = self.event_io
        ret["retro"] = get_card_io("retro")
        ret["proj"] = get_card_io("proj")
        return ret


class CardRouter(UserRouter, IORouter):
    def __init__(self, ** kwargs):
        super().__init__(** kwargs)

        self.mode = kwargs["mode"]
        self.card_class = flask.current_app.get_final_class("BaseCard")
        self.cards_io = self.get_card_io(self.mode)

        self.all_cards_by_id = self.get_all_cards_by_id()
        cards_list = list(self.all_cards_by_id.values())
        self.cards_tree_without_duplicates = utilities.reduce_subsets_from_sets(cards_list)

    @CACHE.cached(timeout=300, key_prefix='all_cards_by_id')
    def get_all_cards_by_id(self):
        ret = self.cards_io.get_loaded_cards_by_id(self.card_class)
        return ret


class ModelRouter(CardRouter):
    def __init__(self, ** kwargs):
        super().__init__(** kwargs)

        self.model = web_utils.get_user_model(self.user_id, self.cards_tree_without_duplicates)
        self.model.update_cards_with_values(self.cards_tree_without_duplicates)


class AggregationRouter(ModelRouter):
    def __init__(self, ** kwargs):
        super().__init__(** kwargs)

        self.start, self.end = flask.current_app.get_config_option("RETROSPECTIVE_PERIOD")
        self.all_events = self.get_all_events()

    @CACHE.cached(timeout=300, key_prefix='all_events')
    def get_all_events(self):
        all_events = data.EventManager()
        all_events.load(self.event_io)
        return all_events

    @property
    def aggregation(self):
        cards = self.cards_tree_without_duplicates
        return self.get_aggregation_of_cards(cards)

    def get_aggregation_of_names(self, names):
        cards = [self.all_cards_by_id[n] for n in names]
        return self.get_aggregation_of_cards(cards)

    def get_aggregation_of_cards(self, cards):
        statuses = flask.current_app.get_final_class("Statuses")()
        ret = history.Aggregation.from_cards(cards, self.start, self.end, statuses)
        ret.process_event_manager(self.all_events)
        return ret
