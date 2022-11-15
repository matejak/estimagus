import flask_login

from . import login

class User(flask_login.UserMixin):
    def __init__(self, uid):
        self.uid = uid
        
    def get_id(self):
        return self.uid


@login.user_loader
def load_user(id):
    return User(id)
