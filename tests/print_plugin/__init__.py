
NAME = "Print"
EXPORTS = dict(Formatter="Printer")


class Printer:
    OVERRIDEN = "yes"

    def format(self, what):
        ret = "-" + super().format(what)
        return ret
