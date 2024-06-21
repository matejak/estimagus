import datetime
import collections

import flask
import flask_login

from . import bp
from . import forms
from .. import web_utils, routers
from ... import data
from ... import utilities, statops
from ...statops import summary
from ... import simpledata as webdata
from ... import history, problems
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


def _move_estimate_from_private_to_global(form, task_name, pollster_router):
    user_point = pollster_router.private_pollster.ask_points(task_name)
    pollster_router.global_pollster.tell_points(task_name, user_point)

    if form.forget_own_estimate.data:
        pollster_router.private_pollster.forget_points(task_name)


def _delete_global_estimate(task_name, pollster_router):
    pollster_cons = pollster_router.global_pollster

    if pollster_cons.knows_points(task_name):
        pollster_cons.forget_points(task_name)
    else:
        flask.flash("Told to forget something that we don't know")


@bp.route('/consensus/<task_name>', methods=['POST'])
@flask_login.login_required
def act_on_global_estimate(task_name):
    r = routers.PollsterRouter()
    form = forms.ConsensusForm()
    if form.validate_on_submit():
        if form.submit.data and form.i_kid_you_not.data:
            _move_estimate_from_private_to_global(form, task_name, r)
        elif form.delete.data:
            _delete_global_estimate(task_name, r)
        else:
            flask.flash("Consensus not updated, request was not serious")

    return flask.redirect(
        web_utils.head_url_for("main.view_projective_task", task_name=task_name))


def _update_tracker_and_local_point_cost(card_name, io_cls, form):
    card_cls = flask.current_app.get_final_class("BaseCard")
    card = card_cls.load_metadata(card_name, io_cls)
    new_cost = form.get_point_cost()
    synchro = flask.current_app.get_final_class("CardSynchronizer").from_form(form)
    synchro.set_tracker_points_of(card, new_cost, io_cls)


@bp.route('/authoritative/<task_name>', methods=['POST'])
@flask_login.login_required
def move_consensus_estimate_to_authoritative(task_name):
    form = flask.current_app.get_final_class("AuthoritativeForm")()
    if form.validate_on_submit():
        r = routers.PollsterRouter()
        est_input = r.global_pollster.ask_points(form.task_name.data)
        estimate = data.Estimate.from_input(est_input)
        form.point_cost.data = str(estimate.expected)
        io_cls = routers.IORouter().get_card_io("proj")
        try:
            _update_tracker_and_local_point_cost(task_name, io_cls, form)
        except Exception as exc:
            msg = f"Error updating the record: {exc}"
            flask.flash(msg)

    return view_projective_task(task_name, dict(authoritative=form))


def _attempt_record_of_estimate(task_name, form, pollster):
    if form.submit.data:
        tell_pollster_about_obtained_data(pollster, task_name, form)
    elif form.delete.data:
        if pollster.knows_points(task_name):
            pollster.forget_points(task_name)
        else:
            flask.flash("Told to forget something that we don't know")


@bp.route('/estimate/<task_name>', methods=['POST'])
@flask_login.login_required
def estimate(task_name):
    r = routers.PollsterRouter()
    pollster = r.global_pollster
    form = forms.SimpleEstimationForm()

    if form.validate_on_submit():
        _attempt_record_of_estimate(task_name, form, pollster)
        if r.private_pollster.knows_points(task_name):
            r.private_pollster.forget_points(task_name)
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


def get_similar_cards_with_estimations(task_name):
    rs = dict(
        proj=routers.ModelRouter(mode="proj"),
        retro=routers.ModelRouter(mode="retro"),
    )
    ref_task = rs["proj"].model.get_element(task_name)

    ret = dict()
    for mode in ("proj", "retro"):
        similar_cards = []

        r = rs[mode]
        similar_tasks = get_similar_tasks(r, ref_task)
        for task in similar_tasks:
            card = r.all_cards_by_id[task.name]
            card.point_estimate = task.nominal_point_estimate
            similar_cards.append(card)
        ret[mode] = similar_cards
    return ret


@bp.route('/projective/task/<task_name>')
@flask_login.login_required
def view_projective_task(task_name, known_forms=None):
    if known_forms is None:
        known_forms = dict()

    request_forms = dict(
        estimation=forms.SimpleEstimationForm(),
        authoritative=flask.current_app.get_final_class("AuthoritativeForm")(),
    )
    request_forms.update(known_forms)

    breadcrumbs = get_projective_breadcrumbs()
    return view_task(task_name, breadcrumbs, "proj", request_forms)


@bp.route('/retrospective/task/<task_name>')
@flask_login.login_required
def view_retro_task(task_name):
    breadcrumbs = get_retro_breadcrumbs()
    return view_task(task_name, breadcrumbs, "retro")


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


def _setup_simple_forms_according_to_context(request_forms, context):
    if context.own_estimation_exists:
        request_forms["estimation"].enable_delete_button()
    if context.global_estimation_exists:
        request_forms["authoritative"].clear_to_go()
        request_forms["authoritative"].task_name.data = context.task_name
        request_forms["authoritative"].point_cost.data = ""

    if context.estimation_source == "none":
        fallback_estimation = data.Estimate.from_input(data.EstimInput(context.task_point_cost))
        feed_estimation_to_form(fallback_estimation, request_forms["estimation"])
    else:
        feed_estimation_to_form(context.estimation, request_forms["estimation"])


def view_task(task_name, breadcrumbs, mode, request_forms=None):
    card_r = routers.CardRouter(mode=mode)
    task = card_r.all_cards_by_id[task_name]

    name_to_url = lambda n: web_utils.head_url_for(f"main.view_epic_{mode}", epic_name=n)
    append_card_to_breadcrumbs(breadcrumbs, task, name_to_url)

    poll_r = routers.PollsterRouter()
    pollster = poll_r.private_pollster
    c_pollster = poll_r.global_pollster

    context = webdata.Context(task)
    give_data_to_context(context, pollster, c_pollster)

    if request_forms:
        _setup_simple_forms_according_to_context(request_forms, context)

    similar_cards = []
    if context.estimation_source != "none":
        similar_cards = get_similar_cards_with_estimations(task_name)
        LIMIT = 8
        similar_cards["proj"] = similar_cards["proj"][:LIMIT]
        similar_cards["retro"] = similar_cards["retro"][:LIMIT - len(similar_cards["proj"])]

    return web_utils.render_template(
        'issue_view.html', title='Estimate Issue', breadcrumbs=breadcrumbs, mode=mode,
        user=poll_r.user, forms=request_forms, task=task, context=context, similar_sized_cards=similar_cards)


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
def view_epic_proj(epic_name):
    r = routers.ModelRouter(mode="proj")

    estimate = r.model.nominal_point_estimate_of(epic_name)

    t = r.all_cards_by_id[epic_name]

    breadcrumbs = get_projective_breadcrumbs()
    append_card_to_breadcrumbs(breadcrumbs, t, lambda n: web_utils.head_url_for("main.view_epic_proj", epic_name=n))

    return web_utils.render_template(
        'epic_view_projective.html', title='View epic', epic=t, estimate=estimate, model=r.model, breadcrumbs=breadcrumbs,
    )


def get_similar_tasks(model_router, ref_task):
    model = model_router.model
    all_tasks = model.get_all_task_models()
    return webdata.order_nearby_tasks(ref_task, all_tasks, 0.5, 2)


@bp.route('/')
def index():
    return flask.redirect(web_utils.head_url_for("main.overview_retro"))


@bp.route('/projective')
@flask_login.login_required
def tree_view():
    r = routers.ModelRouter(mode="proj")
    return web_utils.render_template(
        "tree_view.html", title="Tasks tree view",
        cards=r.cards_tree_without_duplicates, model=r.model)


def executive_summary_of_points_and_velocity(agg_router, cards, cls=history.Summary):
    aggregation = agg_router.get_aggregation_of_cards(cards)
    lower_boundary_of_end = aggregation.end
    if lower_boundary_of_end is None:
        lower_boundary_of_end = datetime.datetime.today()
    cutoff_date = min(datetime.datetime.today(), lower_boundary_of_end)
    summary = cls(aggregation, cutoff_date)

    return summary


@bp.route('/retrospective')
@flask_login.login_required
def overview_retro():
    r = routers.AggregationRouter(mode="retro")

    tier0_cards = [t for t in r.all_cards_by_id.values() if t.tier == 0]
    tier0_cards_tree_without_duplicates = utilities.reduce_subsets_from_sets(tier0_cards)

    summary = executive_summary_of_points_and_velocity(r, tier0_cards_tree_without_duplicates)

    return web_utils.render_template(
        "retrospective_overview.html",
        title="Retrospective view",
        summary=summary)


@bp.route('/completion')
@flask_login.login_required
def completion():
    r = routers.AggregationRouter(mode="retro")

    tier0_cards = [t for t in r.all_cards_by_id.values() if t.tier == 0]
    tier0_cards_tree_without_duplicates = utilities.reduce_subsets_from_sets(tier0_cards)

    summary = executive_summary_of_points_and_velocity(r, tier0_cards_tree_without_duplicates, statops.summary.StatSummary)

    return web_utils.render_template(
        "completion.html",
        title="Completion projection",
        summary=summary)


@bp.route('/retrospective_tree')
@flask_login.login_required
def tree_view_retro():
    r = routers.AggregationRouter(mode="retro")

    tier0_cards = [t for t in r.all_cards_by_id.values() if t.tier == 0]
    tier0_cards_tree_without_duplicates = utilities.reduce_subsets_from_sets(tier0_cards)

    summary = executive_summary_of_points_and_velocity(r, tier0_cards_tree_without_duplicates)
    priority_sorted_cards = sorted(r.cards_tree_without_duplicates, key=lambda x: - x.priority)

    return web_utils.render_template(
        "tree_view_retrospective.html",
        title="Retrospective Tasks tree view",
        cards=priority_sorted_cards, today=datetime.datetime.today(), model=r.model,
        summary=summary, status_of=lambda c: r.statuses.get(c.status))


@bp.route('/retrospective/epic/<epic_name>')
@flask_login.login_required
def view_epic_retro(epic_name):
    r = routers.AggregationRouter(mode="retro")

    t = r.all_cards_by_id[epic_name]

    summary = executive_summary_of_points_and_velocity(r, t.children)
    breadcrumbs = get_retro_breadcrumbs()
    append_card_to_breadcrumbs(breadcrumbs, t, lambda n: web_utils.head_url_for("main.view_epic_retro", epic_name=n))

    return web_utils.render_template(
        'epic_view_retrospective.html', title='View epic', breadcrumbs=breadcrumbs,
        today=datetime.datetime.today(), epic=t, model=r.model, summary=summary)


@bp.route('/problems')
@flask_login.login_required
def view_problems():
    r = routers.ProblemRouter(mode="proj")
    categories = r.classifier.get_categories_with_problems()

    cat_forms = []
    for cat in categories:
        probs = r.classifier.classified_problems[cat.name].values()

        form = flask.current_app.get_final_class("ProblemForm")(prefix=cat.name)
        form.add_problems_and_cat(cat, probs)

        cat_forms.append((cat, form))

    return web_utils.render_template(
        'problems.html', title='Problems', category_forms=[cf[1] for cf in cat_forms],
        all_cards_by_id=r.all_cards_by_id, catforms=cat_forms)


def _solve_problem(solution, card, synchro, io_cls):
    try:
        solution.solve(card, synchro, io_cls)
    except Exception as exc:
        msg = f"Failed to solve problem of {card.name}: {exc}"
        flask.flash(msg)


def _solve_problem_category(form, classifier, all_cards_by_id, io_cls):
    cat_name = form.problem_category.data
    problems_cat = classifier.CATEGORIES[cat_name]
    if not problems_cat.solution.solvable:
        flask.flash(f"Problem of kind '{cat_name}' can't be solved automatically.")
    else:
        synchro = flask.current_app.get_final_class("CardSynchronizer").from_form(form)
        for name in form.problems.data:
            problem = classifier.classified_problems[cat_name][name]
            solution = problems_cat.solution(problem)
            _solve_problem(solution, all_cards_by_id[name], synchro, io_cls)


@bp.route('/problems/fix/<category>', methods=['POST'])
@flask_login.login_required
def fix_problems(category):
    r = routers.ProblemRouter(mode="proj")

    form = flask.current_app.get_final_class("ProblemForm")(prefix=category)
    form.add_problems(r.problem_detector.problems)
    if form.validate_on_submit():
        _solve_problem_category(form, r.classifier, r.all_cards_by_id, r.cards_io)
    else:
        flask.flash(f"Error handing over solution: {form.errors}")
    return flask.redirect(
        web_utils.head_url_for("main.view_problems"))
