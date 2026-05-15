from algo_union import heuristic_algorithm as _algo_union_heuristic_algorithm


def heuristic_algorithm(instance_file="data/instance05.txt", *args, **kwargs):
    kwargs.setdefault("max_seconds", 9.5)
    return _algo_union_heuristic_algorithm(instance_file, *args, **kwargs)
