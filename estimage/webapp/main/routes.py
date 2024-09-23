import flask
import flask_login

from . import bp
from . import forms, cards
from .. import web_utils, routers
from ... import data


def tell_pollster_about_obtained_data(pollster, task_id, form_data):
    est = data.EstimInput(form_data.most_likely.data)
    est.pessimistic = form_data.pessimistic.data
    est.optimistic = form_data.optimistic.data
    pollster.tell_points(task_id, est)


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

    return cards.view_projective_task(task_name, dict(authoritative=form))


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
