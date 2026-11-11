"""A* Search Algorithm for Campus Route Finding.

Finds the shortest walking path between campus buildings using standard A* search:
    f(n) = g(n) + h(n)
where:
    g(n) is the exact accumulated weighted path distance from the start node,
    h(n) is the admissible heuristic from src.campus_graph.heuristic,
    f(n) is the estimated total route cost through node n.
"""

import heapq
from typing import Dict, List, Optional, Any
from src.campus_graph import CAMPUS_GRAPH, heuristic


def find_shortest_route(start: str, goal: str) -> Dict[str, Any]:
    """Find the shortest route between two campus buildings using A* search.

    Args:
        start: Starting building code (e.g. 'EB1', 'EB2', 'TB', 'IM').
        goal: Destination building code.

    Returns:
        Dict[str, Any] containing:
            - 'path': List[str] of building codes from start to goal.
            - 'total_distance': float total walking distance in metres.

    Raises:
        ValueError: If start or goal is not a known building code, or if no route exists.
    """
    if start not in CAMPUS_GRAPH:
        known = sorted(CAMPUS_GRAPH.keys())
        raise ValueError(f"Unknown start building code '{start}'. Known buildings: {known}")
    if goal not in CAMPUS_GRAPH:
        known = sorted(CAMPUS_GRAPH.keys())
        raise ValueError(f"Unknown goal building code '{goal}'. Known buildings: {known}")

    # Handle same start and destination immediately
    if start == goal:
        return {
            "path": [start],
            "total_distance": 0.0,
        }

    # Priority queue stores tuples: (f_score, counter, current_node)
    # Counter ensures deterministic tie-breaking without comparing node strings directly
    entry_counter = 0
    start_h = heuristic(start, goal)
    open_set: List[tuple] = [(start_h, entry_counter, start)]

    # g_scores: best known cost from start to node
    g_scores: Dict[str, float] = {start: 0.0}

    # came_from: for path reconstruction
    came_from: Dict[str, str] = {}

    # closed_set: nodes already expanded with their optimal g_score
    visited: set = set()

    while open_set:
        current_f, _, current = heapq.heappop(open_set)

        if current in visited:
            continue
        visited.add(current)

        # Stop condition: destination popped from priority queue with optimal cost
        if current == goal:
            # Reconstruct path
            path = []
            curr: Optional[str] = goal
            while curr is not None:
                path.append(curr)
                curr = came_from.get(curr)
            path.reverse()
            return {
                "path": path,
                "total_distance": float(g_scores[goal]),
            }

        # Explore neighbors
        current_g = g_scores[current]
        for neighbor, weight in CAMPUS_GRAPH[current].items():
            tentative_g = current_g + weight

            if tentative_g < g_scores.get(neighbor, float("inf")):
                came_from[neighbor] = current
                g_scores[neighbor] = tentative_g
                h_val = heuristic(neighbor, goal)
                f_score = tentative_g + h_val
                entry_counter += 1
                heapq.heappush(open_set, (f_score, entry_counter, neighbor))

    # If the queue empties without reaching goal
    raise ValueError(f"No route found between '{start}' and '{goal}'.")

