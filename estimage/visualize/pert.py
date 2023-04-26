from . import utils


def handle_border_discontinuities(ax, pert):
    if pert[1, 0] != 0:
        ax.scatter(pert[0, 0], pert[1, 0], ec="b", fc="b", lw=2, zorder=3)
        ax.scatter(pert[0, 0], 0, ec="b", fc="w", lw=2, zorder=3)
    if pert[1, -1] != 0:
        ax.scatter(pert[0, -1], pert[1, -1], ec="b", fc="b", lw=2, zorder=3)
        ax.scatter(pert[0, -1], 0, ec="b", fc="w", lw=2, zorder=3)


def plot_continuous_pert(ax, pert, expected, task_name):
    ax.plot(pert[0], pert[1], 'b-', lw=2, label=f'task {task_name}')
    limits = ax.get_xlim()
    ax.plot((limits[0], pert[0, 0]), (0, 0), 'b-', lw=2, scaley=False)
    ax.plot((pert[0, -1], limits[1]), (0, 0), 'b-', lw=2, scaley=False)
    handle_border_discontinuities(ax, pert)
    ax.axvline(expected, color="orange", label="expected value")
    ax.set_xlim(limits)


def plot_delta_pert(ax, pert, expected, task_name):
    dom = pert[0]
    ax.axhline(0, color='blue', lw=2, label=f'task {task_name}')
    ax.axvline(expected, color="orange", label="expected value", zorder=2)
    # ax.arrow(expected, 0, 0, 1, fc='b', ec="b", lw=2, width=0.01, zorder=2)
    ax.set_ylim(-0.1, 1.1)
    ax.set_xlim(max(dom[0], -0.1), max(dom[-1], 0))
    ax.annotate(
        "", xy=(expected, 1), xycoords='data', xytext=(expected, 0), textcoords='data',
        arrowprops=dict(arrowstyle="->", connectionstyle="arc3", ec="b", lw=2), zorder=4)
    ax.scatter(expected, 0, ec="b", fc="w", lw=2, zorder=3)


def get_pert_in_figure(estimation, task_name):
    pert = estimation.get_pert()
    plt = utils.get_standard_pyplot()

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
