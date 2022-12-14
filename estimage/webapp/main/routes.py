import io

import flask
import flask_login
import werkzeug.urls
import matplotlib
import datetime
import types

from . import bp
from . import forms
from ... import data
from ... import utilities
from ... import simpledata as webdata
from ... import history
from ..users import User
from .google_login import google_callback_dest, google_login


matplotlib.use('Agg')
import matplotlib.pyplot as plt


def render_template(template_basename, title, **kwargs):
    authenticated_user = ""
    if flask_login.current_user.is_authenticated:
        authenticated_user = flask_login.current_user
    return flask.render_template(
        template_basename, title=title, authenticated_user=authenticated_user, ** kwargs)


@bp.route('/logout', methods=['GET'])
def logout():
    flask_login.logout_user()
    return flask.redirect("/login")


def autologin():
    form = forms.AutoLoginForm()
    if form.validate_on_submit():
        user = User(form.username.data)
        flask_login.login_user(user, remember=form.remember_me.data)

        next_page = flask.request.args.get('next')
        if not next_page or werkzeug.urls.url_parse(next_page).netloc != '':
            next_page = flask.url_for('main.tree_view')
        return flask.redirect(next_page)
    login_provider = flask.current_app.config["LOGIN_PROVIDER_NAME"]
    return render_template(
        'login.html', title='Sign In', login_form=form, login_provider=login_provider)


@bp.route('/login', methods=['GET', 'POST'])
def login():
    config_dict = flask.current_app.config
    match provider_name := config_dict["LOGIN_PROVIDER_NAME"]:
        case "autologin":
            return autologin()
        case "google":
            return google_login()
        case _:
            msg = f"Unknown login provider: {provider_name}"
            raise ValueError(msg)


def tell_pollster_about_obtained_data(pollster, task_id, form_data):
    est = data.EstimInput(form_data.most_likely.data)
    est.pessimistic = form_data.pessimistic.data
    est.optimistic = form_data.optimistic.data
    pollster.tell_points(task_id, est)


def ask_pollster_of_existing_data(pollster, task_id):
    task_estimates = pollster.ask_points(task_id)
    if not task_estimates:
        return None

    est = data.Estimate.from_triple(
        float(task_estimates.most_likely),
        float(task_estimates.optimistic),
        float(task_estimates.pessimistic))

    return est


def feed_estimation_to_form_and_arg_dict(estimation, form_data, arg_dict):
    form_data.optimistic.data = estimation.source.optimistic
    form_data.most_likely.data = estimation.source.most_likely
    form_data.pessimistic.data = estimation.source.pessimistic

    arg_dict["estimate"] = estimation


def retreive_task(task_id):
    ret = webdata.Target.load_metadata(task_id)
    ret.load_point_cost()
    return ret


@bp.route('/consensus/<task_name>', methods=['POST'])
@flask_login.login_required
def move_issue_estimate_to_consensus(task_name):
    user = flask_login.current_user
    user_id = user.get_id()
    form = forms.ConsensusForm()
    if form.validate_on_submit() and form.i_kid_you_not.data:
        pollster_user = webdata.UserPollster(user_id)
        pollster_cons = webdata.AuthoritativePollster()

        user_point = pollster_user.ask_points(task_name)
        pollster_cons.tell_points(task_name, user_point)

        if form.forget_own_estimate.data:
            pollster_user.forget_points(task_name)

    else:
        flask.flash("Consensus not updated, request was not serious")

    return flask.redirect(
        flask.url_for("main.view_task", task_name=task_name))


@bp.route('/authoritative/<task_name>', methods=['POST'])
@flask_login.login_required
def move_consensus_estimate_to_authoritative(task_name):
    form = forms.AuthoritativeForm()
    if form.validate_on_submit() and form.i_kid_you_not.data:
        pollster_cons = webdata.AuthoritativePollster()

        est_input = pollster_cons.ask_points(task_name)
        propagate_estimate_to_task(task_name, est_input)
    else:
        flask.flash("Authoritative estimate not updated, request was not serious")

    return flask.redirect(
        flask.url_for("main.view_task", task_name=task_name))


def propagate_estimate_to_task(task_name, est_input):
    targets = webdata.Target.get_loaded_targets_by_id()
    target = targets[task_name]

    est = data.Estimate.from_input(est_input)
    target.point_cost = est.expected

    target.save_point_cost()


@bp.route('/estimate/<task_name>', methods=['POST'])
@flask_login.login_required
def estimate(task_name):
    user = flask_login.current_user

    user_id = user.get_id()

    form = forms.NumberEstimationForm()
    pollster = webdata.UserPollster(user_id)

    if form.validate_on_submit():
        tell_pollster_about_obtained_data(pollster, task_name, form)
        return flask.redirect(
            flask.url_for("main.view_task", task_name=task_name))


@bp.route('/view_task/<task_name>')
@flask_login.login_required
def view_task(task_name):
    user = flask_login.current_user

    user_id = user.get_id()
    pollster = webdata.UserPollster(user_id)
    request_forms = dict(
        estimation=forms.NumberEstimationForm(),
        consensus=forms.ConsensusForm(),
        authoritative=forms.AuthoritativeForm(),
    )

    t = retreive_task(task_name)
    estimation_args = dict()
    estimation = ask_pollster_of_existing_data(pollster, task_name)
    if estimation:
        eform = request_forms["estimation"]
        feed_estimation_to_form_and_arg_dict(estimation, eform, estimation_args)

    if "estimate" in estimation_args:
        similar_tasks = get_similar_tasks(user_id, task_name)
        estimation_args["similar_sized_tasks"] = similar_tasks
        all_targets = webdata.Target.get_loaded_targets_by_id()
        estimation_args["similar_sized_targets"] = [
            all_targets[task.name] for task in similar_tasks
        ]

        c_pollster = webdata.AuthoritativePollster()
        con_input = c_pollster.ask_points(task_name)
        estimation_args["consensus"] = data.Estimate.from_input(con_input)

    return render_template(
        'issue_view.html', title='Estimate Issue',
        user=user, forms=request_forms, task=t, ** estimation_args)


@bp.route('/view_epic/<epic_name>')
@flask_login.login_required
def view_epic(epic_name):
    user = flask_login.current_user

    user_id = user.get_id()
    model = get_user_model(user_id)

    t = retreive_task(epic_name)

    return render_template(
        'epic_view.html', title='View epic', epic=t, estimate=model.point_estimate_of(epic_name))


def send_figure_as_png(figure, filename):
    bytesio = io.BytesIO()
    figure.savefig(bytesio, format="png")
    bytesio.seek(0)

    return flask.send_file(bytesio, download_name=filename, mimetype="image/png")


def get_pert_in_figure(estimation, task_name):
    pert = estimation.get_pert()

    fig, ax = plt.subplots(1, 1)
    ax.plot(pert[0], pert[1], 'b-', lw=2, label=f'task {task_name}')
    ax.axvline(estimation.expected, color="orange", label="expected value")
    ax.set_xlabel("points")
    ax.set_ylabel("probability density")
    ax.set_yticklabels([])
    ax.grid()
    ax.legend()

    return fig


@bp.route('/vis/<epic_name>-burndown.png')
@flask_login.login_required
def visualize_burndown(epic_name):
    all_targets = webdata.Target.get_loaded_targets_by_id()
    all_events = webdata.EventManager.load()

    start = flask.current_app.config["PERIOD"]["start"]
    end = flask.current_app.config["PERIOD"]["end"]

    if epic_name == ".":
        aggregation = history.Aggregation.from_targets(all_targets.values(), start, end)
    else:
        epic = all_targets[epic_name]
        aggregation = history.Aggregation.from_target(epic, start, end)

    aggregation.process_event_manager(all_events)

    fig = history.MPLPointPlot(aggregation).get_figure()
    return send_figure_as_png(fig, f'{epic_name}.png')


@bp.route('/vis/<epic_name>-velocity.png')
@flask_login.login_required
def visualize_velocity(epic_name):
    all_targets = webdata.Target.get_loaded_targets_by_id()
    all_events = webdata.EventManager.load()

    start = flask.current_app.config["PERIOD"]["start"]
    end = flask.current_app.config["PERIOD"]["end"]

    if epic_name == ".":
        aggregation = history.Aggregation.from_targets(all_targets.values(), start, end)
    else:
        epic = all_targets[epic_name]
        aggregation = history.Aggregation.from_target(epic, start, end)

    aggregation.process_event_manager(all_events)
    cutoff_date = min(datetime.datetime.today(), end)

    fig = history.MPLVelocityPlot(aggregation).get_figure(cutoff_date)
    return send_figure_as_png(fig, f'{epic_name}.png')


@bp.route('/vis/<task_name>-pert.png')
@flask_login.login_required
def visualize_task(task_name):
    user = flask_login.current_user

    user_id = user.get_id()
    model = get_user_model(user_id)
    if task_name == ".":
        estimation = model.main_composition.point_estimate
    else:
        estimation = model.point_estimate_of(task_name)

    fig = get_pert_in_figure(estimation, task_name)

    return send_figure_as_png(fig, f'{task_name}.png')


def get_target_tree_with_no_double_occurence():
    all_targets = webdata.Target.load_all_targets()
    targets_tree_without_duplicates = utilities.reduce_subsets_from_sets(all_targets)
    return targets_tree_without_duplicates


def get_user_model(user_id, targets_tree_without_duplicates=None):
    if targets_tree_without_duplicates is None:
        targets_tree_without_duplicates = get_target_tree_with_no_double_occurence()
    authoritative_pollster = webdata.AuthoritativePollster()
    user_pollster = webdata.UserPollster(user_id)
    model = webdata.get_model(targets_tree_without_duplicates)
    authoritative_pollster.inform_results(model.get_all_task_models())
    user_pollster.inform_results(model.get_all_task_models())
    return model


def get_similar_tasks(user_id, task_name):
    model = get_user_model(user_id)
    all_tasks = model.get_all_task_models()
    return webdata.order_nearby_tasks(model.get_element(task_name), all_tasks, 0.5, 2)


@bp.route('/')
@flask_login.login_required
def tree_view():
    user = flask_login.current_user
    user_id = user.get_id()

    all_targets = webdata.Target.load_all_targets()
    targets_tree_without_duplicates = utilities.reduce_subsets_from_sets(all_targets)
    model = get_user_model(user_id, targets_tree_without_duplicates)
    return render_template(
        "tree_view.html", title="Tasks tree view",
        targets=targets_tree_without_duplicates, model=model)


def executive_summary_of_points_and_velocity(targets):
    all_events = webdata.EventManager.load()

    start = flask.current_app.config["PERIOD"]["start"]
    end = flask.current_app.config["PERIOD"]["end"]
    cutoff_date = min(datetime.datetime.today(), end)
    aggregation = history.Aggregation.from_targets(targets, start, end)
    aggregation.process_event_manager(all_events)

    not_done_on_start = 0
    cutoff_data = types.SimpleNamespace(todo=0, underway=0, done=0)
    for r in aggregation.repres:
        repre_points = r.get_points_at(start)
        if r.get_status_at(start) in (data.State.todo, data.State.in_progress, data.State.review):
            not_done_on_start += repre_points
        if r.get_status_at(cutoff_date) == data.State.todo:
            cutoff_data.todo += repre_points
        elif r.get_status_at(cutoff_date) in (data.State.in_progress, data.State.review):
            cutoff_data.underway += repre_points
        else:
            cutoff_data.done += repre_points

    output = dict(
        initial_todo=not_done_on_start,
        last_record=cutoff_data,
        total_days_in_period=(cutoff_date - start).days,
        total_points_done=not_done_on_start - (cutoff_data.todo + cutoff_data.underway)
    )
    return output


@bp.route('/retro')
@flask_login.login_required
def tree_view_retro():
    all_targets = webdata.Target.load_all_targets()
    executive_summary = executive_summary_of_points_and_velocity(all_targets)

    targets_tree_without_duplicates = utilities.reduce_subsets_from_sets(all_targets)
    return render_template(
        "tree_view_retrospective.html", title="Retrospective Tasks tree view",
        targets=targets_tree_without_duplicates, ** executive_summary)


@bp.route('/retro/view_epic/<epic_name>')
@flask_login.login_required
def view_epic_retro(epic_name):

    t = retreive_task(epic_name)
    executive_summary = executive_summary_of_points_and_velocity(t.dependents)

    return render_template(
        'epic_view.html', title='View epic', epic=t, ** executive_summary)

