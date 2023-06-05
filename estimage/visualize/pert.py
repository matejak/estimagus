from .. import PluginResolver

from . import utils


@PluginResolver.class_is_extendable("PertPlotter")
class PertPlotter:
    PERT_COLOR="blue"
    EXPECTED_COLOR="orange"

    def __init__(self, task_name: str, estimation):
        self.pert = estimation.get_pert()
        self.task_name = task_name
        self.estimation = estimation
        self.expected = self.estimation.expected

    def handle_border_discontinuities(self, ax):
        display_kwargs = dict(
            ec=self.PERT_COLOR, lw=2,
        )
        domain, values = self.pert
        if values[0] != 0:
            ax.scatter(domain[0], values[0], fc=self.PERT_COLOR, zorder=3, ** display_kwargs)
            ax.scatter(domain[0], 0, fc="white", ** display_kwargs, zorder=3)
        if values[-1] != 0:
            ax.scatter(domain[-1], values[-1], fc=self.PERT_COLOR, ** display_kwargs, zorder=3)
            ax.scatter(domain[-1], 0, fc="white", ** display_kwargs, zorder=3)

    def plot_continuous_pert(self, ax):
        domain, values = self.pert
        ax.plot(domain, values, c=self.PERT_COLOR, lw=2, label=f'task {self.task_name}')
        limits = ax.get_xlim()
        ax.plot((limits[0], domain[0]), (0, 0), c=self.PERT_COLOR, lw=2)
        ax.plot((domain[-1], limits[1]), (0, 0), c=self.PERT_COLOR, lw=2)
        self.handle_border_discontinuities(ax)
        ax.axvline(self.expected, c=self.EXPECTED_COLOR, label="expected value")
        ax.set_xlim(limits)

    def plot_delta_pert(self, ax):
        domain = self.pert[0]
        ax.axhline(0, color=self.PERT_COLOR, lw=2, label=f'task {self.task_name}')
        ax.axvline(self.expected, c=self.EXPECTED_COLOR, label="expected value", zorder=2)
        ax.set_ylim(-0.1, 1.1)
        ax.set_xlim(max(domain[0], -0.1), max(domain[-1], 0))
        ax.annotate(
            "", xy=(self.expected, 1), xycoords='data', xytext=(self.expected, 0), textcoords='data',
            arrowprops=dict(arrowstyle="->", connectionstyle="arc3", ec=self.PERT_COLOR, lw=2), zorder=4)
        ax.scatter(self.expected, 0, ec="b", fc="w", lw=2, zorder=3)

    def plot_any_pert(self, ax):
        if self.estimation.sigma == 0:
            self.plot_delta_pert(ax)
        else:
            self.plot_continuous_pert(ax)


def get_pert_in_figure(estimation, task_name, cls=None):
    if not cls:
        cls = PertPlotter
    plt = utils.get_standard_pyplot()

    fig, ax = plt.subplots(1, 1)

    plotter = cls(task_name, estimation)
    plotter.plot_any_pert(ax)

    ax.set_xlabel("points")
    ax.set_ylabel("probability density")
    ax.set_yticklabels([])
    ax.grid()
    ax.legend()

    return fig
