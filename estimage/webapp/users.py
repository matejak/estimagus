import flask
import flask_login


class User(flask_login.UserMixin):
    def __init__(self, uid, domain=""):
        self.uid = uid
        self.domain = domain

    def get_id(self):
        return self.uid


def load_user(uid):
    return User(uid)
