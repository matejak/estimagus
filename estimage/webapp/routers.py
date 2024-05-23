import flask
import flask_login

from .. import simpledata, persistence, utilities, history
from . import web_utils


class Router:
    def __init__(self, ** kwargs):
        pass


class UserRouter(Router):
    def __init__(self, ** kwargs):
        super().__init__(** kwargs)

        self.user = flask_login.current_user
        self.user_id = self.user.get_id()


class CardRouter(UserRouter):
    IO_BACKEND = "ini"

    def __init__(self, ** kwargs):
        super().__init__(** kwargs)

        self.mode = kwargs["mode"]
        self.card_class = flask.current_app.get_final_class("BaseCard")

        try:
            flavor = simpledata.IOs[self.mode][self.IO_BACKEND]
            saver_type = persistence.SAVERS[self.card_class][self.IO_BACKEND]
            loader_type = persistence.LOADERS[self.card_class][self.IO_BACKEND]
            # in the special case of the ini backend, the registered loader doesn't call super()
            # when looking up CONFIG_FILENAME
            self.io = type("io", (flavor, saver_type, loader_type), dict())
        except KeyError as exc:
            msg = "Unknown specification of source: {self.mode}"
            raise KeyError(msg) from exc

        self.all_cards_by_id = self.io.get_loaded_cards_by_id(self.card_class)
        cards_list = list(self.all_cards_by_id.values())
        self.cards_tree_without_duplicates = utilities.reduce_subsets_from_sets(cards_list)


class ModelRouter(CardRouter):
    def __init__(self, ** kwargs):
        super().__init__(** kwargs)

        self.model = web_utils.get_user_model(self.user_id, self.cards_tree_without_duplicates)
        self.model.update_cards_with_values(self.cards_tree_without_duplicates)


class AggregationRouter(ModelRouter):
    def __init__(self, ** kwargs):
        super().__init__(** kwargs)

        self.start, self.end = flask.current_app.get_config_option("RETROSPECTIVE_PERIOD")
        self.all_events = simpledata.EventManager()
        self.all_events.load()

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
