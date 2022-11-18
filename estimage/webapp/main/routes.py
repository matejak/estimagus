import io

import flask
import flask_login
import werkzeug.urls
import matplotlib

from . import bp
from . import forms
from ... import data
from ... import utilities
from ... import simpledata
from ..users import User


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


@bp.route('/login', methods=['GET', 'POST'])
def login():
    form = forms.LoginForm()
    if form.validate_on_submit():
        user = User(form.username.data)
        flask_login.login_user(user, remember=form.remember_me.data)

        next_page = flask.request.args.get('next')
        if not next_page or werkzeug.urls.url_parse(next_page).netloc != '':
            next_page = flask.url_for('index')
        return flask.redirect(next_page)
    return render_template(
        'login.html', title='Sign In', form=form)


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
    try:
        ret = simpledata.Target.load_metadata(task_id)
    except RuntimeError:
        ret = simpledata.Target()
        ret.name = task_id
        ret.title = f"{task_id} - Task Title"
        ret.description = "task <strong>description</strong>"
    return ret


@bp.route('/consensus/<task_name>', methods=['POST'])
@flask_login.login_required
def move_issue_estimate_to_consensus(task_name):
    user = flask_login.current_user
    user_id = user.get_id()
    form = forms.ConsensusForm()
    if form.validate_on_submit() and form.i_kid_you_not.data:
        pollster_user = simpledata.UserPollster(user_id)
        pollster_cons = simpledata.AuthoritativePollster()

        user_point = pollster_user.ask_points(task_name)
        pollster_cons.tell_points(task_name, user_point)
    else:
        flask.flash("Consensus not updated, request was not serious")

    return flask.redirect(
        flask.url_for("main.view_task", task_name=task_name))


@bp.route('/estimate/<task_name>', methods=['POST'])
@flask_login.login_required
def estimate(task_name):
    user = flask_login.current_user

    user_id = user.get_id()

    form = forms.NumberEstimationForm()
    pollster = simpledata.UserPollster(user_id)

    if form.validate_on_submit():
        tell_pollster_about_obtained_data(pollster, task_name, form)
        return flask.redirect(
            flask.url_for("main.view_task", task_name=task_name))


@bp.route('/view_task/<task_name>')
@flask_login.login_required
def view_task(task_name):
    user = flask_login.current_user

    user_id = user.get_id()
    pollster = simpledata.UserPollster(user_id)
    request_forms = dict(
        estimation=forms.NumberEstimationForm(),
        consensus=forms.ConsensusForm(),
    )

    t = retreive_task(task_name)
    estimation_args = dict()
    estimation = ask_pollster_of_existing_data(pollster, task_name)
    if estimation:
        eform = request_forms["estimation"]
        feed_estimation_to_form_and_arg_dict(estimation, eform, estimation_args)

    if "estimate" in estimation_args:
        supply_similar_tasks(user_id, task_name, estimation_args)

    c_pollster = simpledata.AuthoritativePollster()
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
    all_targets = simpledata.Target.load_all_targets()
    targets_tree_without_duplicates = utilities.reduce_subsets_from_sets(all_targets)
    return targets_tree_without_duplicates


def get_model(targets_tree_without_duplicates=None):
    if not targets_tree_without_duplicates:
        targets_tree_without_duplicates = get_target_tree_with_no_double_occurence()
    main_composition = simpledata.Target.to_tree(targets_tree_without_duplicates)
    model = data.EstiModel()
    model.use_composition(main_composition)
    return model


def get_authoritative_model(targets_tree_without_duplicates=None):
    pollster = simpledata.AuthoritativePollster()
    model = get_model(targets_tree_without_duplicates)
    pollster.inform_results(model.get_all_task_models())
    return model


def get_user_model(user_id, targets_tree_without_duplicates=None):
    pollster = simpledata.UserPollster(user_id)
    model = get_model(targets_tree_without_duplicates)
    pollster.inform_results(model.get_all_task_models())
    return model


def order_nearby_tasks(reference_task, all_tasks, distance_threshold, rank_threshold):
    reference_estimate = reference_task.point_estimate
    expected = reference_estimate.expected

    distance_task_map = dict()
    for t in all_tasks:
        if t.name == reference_task.name:
            continue
        distance = abs(t.point_estimate.expected - expected)
        rank = t.point_estimate.rank_distance(reference_estimate)
        if (distance < distance_threshold or rank < rank_threshold):
            distance_task_map[distance] = t
    distances = sorted(list(distance_task_map.keys()))
    return [distance_task_map[dst] for dst in distances]


def supply_similar_tasks(user_id, task_name, estimation_data):
    model = get_user_model(user_id)
    all_tasks = model.get_all_task_models()
    ordered_tasks = order_nearby_tasks(model.get_element(task_name), all_tasks, 0.5, 2)
    estimation_data["similar_sized_tasks"] = ordered_tasks


@bp.route('/')
@flask_login.login_required
def tree_view():
    user = flask_login.current_user
    user_id = user.get_id()

    targets_tree_without_duplicates = get_target_tree_with_no_double_occurence()
    model = get_user_model(user_id, targets_tree_without_duplicates)
    return render_template(
        "tree_view.html", title="Tasks tree view",
        targets=targets_tree_without_duplicates, model=model)
