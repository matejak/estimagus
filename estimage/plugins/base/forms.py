from flask_wtf import FlaskForm


class BaseForm(FlaskForm):
    def __init__(self, ** kwargs):
        self.extending_fields = []
        super().__init__(** kwargs)

    @classmethod
    def bulk_supporting_js(cls, forms):
        return ""

    def supporting_js(self):
        return self.bulk_supporting_js([self])
