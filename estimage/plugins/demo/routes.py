import os

import flask
import flask_login
import numpy as np

from ...webapp import web_utils
from . import forms
from . import get_not_finished_targets, load_data, reset_data, save_data, start, conclude_target, begin_target

bp = flask.Blueprint("demo", __name__, template_folder="templates")


def apply_velocity(of_what, how_many, velocity_in_stash):
    velocity_in_stash[of_what] = velocity_in_stash.get(of_what, 0) + float(how_many)


def evaluate_progress(velocity_in_stash, targets_by_id, names, model, plugin_data, loader):
    for name in names:
        target = targets_by_id[name]

        if velocity_in_stash[name] > model.remaining_point_estimate_of(target.name).expected:
            flask.flash(f"Finished {target.name}")
            conclude_target(target, loader, plugin_data["day_index"])
        else:
            begin_target(target, loader, plugin_data["day_index"])


def apply_velocities(names, progress, velocity_in_stash):
    proportions = np.random.rand(len(names))
    proportions *= progress / sum(proportions)
    for name, proportion in zip(names, proportions):
        apply_velocity(name, proportion, velocity_in_stash)


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
    velocity_in_stash = plugin_data.get("velocity_in_stash", dict())
    if form.validate_on_submit():
        plugin_data = load_data()
        plugin_data["day_index"] = day_index + 1
        names = form.issues.data
        if len(names) == 1 and names[0] == "noop":
            pass
        else:
            apply_velocities(names, form.progress.data, velocity_in_stash)
            plugin_data["velocity_in_stash"] = velocity_in_stash
            evaluate_progress(velocity_in_stash, targets_by_id, names, model, plugin_data, loader)
        save_data(plugin_data)

    targets = get_not_finished_targets(targets)
    choices = [(t.name, f"{t.title} {velocity_in_stash.get(t.name, 0):.2g}/{t.point_cost}") for t in targets]
    if not choices:
        choices = [("noop", "Do Nothing")]
    form.issues.choices = choices

    return web_utils.render_template(
        'demo.html', title='Demo Plugin', reset_form=forms.ResetForm(), plugin_form=form, day_index=day_index)


@bp.route('/reset', methods=("POST", ))
@flask_login.login_required
def reset():
    reset_form = forms.ResetForm()
    if reset_form.validate_on_submit():
        reset_data()
    return flask.redirect(flask.url_for("demo.next_day"))
