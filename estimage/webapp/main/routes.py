import datetime
import collections

import flask
import flask_login

from . import bp
from . import forms
from .. import web_utils
from ... import data
from ... import utilities, statops
from ...statops import summary
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
    cls, loader = web_utils.get_proj_loader()
    ret = cls.load_metadata(task_id, loader)
    return ret


def retro_retrieve_task(task_id):
    cls, loader = web_utils.get_retro_loader()
    ret = cls.load_metadata(task_id, loader)
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
        web_utils.head_url_for("main.view_projective_task", task_name=task_name))


@bp.route('/authoritative/<task_name>', methods=['POST'])
@flask_login.login_required
def move_consensus_estimate_to_authoritative(task_name):
    form = flask.current_app.get_final_class("AuthoritativeForm")
    if form.validate_on_submit():
        if form.i_kid_you_not.data:
            pollster_cons = webdata.AuthoritativePollster()
            est_input = pollster_cons.ask_points(form.task_name.data)
            estimate = data.Estimate.from_input(est_input)
            form.point_cost.data = str(estimate.expected)
            io_cls = web_utils.get_proj_loader()[1]
            try:
                redhat_compliance.write_some_points(form, io_cls)
            except Exception as exc:
                msg = f"Error updating the record: {exc}"
                flask.flash(msg)
        else:
            flask.flash("Authoritative estimate not updated, request was not serious")

    return flask.redirect(
        web_utils.head_url_for("main.view_projective_task", task_name=task_name))


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
        web_utils.head_url_for("main.view_projective_task", task_name=task_name))


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


def get_similar_cards_with_estimations(user_id, task_name):
    cls, loader = web_utils.get_proj_loader()
    all_cards = loader.get_loaded_cards_by_id(cls)
    cls, loader = web_utils.get_retro_loader()
    all_cards.update(loader.get_loaded_cards_by_id(cls))

    similar_cards = []
    similar_tasks = get_similar_tasks(user_id, task_name, all_cards)
    for task in similar_tasks:
        card = all_cards[task.name]
        card.point_estimate = task.nominal_point_estimate
        similar_cards.append(card)
    return similar_cards


@bp.route('/projective/task/<task_name>')
@flask_login.login_required
def view_projective_task(task_name):
    t = projective_retrieve_task(task_name)

    request_forms = dict(
        estimation=forms.NumberEstimationForm(),
        consensus=forms.ConsensusForm(),
        authoritative=flask.current_app.get_final_class("AuthoritativeForm")(),
    )
    breadcrumbs = get_projective_breadcrumbs()
    append_card_to_breadcrumbs(breadcrumbs, t, lambda n: web_utils.head_url_for("main.view_epic", epic_name=n))
    return view_task(t, breadcrumbs, request_forms)


@bp.route('/retrospective/task/<task_name>')
@flask_login.login_required
def view_retro_task(task_name):
    t = retro_retrieve_task(task_name)

    breadcrumbs = get_retro_breadcrumbs()
    append_card_to_breadcrumbs(breadcrumbs, t, lambda n: web_utils.head_url_for("main.view_epic_retro", epic_name=n))
    return view_task(t, breadcrumbs)


def _setup_forms_according_to_context(request_forms, context):
    if context.own_estimation_exists:
        request_forms["estimation"].enable_delete_button()
        request_forms["consensus"].enable_submit_button()
    if context.global_estimation_exists:
        request_forms["consensus"].enable_delete_button()
        request_forms["authoritative"].clear_to_go()
        request_forms["authoritative"].task_name.data = context.task_name
        request_forms["authoritative"].point_cost.data = ""

    if context.estimation_source == "none":
        fallback_estimation = data.Estimate.from_input(data.EstimInput(context.task_point_cost))
        feed_estimation_to_form(fallback_estimation, request_forms["estimation"])
    else:
        feed_estimation_to_form(context.estimation, request_forms["estimation"])


def view_task(task, breadcrumbs, request_forms=None):
    user = flask_login.current_user
    user_id = user.get_id()
    pollster = webdata.UserPollster(user_id)

    c_pollster = webdata.AuthoritativePollster()
    context = webdata.Context(task)
    give_data_to_context(context, pollster, c_pollster)

    if request_forms:
        _setup_forms_according_to_context(request_forms, context)

    similar_cards = []
    if context.estimation_source != "none":
        similar_cards = get_similar_cards_with_estimations(user_id, task.name)

    return web_utils.render_template(
        'issue_view.html', title='Estimate Issue', breadcrumbs=breadcrumbs,
        user=user, forms=request_forms, task=task, context=context, similar_sized_cards=similar_cards)


def get_projective_breadcrumbs():
    breadcrumbs = collections.OrderedDict()
    breadcrumbs["Planning"] = web_utils.head_url_for("main.tree_view")
    return breadcrumbs


def get_retro_breadcrumbs():
    breadcrumbs = collections.OrderedDict()
    breadcrumbs["Retrospective"] = web_utils.head_url_for("main.tree_view_retro")
    return breadcrumbs


def append_parent_to_breadcrumbs(breadcrumbs, card, name_to_url):
    if card.parent:
        append_parent_to_breadcrumbs(breadcrumbs, card.parent, name_to_url)
    breadcrumbs[card.name] = name_to_url(card.name)


def append_card_to_breadcrumbs(breadcrumbs, card, name_to_url):
    append_parent_to_breadcrumbs(breadcrumbs, card, name_to_url)
    breadcrumbs[card.name] = None


@bp.route('/projective/epic/<epic_name>')
@flask_login.login_required
def view_epic(epic_name):
    user = flask_login.current_user

    user_id = user.get_id()
    cls, loader = web_utils.get_proj_loader()
    all_cards = loader.load_all_cards(cls)
    cards_tree_without_duplicates = utilities.reduce_subsets_from_sets(all_cards)
    model = web_utils.get_user_model(user_id, cards_tree_without_duplicates)

    estimate = model.nominal_point_estimate_of(epic_name)

    t = projective_retrieve_task(epic_name)

    refresh_form = redhat_compliance.forms.RedhatComplianceRefreshForm()
    refresh_form.request_refresh_of([epic_name] + [e.name for e in t.children])
    refresh_form.mode.data = "projective"
    refresh_form.next.data = flask.request.path

    breadcrumbs = get_projective_breadcrumbs()
    append_card_to_breadcrumbs(breadcrumbs, t, lambda n: web_utils.head_url_for("main.view_epic", epic_name=n))

    return web_utils.render_template(
        'epic_view.html', title='View epic', epic=t, estimate=estimate, model=model, breadcrumbs=breadcrumbs,
        refresh_form=refresh_form)


def get_similar_tasks(user_id, task_name, all_cards_by_id):
    all_tasks = []
    all_cards = list(all_cards_by_id.values())
    cards_tree_without_duplicates = utilities.reduce_subsets_from_sets(all_cards)
    model = web_utils.get_user_model(user_id, cards_tree_without_duplicates)
    all_tasks.extend(model.get_all_task_models())
    return webdata.order_nearby_tasks(model.get_element(task_name), all_tasks, 0.5, 2)


@bp.route('/')
def index():
    return flask.redirect(web_utils.head_url_for("main.overview_retro"))


@bp.route('/refresh', methods=["POST"])
@flask_login.login_required
def refresh():
    form = redhat_compliance.forms.RedhatComplianceRefreshForm()
    if form.validate_on_submit():
        if form.mode.data == "projective":
            io_cls = web_utils.get_proj_loader()[1]
        else:
            io_cls = web_utils.get_retro_loader()[1]
        try:
            redhat_compliance.refresh_cards(
                form.get_what_names_to_refresh(), io_cls, form.token.data)
        except Exception as exc:
            msg = f"Error doing refresh: {exc}"
            flask.flash(msg)
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

    all_cards_by_id, model = web_utils.get_all_tasks_by_id_and_user_model("proj", user_id)
    all_cards = list(all_cards_by_id.values())
    cards_tree_without_duplicates = utilities.reduce_subsets_from_sets(all_cards)
    return web_utils.render_template(
        "tree_view.html", title="Tasks tree view",
        cards=cards_tree_without_duplicates, model=model)


def executive_summary_of_points_and_velocity(cards, cls=history.Summary):
    all_events = webdata.EventManager()
    all_events.load()

    start, end = flask.current_app.get_config_option("RETROSPECTIVE_PERIOD")
    cutoff_date = min(datetime.datetime.today(), end)
    statuses = flask.current_app.get_final_class("Statuses")()
    aggregation = history.Aggregation.from_cards(cards, start, end, statuses)
    aggregation.process_event_manager(all_events)
    summary = cls(aggregation, cutoff_date)

    return summary


@bp.route('/retrospective')
@flask_login.login_required
def overview_retro():
    user = flask_login.current_user
    user_id = user.get_id()

    all_cards_by_id, model = web_utils.get_all_tasks_by_id_and_user_model("retro", user_id)
    tier0_cards = [t for t in all_cards_by_id.values() if t.tier == 0]
    tier0_cards_tree_without_duplicates = utilities.reduce_subsets_from_sets(tier0_cards)

    summary = executive_summary_of_points_and_velocity(tier0_cards_tree_without_duplicates)

    return web_utils.render_template(
        "retrospective_overview.html",
        title="Retrospective view",
        summary=summary)


@bp.route('/completion')
@flask_login.login_required
def completion():
    user = flask_login.current_user
    user_id = user.get_id()

    all_cards_by_id, model = web_utils.get_all_tasks_by_id_and_user_model("retro", user_id)
    tier0_cards = [t for t in all_cards_by_id.values() if t.tier == 0]
    tier0_cards_tree_without_duplicates = utilities.reduce_subsets_from_sets(tier0_cards)

    summary = executive_summary_of_points_and_velocity(tier0_cards_tree_without_duplicates, statops.summary.StatSummary)

    return web_utils.render_template(
        "completion.html",
        title="Completion projection",
        summary=summary)


@bp.route('/retrospective_tree')
@flask_login.login_required
def tree_view_retro():
    user = flask_login.current_user
    user_id = user.get_id()

    all_cards_by_id, model = web_utils.get_all_tasks_by_id_and_user_model("retro", user_id)
    all_cards = list(all_cards_by_id.values())
    cards_tree_without_duplicates = utilities.reduce_subsets_from_sets(all_cards)

    tier0_cards = [t for t in all_cards_by_id.values() if t.tier == 0]
    tier0_cards_tree_without_duplicates = utilities.reduce_subsets_from_sets(tier0_cards)
    cards_tree_without_duplicates = utilities.reduce_subsets_from_sets(all_cards)

    summary = executive_summary_of_points_and_velocity(tier0_cards_tree_without_duplicates)
    priority_sorted_cards = sorted(cards_tree_without_duplicates, key=lambda x: - x.priority)
    statuses = flask.current_app.get_final_class("Statuses")()

    refresh_form = redhat_compliance.forms.RedhatComplianceRefreshForm()
    refresh_form.request_refresh_of([e.name for e in priority_sorted_cards])
    refresh_form.mode.data = "retrospective"
    refresh_form.next.data = flask.request.path

    return web_utils.render_template(
        "tree_view_retrospective.html",
        title="Retrospective Tasks tree view",
        cards=priority_sorted_cards, today=datetime.datetime.today(), model=model,
        refresh_form=refresh_form, summary=summary, status_of=lambda c: statuses.get(c.status))


@bp.route('/retrospective/epic/<epic_name>')
@flask_login.login_required
def view_epic_retro(epic_name):
    user = flask_login.current_user
    user_id = user.get_id()

    all_cards_by_id, model = web_utils.get_all_tasks_by_id_and_user_model("retro", user_id)
    t = all_cards_by_id[epic_name]

    summary = executive_summary_of_points_and_velocity(t.children)
    breadcrumbs = get_retro_breadcrumbs()
    append_card_to_breadcrumbs(breadcrumbs, t, lambda n: web_utils.head_url_for("main.view_epic_retro", epic_name=n))

    return web_utils.render_template(
        'epic_view_retrospective.html', title='View epic', breadcrumbs=breadcrumbs,
        today=datetime.datetime.today(), epic=t, model=model, summary=summary)
