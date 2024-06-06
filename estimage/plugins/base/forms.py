from flask_wtf import FlaskForm


class BaseForm(FlaskForm):
    def __init__(self, ** kwargs):
        self.extending_fields = []
        super().__init__(** kwargs)

    @classmethod
    def supporting_js(cls, forms):
        return ""
