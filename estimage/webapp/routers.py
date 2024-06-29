import collections

import flask
import flask_login

from .. import data, simpledata, persistence, utilities, history, problems
from . import web_utils, CACHE


def gen_cache_key(basename):
    current_head_or_something = flask.request.blueprints[-1]
    return f"{current_head_or_something}-{basename}"


class Router:
    def __init__(self, ** kwargs):
        pass

    @classmethod
    def clear_cache(cls):
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

        self.card_class = flask.current_app.get_final_class("BaseCard")
        self.event_io = simpledata.IOs["events"][self.IO_BACKEND]

    def get_card_io(self, mode):
        try:
            flavor = simpledata.IOs[mode][self.IO_BACKEND]
            saver_type = persistence.SAVERS[self.card_class][self.IO_BACKEND]
            loader_type = persistence.LOADERS[self.card_class][self.IO_BACKEND]
            # in the special case of the ini backend, the registered loader doesn't call super()
            # when looking up CONFIG_FILENAME
            cards_io = type("cards_io", (flavor, saver_type, loader_type), dict())
        except KeyError as exc:
            msg = "Unknown specification of source: {mode}"
            raise KeyError(msg) from exc
        return cards_io

    def get_ios_by_target(self):
        ret = dict()
        ret["events"] = self.event_io
        ret["retro"] = self.get_card_io("retro")
        ret["proj"] = self.get_card_io("proj")
        return ret


class CardRouter(IORouter):
    CACHE_STEM_PROJ = "get_all_cards_by_id-proj"
    CACHE_STEM_RETRO = "get_all_cards_by_id-retro"

    def __init__(self, ** kwargs):
        super().__init__(** kwargs)

        self.mode = kwargs["mode"]
        self.cards_io = self.get_card_io(self.mode)

        self.all_cards_by_id = self.get_all_cards_by_id()
        cards_list = list(self.all_cards_by_id.values())
        self.cards_tree_without_duplicates = utilities.reduce_subsets_from_sets(cards_list)

    def get_all_cards_by_id(self):
        if self.mode == "retro":
            ret = self._get_cached_retro_cards()
        else:
            ret = self._get_cached_proj_cards()
        return ret

    @CACHE.cached(timeout=60, key_prefix=lambda: gen_cache_key(CardRouter.CACHE_STEM_RETRO))
    def _get_cached_retro_cards(self):
        return self._get_all_cards_by_id()

    @CACHE.cached(timeout=60, key_prefix=lambda: gen_cache_key(CardRouter.CACHE_STEM_PROJ))
    def _get_cached_proj_cards(self):
        return self._get_all_cards_by_id()

    @classmethod
    def clear_cache(cls):
        super().clear_cache()
        keys = [gen_cache_key(stem) for stem in (cls.CACHE_STEM_PROJ, cls.CACHE_STEM_RETRO)]
        CACHE.delete_many(* keys)

    def _get_all_cards_by_id(self):
        ret = self.cards_io.get_loaded_cards_by_id(self.card_class)
        return ret


class PollsterRouter(UserRouter):
    def __init__(self, ** kwargs):
        super().__init__(** kwargs)

        self.private_pollster = simpledata.AuthoritativePollster()
        self.global_pollster = simpledata.UserPollster(self.user_id)


class ModelRouter(PollsterRouter, CardRouter):
    def __init__(self, ** kwargs):
        super().__init__(** kwargs)

        self.model = web_utils.get_user_model_given_pollsters(
            self.private_pollster, self.global_pollster, self.cards_tree_without_duplicates)
        self.model.update_cards_with_values(self.cards_tree_without_duplicates)


class ProblemRouter(ModelRouter):
    def __init__(self, ** kwargs):
        super().__init__(** kwargs)

        all_cards = list(self.all_cards_by_id.values())
        detector_cls = flask.current_app.get_final_class("ProblemDetector")
        self.problem_detector = detector_cls()
        pollsters = collections.OrderedDict()
        pollsters["global"] = self.global_pollster
        pollsters["private"] = self.private_pollster
        self.problem_detector.detect(self.model, all_cards, pollsters)

        self.classifier = problems.groups.ProblemClassifier()
        self.classifier.classify(self.problem_detector.problems)


class AggregationRouter(ModelRouter):
    CACHE_STEM = "get_all_events"

    def __init__(self, ** kwargs):
        super().__init__(** kwargs)

        self.start, self.end = flask.current_app.get_config_option("RETROSPECTIVE_PERIOD")
        self.all_events = self.get_all_events()
        self.statuses = flask.current_app.get_final_class("Statuses")()

    @CACHE.cached(timeout=60, key_prefix=lambda: gen_cache_key(AggregationRouter.CACHE_STEM))
    def get_all_events(self):
        all_events = data.EventManager()
        all_events.load(self.event_io)
        return all_events

    @classmethod
    def clear_cache(cls):
        super().clear_cache()
        CACHE.delete(gen_cache_key(cls.CACHE_STEM))

    @property
    def aggregation(self):
        cards = self.cards_tree_without_duplicates
        return self.get_aggregation_of_cards(cards)

    def get_aggregation_of_names(self, names):
        cards = [self.all_cards_by_id[n] for n in names]
        return self.get_aggregation_of_cards(cards)

    def get_aggregation_of_cards(self, cards):
        ret = history.Aggregation.from_cards(cards, self.start, self.end, self.statuses)
        ret.process_event_manager(self.all_events)
        return ret
