[![Maintainability](https://api.codeclimate.com/v1/badges/dcb33e05b41d668a1b3e/maintainability)](https://codeclimate.com/github/matejak/estimagus/maintainability)
[![Test Coverage](https://api.codeclimate.com/v1/badges/dcb33e05b41d668a1b3e/test_coverage)](https://codeclimate.com/github/matejak/estimagus/test_coverage)
[![Gitter chat](https://badges.gitter.im/gitterHQ/gitter.png)](https://app.gitter.im/#/room/#estimagus:gitter.im)

# Estimagus

Decision support web application focused on estimation of tasks, on evaluation of progress and on identification of bottlenecks.

The software is not complete, so part of this description is rather a wish than the reality.


## Quickstart

You can run the application locally, or you can utilize containers to get it up and running.

In any case, a running app without testing data is no fun, so you want to run the `create_sample_data.py` script that will output a bunch of `ini` files that can serve as sample data.


### Running in the live system

Install Python dependencies listed in `requirements.txt.in` - the easiest way is to run `pip install -r requirements.txt.in` in a Python virtual environment.
Then, execute

```
SECRET_KEY=abcd DATA_DIR=. python -m flask run
```

and voila - you should be able to connect to http://localhost:5000, and start exploring the app.


### Running in a container

See the `examples/docker-compose.yml` file - everything is there.
Create a directory `data`, and put those sample ini files in it.
The compose file is set up to mount the data directory to the container where it expects the data to be.

Anyway, after running `docker-compose up estimagus`, you should be able to connect to http://localhost:5000, and start exploring the app.


## Configuration

Following environmental variables are recognized and used:

- `SECRET_KEY`: Has to be set to a string, preferably a long and random one. Needed for persistence of user logins.
- `DATA_DIR`: Where the app should look for the data.
- `LOGIN_PROVIDER_NAME`: one of `autologin` or `google`. Autologin logs in any user, google allows Google login when set up properly.
- `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`: When using google login, you need to obtain those from Google to have the Google login working.
- `PLUGINS`: An ordered, comma-separated list of plugin names to load.


## Assumptions

### Planning

- Any task's size can be expressed as an amount of "points" - whatever that means.
  A point is the only unit available, it can reflect e.g. relative difficulty or time cost, but one can't have both.
- Task can be meaningfully estimated using a (possibly degenerate) three-point estimate.
- The expected time when the task/epic is supposed to be worked on can be set statically by specifying two dates.
- Task sizes are a linear quantity, and a collection of tasks (epic) doesn't entail anything else besides its tasks.
  The size of work on an epic can be estimated by adding up (whatever that means) estimations of individual tasks.
- The plan and the actual execution are related only through the velocity.
  Velocity is treated as a black box.
  There is no distinction between a team member taking time off and underestimation - both result in temporal reduction of velocity.


### Execution

- Tasks are being worked on when the task's state is "In Progress".
- The expected value of task's estimate corresponds to the work that has been done on the task.
- There is no way how to directly measure the rate of progress (velocity) before concluding an element of work (e.g. task, subtask).
  The velocity can only be measured indirectly based on the estimated size and delivery time.
- The velocity is constant in time while the task is in progress.
- Execution of each tasks is an independent event.
  Tasks may depend on each other, but how relatively smoothly will a task flow can't be deduced from execution of other tasks.
- If the team reestimates anything, the history of reestimations is not relevant.


## Features

### TLDR

- Conduct smooth planning:

  - Leverage the 3-point estimation technique to produce aggregate estimations with quantitative confidence.
  - Offer similar issues for reference when conducting the planning.

- Know what's going on during the execution phase:

  - View status-aware burndown charts in the global scale, or on a finer scale of composite issues (epics).
  - View velocity data on all scales as well.

- Plan better next time: Use past velocity to convert story points to time estimations including the corresponding quantitative confidence.


### Concepts

#### Projective view

The tool allows individuals to estimate issues using the 3-point estimation technique.
Their estimates are private, but they can be promoted to global, concensus estimates that are visible to everybody.
Authoritative estimates reflect the actual entry stored in the tracking system that the team is using.


#### Retrospective view

The tool visualizes progress and velocity of issues that are currently being worked on.


### Driving user stories

- As a sysadmin, I want to be able to set up Estimagus to connect to various task systems, so my customers will be able to estimate on the top of those systems using Estimagus, while being backwards-compatible.
- As a developer, I want to
  - estimate tasks using the 3-point method without interfering with others.
  - export results of my estimations to the main task database, so my estimations can be used by the whole team.
  - see similar tasks when estimating, so I get feedback that can improve my relative estimation.
  - nominate a set of estimations as globally authoritative, so I have access to working versions of 3-point estimates at any time.
  - keep track of history of the authoritative estimation, so reestimates are easily identifiable, and not hidden.
  - work with my estimation and the authoritative estimation if it exists, or at least with a marked estimation as its fallback.
  - express interest on working on an issue or epic, and to review this information, so that I can manage my focus, and I can help others to plan in a way that can consider my contribution preferences.
- As a stakeholder, I want to
  - see the team's burndown charts and velocity charts, so that I know whether the team is in control of things.
  - have projection of the state of things readily available, so that I can correlate it with the team's version and focus on potential differences.
  - identify tasks or epics that are in danger of slipping, so that I can realocate resources in time.

