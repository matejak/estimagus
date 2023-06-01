
NAME = "Print"
EXPORTS = dict(
    Formatter="Printer",
    Ext="Greeter",
)


class Printer:
    OVERRIDEN = "yes"

    def format(self, what):
        ret = "-" + super().format(what)
        return ret


class Greeter:
    def return_hello(self):
        return super().return_hello() + "!"
