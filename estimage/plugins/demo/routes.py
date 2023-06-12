import flask
import flask_login

from ...webapp import web_utils
from . import forms
from . import get_not_finished_targets, load_data, save_data, start, conclude_target, begin_target

bp = flask.Blueprint("demo", __name__, template_folder="templates")


@bp.route('/demo', methods=("GET", "POST"))
@flask_login.login_required
def next_day():
    user = flask_login.current_user
    user_id = user.get_id()

    cls, loader = web_utils.get_retro_loader()
    targets_by_id, model = web_utils.get_all_tasks_by_id_and_user_model("retro", user_id)
    targets = get_not_finished_targets(targets_by_id.values())
    targets = [targets_by_id[n] for n in sorted([t.name for t in targets])]

    plugin_data = load_data()
    if (day_index := plugin_data.get("day_index", 0)) == 0:
        start(targets_by_id.values(), loader)

    form = forms.DemoForm()
    choices = [(t.name, t.title) for t in targets]
    if not choices:
        choices = [("noop", "Do Nothing")]
    form.issues.choices = choices
    if form.validate_on_submit():
        name = form.issues.data
        plugin_data = load_data()
        plugin_data["day_index"] = day_index + 1
        velocity_in_stash = plugin_data.get("velocity_in_stash", dict())
        velocity_in_stash[name] = velocity_in_stash.get(name, 0) + float(form.progress.data)
        if form.issues.data != "noop":
            target = targets_by_id[name]

            if velocity_in_stash[name] > model.remaining_point_estimate_of(target.name).expected:
                flask.flash(f"Finished {target.name}")
                conclude_target(target, loader, plugin_data["day_index"])
            else:
                begin_target(target, loader, plugin_data["day_index"])

            plugin_data["velocity_in_stash"] = velocity_in_stash
        save_data(plugin_data)

    targets = get_not_finished_targets(targets)
    choices = [(t.name, t.title) for t in targets]
    if not choices:
        choices = [("noop", "Do Nothing")]
    form.issues.choices = choices

    return web_utils.render_template(
        'demo.html', title='Demo Plugin', plugin_form=form, day_index=day_index)
