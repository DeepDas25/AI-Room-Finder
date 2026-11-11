"""Campus Graph and Admissible Heuristic for Route Finding.

Represents the university campus as an undirected weighted graph and provides
an admissible heuristic function h(n) = 5 * (minimum hop count to goal),
leveraging the fact that every edge in the campus graph has weight >= 5 metres.
"""

from collections import deque
from typing import Dict, Set, Optional

# Standard building nodes in the campus graph
CAMPUS_BUILDINGS: Set[str] = {"EB1", "EB2", "TB", "IM"}

# Undirected weighted graph: node -> {neighbor: weight_in_metres}
CAMPUS_GRAPH: Dict[str, Dict[str, float]] = {
    "EB1": {
        "EB2": 5.0,
        "TB": 10.0,
        "IM": 40.0,
    },
    "EB2": {
        "EB1": 5.0,
        "IM": 50.0,
    },
    "TB": {
        "EB1": 10.0,
    },
    "IM": {
        "EB1": 40.0,
        "EB2": 50.0,
    },
}

# The minimum edge weight across the entire graph (5.0 metres)
MIN_EDGE_WEIGHT: float = 5.0


def _min_hops(start: str, goal: str) -> Optional[int]:
    """Calculate the minimum number of edges (unweighted shortest-path hop count)
    between start and goal using Breadth-First Search (BFS).

    Returns:
        int: Minimum number of edges between start and goal.
        None: If either node is not in the graph or no path exists.
    """
    if start not in CAMPUS_GRAPH or goal not in CAMPUS_GRAPH:
        return None

    if start == goal:
        return 0

    queue = deque([(start, 0)])
    visited = {start}

    while queue:
        current, hops = queue.popleft()
        if current == goal:
            return hops

        for neighbor in CAMPUS_GRAPH[current]:
            if neighbor not in visited:
                visited.add(neighbor)
                queue.append((neighbor, hops + 1))

    return None


def heuristic(current: str, goal: str) -> float:
    """Calculate the admissible heuristic h(n) for A* search.

    Formula:
        h(n) = MIN_EDGE_WEIGHT * (minimum hops from current to goal)
             = 5 * (minimum number of edges)

    Properties:
        - h(goal, goal) = 0.
        - Admissibility: Since every edge in the graph has a physical distance
          >= 5 metres, min_hops * 5 can never exceed the true shortest weighted
          path distance (h(n) <= h*(n)).
        - Consistency (monotonicity): For any edge (u, v) with weight w:
          h(u) <= w + h(v) because min_hops(u, goal) <= 1 + min_hops(v, goal)
          and w >= 5.

    Args:
        current: Source building identifier (e.g. 'EB1', 'EB2', 'TB', 'IM').
        goal: Destination building identifier.

    Returns:
        float: Estimated distance in metres.

    Raises:
        ValueError: If current or goal is not a known building code in CAMPUS_GRAPH.
    """
    if current not in CAMPUS_GRAPH:
        raise ValueError(f"Unknown building code '{current}'. Known buildings: {sorted(CAMPUS_BUILDINGS)}")
    if goal not in CAMPUS_GRAPH:
        raise ValueError(f"Unknown building code '{goal}'. Known buildings: {sorted(CAMPUS_BUILDINGS)}")

    if current == goal:
        return 0.0

    hops = _min_hops(current, goal)
    if hops is None:
        raise ValueError(f"No path exists between '{current}' and '{goal}'.")

    return float(MIN_EDGE_WEIGHT * hops)

