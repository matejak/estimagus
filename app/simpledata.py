from . import inidata


class Target(inidata.IniTarget):
    CONFIG_FILENAME = "targets.ini"


class Pollster(inidata.IniPollster):
    CONFIG_FILENAME = "pollsters.ini"

    def __init__(self, poll_id_prefix, * args, ** kwargs):
        self.poll_id_prefix = f"{poll_id_prefix}-"
        super().__init__(* args, ** kwargs)

    def tell_points(self, name, points):
        poll_id = self.poll_id_prefix + name
        return super().tell_points(poll_id, points)

    def ask_points(self, name):
        poll_id = self.poll_id_prefix + name
        return super().ask_points(poll_id)

    def knows_points(self, name):
        poll_id = self.poll_id_prefix + name
        return super().knows_points(poll_id)
