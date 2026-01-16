History
=======

The historical development functionality has many sides.


Inputs
------

Cards and Events.


Events
++++++

Events are exported by plugins from trackers, they are then saved and loaded, and they are picked up mainly by Timelines.
The export date range range corresponds to the date range expected by individual Timelines.

Aggregation just sorts events based on tasks, and hands them to Progress.

Progress transforms status events to integer events, and then passes all events to timelines.
It also uses events as an interface to set timelines' values.

Timelines simply accept events, and they set values based on those events.


Outputs
-------

Burndown
++++++++

The burndown is wrapped in multiple layers --- Aggregation of Progresses (of individual cards) that are represented by Timelines.

It is typically instantiated from the top: First of all, a tree of cards, timespan and the set of statuses is passed to the `from_cards` function.
There, parent's span is propagated to children.
Then, leaves (all children who don't have children) of supplied cards are identified and used.

Children are converted into Progress.
Basic usage of placeholders takes place, as Progress is defined over a period of time, but we don't know about card's history yet.


Then, events are handled to `process_event_manager`.

Recommendations:

- Treat span as a card property that has to be resolved somehow in the hierarchy, and this should be encoded in some class.
