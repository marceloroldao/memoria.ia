from memoria_resolutiva.ordered import compare_ordered
from memoria_resolutiva.trajectory import Occurrence


def make(memory_id, times, nodes):
    return [Occurrence(memory_id, 0, t, n) for t, n in zip(times, nodes)]


reference = make("reference", [0, 1, 2, 3], ["A", "B", "C", "D"])
same = make("same", [0, 1, 2, 3], ["A", "B", "C", "D"])
reordered = make("reordered", [0, 1, 2, 3], ["D", "C", "B", "A"])
stretched = make("stretched", [0, 2, 5, 9], ["A", "B", "C", "D"])

for candidate in [same, reordered, stretched]:
    result = compare_ordered(reference, candidate)
    print(candidate[0].memory_id, result)
