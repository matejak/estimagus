[![Maintainability](https://api.codeclimate.com/v1/badges/dcb33e05b41d668a1b3e/maintainability)](https://codeclimate.com/github/matejak/estimagus/maintainability)
[![Test Coverage](https://api.codeclimate.com/v1/badges/dcb33e05b41d668a1b3e/test_coverage)](https://codeclimate.com/github/matejak/estimagus/test_coverage)
[![Gitter chat](https://badges.gitter.im/gitterHQ/gitter.png)](https://app.gitter.im/#/room/#estimagus:gitter.im)

# Estimagus

Estimagus is a framework and a decision support web application focused on estimation of tasks, on evaluation of progress and on identification of bottlenecks when working on projects that can be decomposed into a tree of tasks.

Estimagus can be extended to synchronize with trackers s.a. Jira, and operate on local copy of the data, possibly synchronizing updates back to the tracker.


## Quickstart

You can run the application locally, or you can utilize containers to get it up and running.

In any case, a running app without testing data is no fun, so you want to run the `create_sample_data.py` script that will output a bunch of `ini` files that can serve as sample data.
Still, it is not particularly fun, so perhaps join Gitter and find out how to get some real data from your tracker.


### Running in the live system

Install Python dependencies listed in `requirements.txt.in` - the easiest way is to run `pip install -r requirements.txt.in` in a Python virtual environment.
Then, execute

```
SECRET_KEY=abcd DATA_DIR=. python -m flask run
```

and voila - you should be able to connect to http://localhost:5000, and start exploring the app.
The `$DATA_DIR/appdata.ini` file contains additional configuration that can be edited.


### Running in a container

See the `examples/docker-compose.yml` file - everything is there.
Create a directory `data`, and put those sample ini files in it.
The compose file is set up to mount the data directory to the container where it expects the data to be.

Anyway, after running `docker-compose up estimagus`, you should be able to connect to http://localhost:5000, and start exploring the app.


## Single-head vs multihead

Estimagus can operate support more independent views - typically multiple projects, or historical snapshots of a project.
The switch between single- and multi-head operation is the `DATA_DIRS` environmental variable - if supplied, the app will launch in a multi-head mode.
From the usability perspective, accessing the root will always put you on track.


## Configuration

Following environmental variables are recognized and used:

- `SECRET_KEY`: Has to be set to a string, preferably a long and random one. Needed for persistence of user logins.
- `DATA_DIR`: Where the single-head app should look for the data.
- `DATA_DIRS`: An ordered, comma-separated list of directories with configuration and data of "heads" for the multi-head setup.
- `LOGIN_PROVIDER_NAME`: one of `autologin` or `google`. Autologin logs in any user, google allows Google login when set up properly.
- `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`: When using google login, you need to obtain those from Google to have the Google login working.
- `PLUGINS`: An ordered, comma-separated list of plugin names to load. Plugins are Python packages located in the `plugins` directory of Estimagus.


## Assumptions

Some assumptions are hard, while others may be subjects to change.

### Terms

*Card* is a node in the task tree of the project.
Therefore, it can be a task, or a collection of tasks.


### Planning

- Any task's size can be expressed as an amount of "points" - whatever that means.
  A point is the only unit available at a time, it can reflect e.g. relative difficulty or time cost, but one can't have both quantities next to each other.
- Task can be meaningfully estimated using a (possibly degenerate) three-point estimate (optimistic, most likely, pessimistic) interval that covers the actual value with an estimated probability of about 95%.
  It is therefore possible (with about 5% probability) that the actual case is worse than pessimistic, or better than optimistic.
- The expected time when a card is supposed to be worked on can be set statically by specifying start and end dates.
  This enables individual projections of the on-track state on the level of cards.
- Task sizes are a linear quantity, and a size of a card that has children is exactly the sum of sizes of its children.
  In other words, the size of work on an epic can be estimated by adding up (whatever that means) estimations of individual tasks.
  Notably, integration of work between individual tasks is therefore factored in task estimates.


### Execution

- Tasks are being worked on when the task's state is "In Progress".
- The expected value of task's estimate corresponds to the work that has been done on the task when it is completed.
- There is no way how to directly measure the rate of progress (velocity) before completing a card.
  The velocity can only be measured indirectly based on the estimated size and time spent in progress.
- The velocity is constant when the task is in progress.
- Execution of each tasks is an independent event.
  Tasks may depend on each other, but how relatively smoothly will a task flow can't be deduced from execution of other tasks.
- If anything, the history of reestimations is not relevant, the last number is what counts.
- It is impossible to find out who or how many people worked to complete a task.


## Features

### TLDR

- Conduct smooth planning:

  - Leverage the 3-point estimation technique to produce aggregate estimations with quantitative confidence.
  - Offer similar issues for reference when conducting the planning.

- Know what's going on during the execution phase:

  - View status-aware burndown charts on the global scale, or on a finer scale of composite cards (epics).
  - View velocity data on all scales as well.

- Plan better next time: Use past velocity to convert story points to time estimations including the corresponding quantitative confidence.


### Concepts

#### Projective view

The tool allows individuals to estimate issues using the 3-point estimation technique.
Their estimates are private, but they can be promoted to global, concensus estimates that are visible to everybody.
Authoritative estimates reflect the actual entry stored in the tracking system that the team is using.


#### Retrospective view

The tool visualizes progress and velocity of issues that are currently being worked on.
