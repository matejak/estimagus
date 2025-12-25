Concepts
========

Most of the entities described here can be extended by the Estimagus Plugin System.


Card
----

:class:`estimage.entities.card.BaseCard` is an objective element of project management, typically a task or a container (epic, feature) in issue trackers.
A Card is defined by a set of fields, and idetnitfied by its ``name``.
Cards can have other cards as children.

.. warning::

   Cards should only form trees, but technically, they can form cycled graphs, where a card is a parent and a child of itself at the same time.
   Estimagus doesn't handle cycles --- it is your responsibility to prevent this from happening.

Typically, cards are imported from issue trackers, where there is a 1:1 relationship between tracker entities and an Estimagus ``Card``.
The "level" of a Card is not of any interest to Estimagus, as Cards should form a tree structure, where leaves are tasks-level items, and all other nodes are containers.


Status
------

Cards can have a :class:`estimage.entities.status.Status`.
Status is defined by its attributes, and identified by its ``name``.
The purpose of an Estimagus Status is to define properties of a status and forget about its name while it is being processed.

There can be numerous different statuses that are equivalent, because they have the same attributes.
A class ``Statuses`` is a "manager" of statuses for the use case in question, and ensures that tasks are processed consistently.
For example, some classes want to represent a status as an ordinal, and Statuses does this without requiring anything from the Status class.


Model
-----

While a Card is an entry, it doesn't interact with other Cards.
Model is a class that is able to take cards, and establish the tree graph structure on them.

For example, a Card can have a size assigned in the tracker.
However, the Model can ask more entities about its size --- if a card is a container, its real size is given by considering the sum of sizes of its children that are not yet completed.
If the card is a task, then there may be a 3-point estimate available for it, which the tracker may not support natively.


Estimate
--------

Estimate is a three-point estimate of a scalar quantity.
It can be degenerate, when all three quantities equal each other, in which case it behaves as a number.
It can be constructed by supplying the most likely, optimistic, pessimistic values given the parameter :math:`\gamma`,
or it can be a result of an operation between existing estimates.


History
-------

To visualize historical development, there are three concepts,
Aggregation, Progress and Timeline.
We start by the simplest, and continue our way upwards.


Event
+++++

Event is a counterpart to Card --- it is something that happened to the card at some point.
Events can be imported from a tracker s.a. Jira.


Timeline
++++++++

Timeline is an array that samples quantity in time.
The quantity may be size estimate, status, or a relevance of the entity in question.

Although timeline is a simple concept, it is the basis of everything, and there are numerous tricky matters:

- Calculation of values by processing events.
- Interpolation of quantity by working with fixed dates with expected values (expected start of work, deadline).


Progress
++++++++

Progress consists of multiple timelines.
Typically, we are interested in size and status, but projection or relevance of a represented item is also important.
