import datetime
import dataclasses
import collections

import flask
import flask_login

from . import bp, forms
from .. import web_utils, routers
from ... import simpledata as webdata
from ... import history
from ... import data
from ... import utilities, statops, PluginResolver


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


def feed_estimation_to_form(estimation, form_data):
    form_data.optimistic.data = estimation.source.optimistic
    form_data.most_likely.data = estimation.source.most_likely
    form_data.pessimistic.data = estimation.source.pessimistic


def view_task(task_name, breadcrumbs, mode, card_details=None):
    card_r = routers.CardRouter(mode=mode)
    task = card_r.all_cards_by_id[task_name]

    name_to_url = lambda n: web_utils.head_url_for(f"main.view_epic_{mode}", epic_name=n)
    append_card_to_breadcrumbs(breadcrumbs, task, name_to_url)

    poll_r = routers.PollsterRouter()
    pollster = poll_r.private_pollster
    c_pollster = poll_r.global_pollster

    context = webdata.Context(task)
    give_data_to_context(context, pollster, c_pollster)

    if card_details:
        card_details.setup_forms_according_to_context(context, task)

    similar_cards = []
    if context.estimation_source != "none":
        similar_cards = get_similar_cards_with_estimations(task_name)
        LIMIT = 8
        similar_cards["proj"] = similar_cards["proj"][:LIMIT]
        similar_cards["retro"] = similar_cards["retro"][:LIMIT - len(similar_cards["proj"])]

    return web_utils.render_template(
        'issue_view.html', title='Estimate Issue', breadcrumbs=breadcrumbs, mode=mode,
        user=poll_r.user, card_details=card_details, task=task, context=context, similar_sized_cards=similar_cards)


def get_projective_breadcrumbs():
    breadcrumbs = collections.OrderedDict()
    breadcrumbs["Planning"] = web_utils.head_url_for("main.tree_view")
    return breadcrumbs


def get_retro_breadcrumbs():
    breadcrumbs = collections.OrderedDict()
    breadcrumbs["Retrospective"] = web_utils.head_url_for("main.tree_view_retro")
    return breadcrumbs


@dataclasses.dataclass
class Section:
    name: str
    title: str


@PluginResolver.class_is_extendable("ProjectiveForms")
class ProjectiveDetails:
    def __init__(self):
        self.forms = dict()
        self.sections_by_priority = dict()
        self._known_section_names = set()
        self.add_sections()

    def get_category(self, name):
        for section in self.sections_by_priority.values():
            if section.name == name:
                return section
        msg = f"Couldn't find category '{name}', knows only {list(self._known_section_names)}"
        raise KeyError(msg)

    @property
    def ordered_sections(self):
        ordered_keys = sorted(self.sections_by_priority.keys())
        ordered_values = [self.sections_by_priority[key] for key in ordered_keys]
        return ordered_values

    def _add_section(self, priority, ** kwargs):
        section = Section(** kwargs)
        self.sections_by_priority[priority] = section
        self._known_section_names.add(kwargs["name"])

    def add_sections(self):
        self._add_section(10, name="estimation", title="Estimation")

    def instantiate_forms(self, app):
        self.forms["estimation"] = forms.SimpleEstimationForm()
        self.forms["authoritative"] = app.get_final_class("AuthoritativeForm")()

    def setup_forms_according_to_context(self, context, card):
        if context.own_estimation_exists:
            self.forms["estimation"].enable_delete_button()
        if context.global_estimation_exists:
            self.forms["authoritative"].clear_to_go()
            self.forms["authoritative"].task_name.data = context.task_name
            self.forms["authoritative"].point_cost.data = ""

        if context.estimation_source == "none":
            fallback_estimation = data.Estimate.from_input(data.EstimInput(context.task_point_cost))
            feed_estimation_to_form(fallback_estimation, self.forms["estimation"])
        else:
            feed_estimation_to_form(context.estimation, self.forms["estimation"])


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


@bp.route('/projective/task/<task_name>')
@flask_login.login_required
def view_projective_task(task_name, known_forms=None):
    if known_forms is None:
        known_forms = dict()

    card_details = flask.current_app.get_final_class("ProjectiveForms")()
    card_details.instantiate_forms(flask.current_app)
    card_details.forms.update(known_forms)

    breadcrumbs = get_projective_breadcrumbs()
    return view_task(task_name, breadcrumbs, "proj", card_details)


@bp.route('/retrospective/task/<task_name>')
@flask_login.login_required
def view_retro_task(task_name):
    breadcrumbs = get_retro_breadcrumbs()
    return view_task(task_name, breadcrumbs, "retro")


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


def executive_summary_of_points_and_velocity(agg_router, cards, cls=history.Summary):
    aggregation = agg_router.get_aggregation_of_cards(cards)
    lower_boundary_of_end = aggregation.end
    if lower_boundary_of_end is None:
        lower_boundary_of_end = datetime.datetime.today()
    cutoff_date = min(datetime.datetime.today(), lower_boundary_of_end)
    summary = cls(aggregation, cutoff_date)

    return summary


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


def tell_of_bad_estimation_input(task_name, task_category, message):
    msg = f"Task '{task_name}' has a bad {task_category} estimation record: {message}"
    return msg


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


def get_similar_tasks(model_router, ref_task):
    model = model_router.model
    all_tasks = model.get_all_task_models()
    return webdata.order_nearby_tasks(ref_task, all_tasks, 0.5, 2)
