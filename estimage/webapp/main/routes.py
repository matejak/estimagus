import io
import cProfile
import functools

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


def profile(wrapped):
    """
    Decorate a function to save profiling info to the working directory.
    The order of decorators matters.
    """
    @functools.wraps(wrapped)
    def wrapper(* args, ** kwargs):
        with cProfile.Profile() as pr:
            ret = wrapped(* args, ** kwargs)
            pr.dump_stats(f"{wrapped.__name__}.pstats")
        return ret
    return wrapper


def render_template(template_basename, title, **kwargs):
    authenticated_user = ""
    if flask_login.current_user.is_authenticated:
        authenticated_user = flask_login.current_user
    return flask.render_template(
        template_basename, title=title, authenticated_user=authenticated_user, ** kwargs)


@bp.route('/logout', methods=['GET'])
def logout():
    flask_login.logout_user()
    return flask.redirect(flask.url_for("main.login"))


def autologin(safe_next_page):
    form = forms.AutoLoginForm()
    if form.validate_on_submit():
        user = User(form.username.data)
        flask_login.login_user(user, remember=form.remember_me.data)
        return flask.redirect(safe_next_page)
    login_provider = flask.current_app.config["LOGIN_PROVIDER_NAME"]
    return render_template(
        'login.html', title='Sign In', login_form=form,
        next=safe_next_page, login_provider=login_provider)


@bp.route('/login', methods=['GET', 'POST'])
def login():
    config_dict = flask.current_app.config

    next_page = flask.request.args.get('next')
    if not next_page or werkzeug.urls.url_parse(next_page).netloc != '':
        next_page = flask.url_for('main.tree_view')

    match provider_name := config_dict["LOGIN_PROVIDER_NAME"]:
        case "autologin":
            return autologin(next_page)
        case "google":
            return google_login(next_page)
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


def projective_retrieve_task(task_id):
    ret = webdata.ProjTarget.load_metadata(task_id)
    ret.load_point_cost()
    return ret


def retro_retrieve_task(task_id):
    ret = webdata.RetroTarget.load_metadata(task_id)
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
    targets = webdata.ProjTarget.get_loaded_targets_by_id()
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


@bp.route('/projective/task/<task_name>')
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

    t = projective_retrieve_task(task_name)
    estimation_args = dict()
    estimation = ask_pollster_of_existing_data(pollster, task_name)
    if estimation:
        eform = request_forms["estimation"]
        feed_estimation_to_form_and_arg_dict(estimation, eform, estimation_args)

    if "estimate" in estimation_args:
        similar_tasks = get_similar_tasks(user_id, task_name)
        estimation_args["similar_sized_tasks"] = similar_tasks
        all_targets = webdata.ProjTarget.get_loaded_targets_by_id()
        all_targets.update(webdata.RetroTarget.get_loaded_targets_by_id())
        estimation_args["similar_sized_targets"] = [
            all_targets[task.name] for task in similar_tasks
        ]

        c_pollster = webdata.AuthoritativePollster()
        con_input = c_pollster.ask_points(task_name)
        estimation_args["consensus"] = data.Estimate.from_input(con_input)

    return render_template(
        'issue_view.html', title='Estimate Issue',
        user=user, forms=request_forms, task=t, ** estimation_args)


@bp.route('/projective/epic/<epic_name>')
@flask_login.login_required
def view_epic(epic_name):
    user = flask_login.current_user

    user_id = user.get_id()
    model = get_user_model(user_id, webdata.ProjTarget)

    t = projective_retrieve_task(epic_name)

    return render_template(
        'epic_view.html', title='View epic', epic=t, model=model)


def send_figure_as_png(figure, basename):
    filename = basename + ".png"

    bytesio = io.BytesIO()
    figure.savefig(bytesio, format="png", bbox_inches='tight')
    import matplotlib.pyplot as plt
    plt.close(figure)
    bytesio.seek(0)

    return flask.send_file(bytesio, download_name=filename, mimetype="image/png")


def send_figure_as_svg(figure, basename):
    filename = basename + ".svg"

    bytesio = io.BytesIO()
    figure.savefig(bytesio, pad_inches=0, dpi="figure", format="svg", bbox_inches='tight')
    import matplotlib.pyplot as plt
    plt.close(figure)
    bytesio.seek(0)

    return flask.send_file(bytesio, download_name=filename, mimetype="image/svg+xml")


def get_pert_in_figure(estimation, task_name):
    pert = estimation.get_pert()

    plt.rcParams['svg.fonttype'] = 'none'
    plt.rcParams['font.sans-serif'] = (
        "system-ui", "-apple-system", "Segoe UI", "Roboto", "Helvetica Neue", "Noto Sans", "Liberation Sans",
        "Arial,sans-serif" ,"Apple Color Emoji", "Segoe UI Emoji", "Segoe UI Symbol", "Noto Color Emoji",
    )
    plt.rcParams['font.size'] = 12

    fig, ax = plt.subplots(1, 1)
    if estimation.sigma == 0:
        plot_delta_pert(ax, pert, estimation.expected, task_name)
    else:
        plot_continuous_pert(ax, pert, estimation.expected, task_name)

    ax.set_xlabel("points")
    ax.set_ylabel("probability density")
    ax.set_yticklabels([])
    ax.grid()
    ax.legend()

    return fig


def plot_continuous_pert(ax, pert, expected, task_name):
    ax.plot(pert[0], pert[1], 'b-', lw=2, label=f'task {task_name}')
    ax.axvline(expected, color="orange", label="expected value")


def plot_delta_pert(ax, pert, expected, task_name):
    dom = pert[0]
    ax.plot(dom, 0 * dom, 'b-', lw=2, label=f'task {task_name}')
    ax.axvline(expected, color="orange", label="expected value", zorder=2)
    # ax.arrow(expected, 0, 0, 1, fc='b', ec="b", lw=2, width=0.01, zorder=2)
    ax.set_ylim(-0.1, 1.1)
    ax.set_xlim(max(dom[0], -0.1), max(dom[-1], 0))
    ax.annotate(
        "", xy=(expected, 1), xycoords='data', xytext=(expected, 0), textcoords='data',
        arrowprops=dict(arrowstyle="->", connectionstyle="arc3", ec="b", lw=2), zorder=4)
    ax.scatter(expected, 0, ec="b", fc="w", lw=2, zorder=3)


@bp.route('/vis/<epic_name>-<size>-burndown.svg')
@flask_login.login_required
def visualize_burndown(epic_name, size):
    assert size in ("small", "normal")
    all_targets = webdata.RetroTarget.get_loaded_targets_by_id()
    target_tree = utilities.reduce_subsets_from_sets(list(all_targets.values()))
    all_events = webdata.EventManager.load()

    start = flask.current_app.config["PERIOD"]["start"]
    end = flask.current_app.config["PERIOD"]["end"]

    if epic_name == ".":
        aggregation = history.Aggregation.from_targets(target_tree, start, end)
    else:
        epic = all_targets[epic_name]
        aggregation = history.Aggregation.from_target(epic, start, end)

    aggregation.process_event_manager(all_events)

    if size == "small":
        fig = history.MPLPointPlot(aggregation).get_small_figure()
    else:
        fig = history.MPLPointPlot(aggregation).get_figure()
    return send_figure_as_svg(fig, epic_name)


@bp.route('/vis/<epic_name>-velocity.svg')
@flask_login.login_required
def visualize_velocity(epic_name):
    all_targets = webdata.RetroTarget.get_loaded_targets_by_id()
    target_tree = utilities.reduce_subsets_from_sets(list(all_targets.values()))
    all_events = webdata.EventManager.load()

    start = flask.current_app.config["PERIOD"]["start"]
    end = flask.current_app.config["PERIOD"]["end"]

    if epic_name == ".":
        aggregation = history.Aggregation.from_targets(target_tree, start, end)
    else:
        epic = all_targets[epic_name]
        aggregation = history.Aggregation.from_target(epic, start, end)

    aggregation.process_event_manager(all_events)
    cutoff_date = min(datetime.datetime.today(), end)

    fig = history.MPLVelocityPlot(aggregation).get_figure(cutoff_date)
    fig.set_size_inches(6.0, 4.4)
    return send_figure_as_svg(fig, epic_name)


@bp.route('/vis/<task_name>-pert.svg')
@flask_login.login_required
def visualize_task(task_name):
    user = flask_login.current_user

    user_id = user.get_id()
    model = get_user_model(user_id, webdata.ProjTarget)
    if task_name == ".":
        estimation = model.nominal_point_estimate
    else:
        estimation = model.nominal_point_estimate_of(task_name)

    fig = get_pert_in_figure(estimation, task_name)

    return send_figure_as_svg(fig, task_name)


def get_target_tree_with_no_double_occurence(cls):
    all_targets = cls.load_all_targets()
    targets_tree_without_duplicates = utilities.reduce_subsets_from_sets(all_targets)
    return targets_tree_without_duplicates


def get_user_model(user_id, cls, targets_tree_without_duplicates=None):
    if targets_tree_without_duplicates is None:
        targets_tree_without_duplicates = get_target_tree_with_no_double_occurence(cls)
    authoritative_pollster = webdata.AuthoritativePollster()
    user_pollster = webdata.UserPollster(user_id)
    model = webdata.get_model(targets_tree_without_duplicates)
    authoritative_pollster.inform_results(model.get_all_task_models())
    user_pollster.inform_results(model.get_all_task_models())
    return model


def get_similar_tasks(user_id, task_name):
    all_tasks = []
    for cls in (webdata.RetroTarget, webdata.ProjTarget):
        model = get_user_model(user_id, cls)
        all_tasks.extend(model.get_all_task_models())
    return webdata.order_nearby_tasks(model.get_element(task_name), all_tasks, 0.5, 2)


@bp.route('/')
def index():
    return flask.redirect(flask.url_for("main.tree_view"))


@bp.route('/projective')
@flask_login.login_required
def tree_view():
    user = flask_login.current_user
    user_id = user.get_id()

    all_targets = webdata.ProjTarget.load_all_targets()
    targets_tree_without_duplicates = utilities.reduce_subsets_from_sets(all_targets)
    model = get_user_model(user_id, webdata.ProjTarget, targets_tree_without_duplicates)
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

    done_on_start = 0
    not_done_on_start = 0
    cutoff_data = types.SimpleNamespace(todo=0, underway=0, done=0)
    for r in aggregation.repres:
        repre_points = r.get_points_at(start)
        if r.get_status_at(start) in (data.State.todo, data.State.in_progress, data.State.review):
            not_done_on_start += repre_points
        elif r.get_status_at(start) == data.State.done:
            done_on_start += repre_points

        if r.get_status_at(cutoff_date) == data.State.todo:
            cutoff_data.todo += repre_points
        elif r.get_status_at(cutoff_date) in (data.State.in_progress, data.State.review):
            cutoff_data.underway += repre_points
        elif r.get_status_at(cutoff_date) == data.State.done:
            cutoff_data.done += repre_points

    output = dict(
        initial_todo=not_done_on_start,
        initial_done=not_done_on_start,
        last_record=cutoff_data,
        total_days_in_period=(cutoff_date - start).days,
        total_days_while_working=sum(aggregation.get_velocity_array() > 0),
        total_points_done=cutoff_data.done - done_on_start,
    )
    return output


@bp.route('/retrospective')
@flask_login.login_required
def tree_view_retro():
    all_targets = webdata.RetroTarget.load_all_targets()
    targets_tree_without_duplicates = utilities.reduce_subsets_from_sets(all_targets)
    executive_summary = executive_summary_of_points_and_velocity(targets_tree_without_duplicates)

    user = flask_login.current_user
    user_id = user.get_id()
    model = get_user_model(user_id, webdata.RetroTarget, targets_tree_without_duplicates)

    priority_sorted_targets = sorted(targets_tree_without_duplicates, key=lambda x: - x.priority)

    return render_template(
        "tree_view_retrospective.html", title="Retrospective Tasks tree view",
        targets=priority_sorted_targets, today=datetime.datetime.today(), model=model, ** executive_summary)


@bp.route('/retrospective/epic/<epic_name>')
@flask_login.login_required
def view_epic_retro(epic_name):
    t = retro_retrieve_task(epic_name)
    executive_summary = executive_summary_of_points_and_velocity(t.dependents)

    user = flask_login.current_user
    user_id = user.get_id()
    model = get_user_model(user_id, webdata.RetroTarget, [t])

    return render_template(
        'epic_view_retrospective.html', title='View epic',
        today=datetime.datetime.today(), epic=t, model=model, ** executive_summary)


@bp.route('/plugins/jira', methods=("GET", "POST"))
@flask_login.login_required
def jira_plugin():
    form = forms.JiraForm()
    if form.validate_on_submit():

        from estimage import plugins
        import estimage.plugins.jira
        task_spec = plugins.jira.InputSpec.from_dict(form)
        plugins.jira.do_stuff(task_spec)

    return render_template(
        'jira.html', title='Jira Plugin', plugin_form=form, )
