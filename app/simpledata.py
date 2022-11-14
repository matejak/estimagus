from . import inidata


class Target(inidata.IniTarget):
    CONFIG_FILENAME = "targets.ini"


class Pollster(inidata.IniPollster):
    CONFIG_FILENAME = "pollsters.ini"

    def __init__(self, poll_id_prefix, * args, ** kwargs):
        super().__init__(* args, ** kwargs)
        self.set_namespace(poll_id_prefix)

    def _keyname(self, ns, name):
        keyname = f"{ns}{name}"
        return keyname
