

def reduce_subsets_from_sets(sets):
    reduced = []
    for index, evaluated in enumerate(sets):
        evaluated_not_contained_elsewhere = True
        for reference in sets[index + 1:] + reduced:
            if evaluated in reference:
                evaluated_not_contained_elsewhere = False
                break
        if evaluated_not_contained_elsewhere:
            reduced.append(evaluated)
    return reduced


def norm_pdf(values, dx):
    values[:] /= values.sum() * dx
