import flask
import flask_login

from ...webapp import web_utils
from . import forms
from . import get_not_finished_targets, load_data, save_data

bp = flask.Blueprint("demo", __name__, template_folder="templates")


@bp.route('/demo', methods=("GET", "POST"))
@flask_login.login_required
def next_day():
    cls, loader = web_utils.get_retro_loader()
    targets_by_id = loader.get_loaded_targets_by_id()
    targets = get_not_finished_targets(targets_by_id.values())

    form = forms.DemoForm()
    choices = [(t.name, t.title) for t in targets]
    form.issues.choices = choices
    if form.validate_on_submit():
        old_plugin_data = load_data()
        old_plugin_data["day_index"] = old_plugin_data.get("day_index", 0) + 1
        save_data(old_plugin_data)

    return web_utils.render_template(
        'demo.html', title='Demo Plugin', plugin_form=form, day_index=0)
