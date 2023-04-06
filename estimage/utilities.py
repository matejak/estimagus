import typing


def _container_in_one_of(reference: typing.Container, sets: typing.Iterable[typing.Container]):
    for candidate in sets:
        if reference in candidate:
            return True
    return False


def reduce_subsets_from_sets(sets: typing.Iterable[typing.Container]):
    """
    Given a sequence of containers, return a reduced sequence of containers
    where no element is contained in other elements
    """
    reduced = []
    for index, evaluated in enumerate(sets):
        if _container_in_one_of(evaluated, sets[index + 1:]):
            continue
        if _container_in_one_of(evaluated, reduced):
            continue
        reduced.append(evaluated)
    return reduced


def norm_pdf(values, dx):
    norming_factor = values.sum() * dx
    if norming_factor:
        values[:] /= norming_factor
