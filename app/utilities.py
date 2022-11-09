

def reduce_subsets_from_sets(sets):
    reduced = []
    for index, evaluated in enumerate(sets):
        evaluated_not_contained_further = True
        for reference in sets[index + 1:]:
            if evaluated in reference:
                evaluated_not_contained_further = False
                break
        if evaluated_not_contained_further:
            reduced.append(evaluated)
    return reduced


def norm_pdf(values, dx):
    values[:] /= values.sum() * dx
