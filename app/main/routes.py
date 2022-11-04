import flask
import flask_login

from . import bp
from .forms import LoginForm, PointEstimationForm, NumberEstimationForm
from .. import data
from .. import simpledata
from ..users import User


def render_template(template_basename, title, **kwargs):
    authenticated_user = ""
    if flask_login.current_user.is_authenticated:
        authenticated_user = flask_login.current_user
    return flask.render_template(
        template_basename, title=title, authenticated_user=authenticated_user, ** kwargs)


@bp.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user = User(form.username.data)
        flask_login.login_user(user, remember=form.remember_me.data)
        return flask.redirect("/")
    return render_template(
        'login.html', title='Sign In', form=form)


def tell_pollster_about_obtained_data(pollster, task_id, form_data):
    est = data.EstimInput(form_data.most_likely.data)
    est.pessimistic = form_data.pessimistic.data
    est.optimistic = form_data.optimistic.data
    pollster.tell_points(task_id, est)


def ask_pollster_of_existing_data(pollster, task_id, form_data):
    task_estimates = pollster.ask_points(task_id)
    estimation_arg = dict()
    if task_estimates:
        form_data.optimistic.data = task_estimates.optimistic
        form_data.most_likely.data = task_estimates.most_likely
        form_data.pessimistic.data = task_estimates.pessimistic

        est = data.Estimate.from_triple(
            float(task_estimates.most_likely),
            float(task_estimates.optimistic),
            float(task_estimates.pessimistic))

        estimation_arg["estimate"] = est

    return estimation_arg


def retreive_task(task_id):
    try:
        ret = simpledata.Target.load_metadata(task_id)
    except RuntimeError:
        ret = simpledata.Target()
        ret.name = task_id
        ret.title = f"{task_id} - Task Title"
        ret.description = "task <strong>description</strong>"
    return ret


@flask_login.login_required
@bp.route('/estimate/<task_name>', methods=['GET', 'POST'])
def estimate(task_name):
    user = flask_login.current_user

    user_id = user.get_id()
    pollster = simpledata.Pollster(user_id)
    form = NumberEstimationForm()
    if form.validate_on_submit():
        tell_pollster_about_obtained_data(pollster, task_name, form)
        return flask.redirect(flask.url_for("main.estimate", task_name=task_name))

    t = retreive_task(task_name)
    estimation_args = ask_pollster_of_existing_data(pollster, task_name, form)
    if estimation_args:
        supply_similar_tasks(user_id, task_name, estimation_args)
    return render_template(
        'issue_view.html', title='Estimate Issue', user=user, form=form, task=t, ** estimation_args)


@flask_login.login_required
@bp.route('/view/<epic_name>')
def view(epic_name):
    user = flask_login.current_user

    user_id = user.get_id()
    model = get_custom_model(user_id)

    t = retreive_task(epic_name)

    return render_template(
        'epic_view.html', title='View epic', epic=t, estimate=model.point_estimate_of(epic_name))


def get_reduced_targets():
    all_targets = simpledata.Target.load_all_targets()
    reduced_targets = data.reduce_subsets_from_sets(all_targets)
    return reduced_targets


def get_model(reduced_targets=None):
    if not reduced_targets:
        reduced_targets = get_reduced_targets()
    main_composition = simpledata.Target.to_tree(reduced_targets)
    model = data.EstiModel()
    model.use_composition(main_composition)
    return model


def get_custom_model(user_id, reduced_targets=None):
    pollster = simpledata.Pollster(user_id)
    model = get_model(reduced_targets)
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
    model = get_custom_model(user_id)
    all_tasks = model.get_all_task_models()
    ordered_tasks = order_nearby_tasks(model.get_element(task_name), all_tasks, 0.5, 2)
    estimation_data["similar_sized_tasks"] = ordered_tasks


@flask_login.login_required
@bp.route('/')
def tree_view():
    user = flask_login.current_user
    user_id = user.get_id()

    reduced_targets = get_reduced_targets()
    model = get_custom_model(user_id, reduced_targets)
    return render_template(
        "tree_view.html", title="Tasks tree view", targets=reduced_targets, model=model)
