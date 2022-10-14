import math

import pytest

import app.data as tm


def test_storage():
    el = tm.BaseTarget()
    cost = el.point_cost
    assert cost >= 0

    cost2 = el.time_cost
    assert cost >= 0
    
    
    assert el.parse_point_cost("5") == 5
    
    el.TIME_UNIT = "pw"
    assert el.parse_time_cost("5pw") == 5
    assert el.parse_time_cost("5 pw") == 5
    
    assert el.format_time_cost(8.2) == "8 pw"
    

def test_estimate():
    est = tm.Estimate.from_triple(5, 3, 8)
    assert est.expected > 5
    

def test_composition():
    c = tm.Composition("c")
    assert c.time_estimate.expected == 0
    assert c.point_estimate.expected == 0
    
    e1 = tm.Result("foo")
    e1.point_estimate = tm.Estimate(2, 1)
    e1.time_estimate = tm.Estimate(1, 1)
    
    c.add_element(e1)
    assert c.point_estimate.expected == 2
    
    c2 = tm.Composition("c2")
    c2.add_element(e1)
    c2.add_element(e1)
    assert c2.point_estimate.expected == 4
    assert c2.point_estimate.sigma == math.sqrt(2)
    c.add_composition(c2)
    assert c.point_estimate.expected == 6
    assert c.time_estimate.expected == 3
    
    e1.nullify()
    assert e1.point_estimate.expected == 0
    
    

def test_supply():
    est = tm.Estimator()

    e1 = tm.Result("foo")
    est.add_element(e1)
    
    user_input = tm.EstimInput(1)
    
    est.estimate_points_of("foo", user_input)
    assert est.main_composition.point_estimate.expected == 1

    user_input = tm.EstimInput(2)

    est.estimate_time_of("foo", user_input)
    assert est.main_composition.time_estimate.expected == 2
    
    with pytest.raises(RuntimeError):
        est.add_element(e1)
    
    target = est.export_element("foo")
    assert target.point_cost == 1
    assert target.time_cost == 2

    assert est.main_composition.time_estimate.expected == 2
    
    est.complete_element("foo")
    assert est.main_composition.point_estimate.expected == 0
    assert est.main_composition.time_estimate.expected == 0
    
    est.new_element("bar")
    est.estimate_points_of("bar", user_input)
    assert est.main_composition.point_estimate.expected == 2
    

def test_poll():
    pollster = tm.MemoryPollster()

    point_input = pollster.ask_points("foo")
    assert point_input.most_likely == 0

    hint = tm.EstimInput(1)

    pollster.tell_points("foo", hint)
    point_input = pollster.ask_points("foo")

    assert point_input.most_likely == 1
    

def test_integrate():
    pollster = tm.MemoryPollster()
    est = tm.Estimator()

    name1 = "foo"
    e1 = tm.Result(name1)
    est.add_element(e1)
    
    pollster.tell_points(name1, tm.EstimInput(3))
    user_point_input = pollster.ask_points(name1)
    est.estimate_points_of(name1, user_point_input)

    name2 = "bar"
    e2 = tm.Result(name2)
    est.add_element(e2)
    
    pollster.tell_points(name2, tm.EstimInput(5))
    user_point_input = pollster.ask_points(name2)
    
    est.estimate_points_of(name2, user_point_input)
    
    assert e1.point_estimate.expected == 3
    assert e1.point_estimate.variance == 0
    assert e2.point_estimate.expected == 5

    assert est.main_composition.point_estimate.expected == 8
    assert est.main_composition.point_estimate.variance == 0

                         
def test_memory_types():
    r1 = tm.MemoryResult("R")
    r1.set_point_estimate(3, 2, 4)
    r1.save()
    r1.set_point_estimate(2, 1, 3)
    
    r2 = tm.MemoryResult("RR")
    r2.set_time_estimate(3, 2, 4)
    r2.save()
    
    r12 = tm.MemoryResult.load("R")
    assert r12.point_estimate.expected == 3
    r1.save()
    r12 = tm.MemoryResult.load("R")
    assert r12.point_estimate.expected == r1.point_estimate.expected
    
    r22 = tm.MemoryResult.load("RR")
    assert r22.time_estimate.expected == 3
    
    c1 = tm.MemoryComposition("C")
    c1.add_element(r1)
    c2 = tm.MemoryComposition("D")
    c1.add_composition(c2)
    c2.add_element(r2)
    
    c1.save()
    c3 = tm.MemoryComposition.load("C")
    assert c3.elements[0].point_estimate.expected == r1.point_estimate.expected
    c4 = c3.compositions[0]
    assert c4.elements[0].time_estimate.expected == r2.time_estimate.expected

    