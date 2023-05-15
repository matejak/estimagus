import datetime
import types

import flask
import flask_login

from . import bp
from . import forms
from .. import web_utils
from ... import data
from ... import utilities
from ... import simpledata as webdata
from ... import history
from ...plugins import redhat_compliance


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


def feed_estimation_to_form(estimation, form_data):
    form_data.optimistic.data = estimation.source.optimistic
    form_data.most_likely.data = estimation.source.most_likely
    form_data.pessimistic.data = estimation.source.pessimistic


def projective_retrieve_task(task_id):
    ret = data.BaseTarget.load_metadata(task_id, webdata.ProjTargetIO)
    return ret


def retro_retrieve_task(task_id):
    ret = data.BaseTarget.load_metadata(task_id, webdata.RetroTargetIO)
    return ret


@bp.route('/consensus/<task_name>', methods=['POST'])
@flask_login.login_required
def move_issue_estimate_to_consensus(task_name):
    user = flask_login.current_user
    user_id = user.get_id()
    form = forms.ConsensusForm()
    if form.validate_on_submit():
        if form.submit.data and form.i_kid_you_not.data:
            pollster_user = webdata.UserPollster(user_id)
            pollster_cons = webdata.AuthoritativePollster()

            user_point = pollster_user.ask_points(task_name)
            pollster_cons.tell_points(task_name, user_point)

            if form.forget_own_estimate.data:
                pollster_user.forget_points(task_name)
        elif form.delete.data:
            pollster_cons = webdata.AuthoritativePollster()

            if pollster_cons.knows_points(task_name):
                pollster_cons.forget_points(task_name)
            else:
                flask.flash("Told to forget something that we don't know")
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
        if form.submit.data:
            tell_pollster_about_obtained_data(pollster, task_name, form)
        elif form.delete.data:
            if pollster.knows_points(task_name):
                pollster.forget_points(task_name)
            else:
                flask.flash("Told to forget something that we don't know")
    else:
        msg = "There were following errors: "
        msg += ", ".join(form.get_all_errors())
        flask.flash(msg)
    return flask.redirect(
        flask.url_for("main.view_task", task_name=task_name))


def tell_of_bad_estimation_input(task_name, task_category, message):
    msg = f"Task '{task_name}' has a bad {task_category} estimation record: {message}"
    return msg


def give_data_to_context(context, user_pollster, global_pollster):
    task_name = context.task_name
    try:
        context.process_own_pollster(user_pollster)
    except ValueError as exc:
        msg = tell_of_bad_estimation_input(task_name, "own", str(exc))
        flask.flash(msg)
    try:
        context.process_global_pollster(global_pollster)
    except ValueError as exc:
        msg = tell_of_bad_estimation_input(task_name, "global", str(exc))
        flask.flash(msg)


def get_similar_targets_with_estimations(user_id, task_name):
    similar_targets = []
    similar_tasks = get_similar_tasks(user_id, task_name)

    all_targets = webdata.ProjTargetIO.get_loaded_targets_by_id()
    all_targets.update(webdata.RetroTargetIO.get_loaded_targets_by_id())
    for task in similar_tasks:
        target = all_targets[task.name]
        target.point_estimate = task.nominal_point_estimate
        similar_targets.append(target)
    return similar_targets


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

    c_pollster = webdata.AuthoritativePollster()
    context = webdata.Context(t.name)
    give_data_to_context(context, pollster, c_pollster)

    if context.own_estimation_exists:
        request_forms["estimation"].enable_delete_button()
        request_forms["consensus"].enable_submit_button()
    if context.global_estimation_exists:
        request_forms["consensus"].enable_delete_button()
        request_forms["authoritative"].enable_submit_button()

    similar_targets = []
    if context.estimation_source == "none":
        fallback_estimation = data.Estimate.from_input(data.EstimInput(t.point_cost))
        feed_estimation_to_form(fallback_estimation, request_forms["estimation"])
    else:
        feed_estimation_to_form(context.estimation, request_forms["estimation"])

        similar_targets = get_similar_targets_with_estimations(user_id, task_name)

    return web_utils.render_template(
        'issue_view.html', title='Estimate Issue',
        user=user, forms=request_forms, task=t, context=context, similar_sized_targets=similar_targets)


@bp.route('/projective/epic/<epic_name>')
@flask_login.login_required
def view_epic(epic_name):
    user = flask_login.current_user

    user_id = user.get_id()
    model = web_utils.get_user_model(user_id, webdata.ProjTargetIO)

    estimate = model.nominal_point_estimate_of(epic_name)

    t = projective_retrieve_task(epic_name)

    refresh_form = redhat_compliance.forms.RedhatComplianceRefreshForm()
    refresh_form.request_refresh_of([epic_name] + [e.name for e in t.dependents])
    refresh_form.mode.data = "projective"
    refresh_form.next.data = flask.request.path

    return web_utils.render_template(
        'epic_view.html', title='View epic', epic=t, estimate=estimate, model=model,
        refresh_form=refresh_form)


def get_similar_tasks(user_id, task_name):
    all_tasks = []
    for cls in (webdata.RetroTargetIO, webdata.ProjTargetIO):
        model = web_utils.get_user_model(user_id, cls)
        all_tasks.extend(model.get_all_task_models())
    return webdata.order_nearby_tasks(model.get_element(task_name), all_tasks, 0.5, 2)


@bp.route('/')
def index():
    return flask.redirect(flask.url_for("main.tree_view"))


@bp.route('/refresh', methods=["POST"])
@flask_login.login_required
def refresh():
    form = redhat_compliance.forms.RedhatComplianceRefreshForm()
    if form.validate_on_submit():
        redhat_compliance.refresh_targets(
            form.get_what_names_to_refresh(), form.mode.data, form.token.data)
    redirect = web_utils.safe_url_to_redirect(form.next.data)
    return flask.redirect(redirect)


@bp.route('/refresh_single', methods=["GET"])
@flask_login.login_required
def refresh_single():
    # TODO: The refresh code goes here
    redirect = web_utils.safe_url_to_redirect(flask.request.args.get("next", "/"))
    return flask.redirect(redirect)


@bp.route('/projective')
@flask_login.login_required
def tree_view():
    user = flask_login.current_user
    user_id = user.get_id()

    all_targets = webdata.ProjTargetIO.load_all_targets()
    targets_tree_without_duplicates = utilities.reduce_subsets_from_sets(all_targets)
    model = web_utils.get_user_model(user_id, webdata.ProjTargetIO, targets_tree_without_duplicates)
    return web_utils.render_template(
        "tree_view.html", title="Tasks tree view",
        targets=targets_tree_without_duplicates, model=model)


def executive_summary_of_points_and_velocity(targets):
    all_events = webdata.EventManager()
    all_events.load()

    start, end = flask.current_app.config["RETROSPECTIVE_PERIOD"]
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

    velocity_array = aggregation.get_velocity_array()
    velocity_stdev = velocity_array.var()**0.5
    velocity_stdev_while_working = velocity_array[velocity_array > 0].var() ** 0.5

    output = dict(
        initial_todo=not_done_on_start,
        initial_done=done_on_start,
        last_record=cutoff_data,
        total_days_in_period=(cutoff_date - start).days,
        total_days_while_working=sum(velocity_array > 0),
        velocity_stdev=velocity_stdev,
        velocity_stdev_while_working=velocity_stdev_while_working,
        total_points_done=cutoff_data.done - done_on_start,
    )
    return output


@bp.route('/retrospective')
@flask_login.login_required
def tree_view_retro():
    all_targets = webdata.RetroTargetIO.load_all_targets()
    tier0_targets = [t for t in all_targets if t.tier == 0]
    tier0_targets_tree_without_duplicates = utilities.reduce_subsets_from_sets(tier0_targets)
    targets_tree_without_duplicates = utilities.reduce_subsets_from_sets(all_targets)

    user = flask_login.current_user
    user_id = user.get_id()
    model = web_utils.get_user_model(user_id, webdata.RetroTargetIO, targets_tree_without_duplicates)
    model.update_targets_with_values(tier0_targets_tree_without_duplicates)
    model.update_targets_with_values(targets_tree_without_duplicates)

    summary = executive_summary_of_points_and_velocity(tier0_targets_tree_without_duplicates)
    priority_sorted_targets = sorted(targets_tree_without_duplicates, key=lambda x: - x.priority)

    refresh_form = redhat_compliance.forms.RedhatComplianceRefreshForm()
    refresh_form.request_refresh_of([e.name for e in priority_sorted_targets])
    refresh_form.mode.data = "retrospective"
    refresh_form.next.data = flask.request.path

    return web_utils.render_template(
        "tree_view_retrospective.html",
        title="Retrospective Tasks tree view",
        targets=priority_sorted_targets, today=datetime.datetime.today(), model=model,
        refresh_form=refresh_form, ** summary)


@bp.route('/retrospective/epic/<epic_name>')
@flask_login.login_required
def view_epic_retro(epic_name):
    t = retro_retrieve_task(epic_name)
    executive_summary = executive_summary_of_points_and_velocity(t.dependents)

    user = flask_login.current_user
    user_id = user.get_id()
    model = web_utils.get_user_model(user_id, webdata.RetroTargetIO, [t])

    return web_utils.render_template(
        'epic_view_retrospective.html', title='View epic',
        today=datetime.datetime.today(), epic=t, model=model, ** executive_summary)


@bp.route('/plugins/jira', methods=("GET", "POST"))
@flask_login.login_required
def jira_plugin():
    from estimage import plugins
    import estimage.plugins.jira
    import estimage.plugins.jira.forms

    form = estimage.plugins.jira.forms.JiraForm()
    if form.validate_on_submit():

        task_spec = plugins.jira.InputSpec.from_dict(form)
        plugins.jira.do_stuff(task_spec)

    return web_utils.render_template(
        'jira.html', title='Jira Plugin', plugin_form=form, )


@bp.route('/plugins/rhcompliance', methods=("GET", "POST"))
@flask_login.login_required
def rhcompliance_plugin():
    from estimage import plugins
    import estimage.plugins.redhat_compliance
    import estimage.plugins.redhat_compliance.forms

    form = estimage.plugins.redhat_compliance.forms.RedhatComplianceForm()
    if form.validate_on_submit():

        task_spec = plugins.redhat_compliance.InputSpec.from_dict(form)
        plugins.redhat_compliance.do_stuff(task_spec)

    return web_utils.render_template(
        'rhcompliance.html', title='Red Hat Compliacne Plugin', plugin_form=form, )
