Jira Plugin
===========

Any tracker plugin has to do these things:

- Discover issues --- typically using a base query and a set of snowball queries.
- Read attributes and their history --- the Estimagus's preference is in stateless operation, when Estimagus reads everything by means of a query.
- Understand statuses --- Estimagus works with semantic statuses defined by attributes, while trackers often feature statuses or sub-statuses as names.
- Update the tracker --- If somebody uses Estimagus to update size metadata, this needs to be propagated back to the tracker.
- Guard consistency --- Due to Estimagus being a secondary tracker, any updates can cause inconsistencies if somebody updated the tracker before Estimagus or its users found out.


Import of Data
--------------

The :class:`estimagus.plugins.jira.Importer` class is responsible for getting all cards on one place.

What the importer does:

- Extraction of cards with metadata.
- Extraction of events.
- Inheritance handling (one's child is others' parent, inheritance of implicit attributes s.a. priority, tier (?))


Ideas: Event as a data structure
Reconstructor accepts events and can be extended, so it knows how to apply events to respective (?) classes

Typically, the importer imports data, saves (that's the actual handout to the rest of the app), and hands it for further processing (e.g. for visual feedback).

Fitst, it sets the context, because the importer typically imports items for projective and retrospective results, and callers may want (?) to interfere in some way depending on the context.
Given the query, it gets identified items.
It stores them in the ``all_issues_by_name``, however a list of names is also returned to identify what of those ``all_issues_by_name`` are relevant.
Then, it expands them to form a tree.

- Build a map of parents -> children, and by that it completes the tree, and it keeps the map for the future 
- Based on dynamic criteria, it either finds children by asking potential parents who are their children, or it forms a query asking who has an item as a parent.
- In any case, whenever an entry is uncovered, it is added to the global list of entries. 

Sometimes, a subset of subtasks is selected from a parent task.
In those cases, it is likely that virtual parent tasks with limited scope can be useful to simply serve as grouping entities for the purposes of the tasks in the particular query.
For those cases, an ability to go deeper in the tree is also useful, with a stop condition.
It is questionable to what degree is a subsequent completion of the upper part of the tree essential. 


Examples
++++++++

- Task-based sprint: Sprint consisting of only tasks is trivial, perhaps some of the tasks will have subtasks.
- Epic-based sprint: Epic, tasks and whatever else is below gets in the sprint. Easy.
- Task-based sprint, grouped by epics: A task-based sprint, except grouped by epics that may be incomplete.
- Feature-based selection: High-level items, not necessarily decomposed to the last bit.


Recommendation
--------------

Introduce an abstract Tracker.

Assumptions:

- Every tracker item has a unique ID (name), so it is possible to store all tracker items in name-indexed dictionaries.
- Tracker support queries, whatever that means.
- Trackers need a spec to be able to start operating. Typically, that is an URL and a set of credentials.
- Tracker needs a status resolution logic. There can be a set of minimal states (New, In Progress, Done, Abandoned), but generally, set of input and output states is unknown.
