"""Unit tests for Campus Graph representation and Admissible Heuristic."""

import unittest
import heapq
from typing import Dict, List, Tuple
from pathlib import Path
import sys

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from src.campus_graph import (
    CAMPUS_GRAPH,
    CAMPUS_BUILDINGS,
    MIN_EDGE_WEIGHT,
    heuristic,
    _min_hops,
)


def _dijkstra_shortest_distance(start: str, goal: str) -> float:
    """Helper implementing Dijkstra's algorithm to compute exact shortest weighted distance h*(n)."""
    if start == goal:
        return 0.0

    pq: List[Tuple[float, str]] = [(0.0, start)]
    distances: Dict[str, float] = {start: 0.0}

    while pq:
        d, u = heapq.heappop(pq)
        if d > distances.get(u, float("inf")):
            continue
        if u == goal:
            return d

        for v, weight in CAMPUS_GRAPH[u].items():
            new_dist = d + weight
            if new_dist < distances.get(v, float("inf")):
                distances[v] = new_dist
                heapq.heappush(pq, (new_dist, v))

    return distances.get(goal, float("inf"))


class TestCampusGraph(unittest.TestCase):

    def test_buildings_set(self):
        """All expected campus buildings must be present in the graph."""
        expected = {"EB1", "EB2", "TB", "IM"}
        self.assertEqual(CAMPUS_BUILDINGS, expected)
        self.assertEqual(set(CAMPUS_GRAPH.keys()), expected)

    def test_bidirectional_connections_and_weights(self):
        """Verify the exact 4 bidirectional connections and their specified weights."""
        expected_connections = [
            ("EB2", "EB1", 5.0),
            ("EB1", "TB", 10.0),
            ("EB1", "IM", 40.0),
            ("EB2", "IM", 50.0),
        ]

        for u, v, w in expected_connections:
            # Check forward direction
            self.assertIn(v, CAMPUS_GRAPH[u], f"Edge {u} -> {v} must exist.")
            self.assertEqual(CAMPUS_GRAPH[u][v], w, f"Weight of {u} -> {v} must be {w}.")
            # Check reverse direction (undirected graph)
            self.assertIn(u, CAMPUS_GRAPH[v], f"Edge {v} -> {u} must exist.")
            self.assertEqual(CAMPUS_GRAPH[v][u], w, f"Weight of {v} -> {u} must be {w}.")

        # Check total number of directed edges in the adjacency list:
        # EB1 has 3 (EB2, TB, IM), EB2 has 2 (EB1, IM), TB has 1 (EB1), IM has 2 (EB1, EB2) -> total 8 directed entries (4 bidirectional)
        total_directed_edges = sum(len(neighbors) for neighbors in CAMPUS_GRAPH.values())
        self.assertEqual(total_directed_edges, 8)

    def test_heuristic_same_node(self):
        """Heuristic for same source and destination must always return 0."""
        for b in CAMPUS_BUILDINGS:
            h_val = heuristic(b, b)
            self.assertEqual(h_val, 0.0, f"Heuristic({b}, {b}) must be 0.0")

    def test_heuristic_values_known_pairs(self):
        """Check exact heuristic calculation h(n) = 5 * min_hops for specific pairs."""
        # 1-hop pairs -> h = 5.0
        self.assertEqual(heuristic("EB1", "EB2"), 5.0)
        self.assertEqual(heuristic("EB2", "EB1"), 5.0)
        self.assertEqual(heuristic("EB1", "TB"), 5.0)
        self.assertEqual(heuristic("TB", "EB1"), 5.0)
        self.assertEqual(heuristic("EB1", "IM"), 5.0)
        self.assertEqual(heuristic("IM", "EB1"), 5.0)
        self.assertEqual(heuristic("EB2", "IM"), 5.0)
        self.assertEqual(heuristic("IM", "EB2"), 5.0)

        # 2-hop pairs -> h = 10.0
        # TB <-> EB2: path is TB - EB1 - EB2 (2 hops)
        self.assertEqual(_min_hops("TB", "EB2"), 2)
        self.assertEqual(heuristic("TB", "EB2"), 10.0)
        self.assertEqual(heuristic("EB2", "TB"), 10.0)

        # TB <-> IM: path is TB - EB1 - IM (2 hops)
        self.assertEqual(_min_hops("TB", "IM"), 2)
        self.assertEqual(heuristic("TB", "IM"), 10.0)
        self.assertEqual(heuristic("IM", "TB"), 10.0)

    def test_invalid_and_unknown_building_codes(self):
        """Invalid or unknown building codes must raise ValueError."""
        invalid_codes = ["", "XYZ", "EB3", "LIBRARY", None, 123]
        for code in invalid_codes:
            with self.assertRaises(ValueError):
                heuristic(code, "EB1")
            with self.assertRaises(ValueError):
                heuristic("EB1", code)

    def test_heuristic_admissibility_all_pairs(self):
        """Heuristic must be admissible: for every pair (u, v), h(u, v) <= true_shortest_distance(u, v)."""
        buildings = sorted(CAMPUS_BUILDINGS)
        for u in buildings:
            for v in buildings:
                h_val = heuristic(u, v)
                actual_dist = _dijkstra_shortest_distance(u, v)
                self.assertLessEqual(
                    h_val,
                    actual_dist,
                    f"Heuristic h({u}, {v})={h_val} exceeds true shortest distance {actual_dist}!",
                )

    def test_heuristic_consistency_all_edges(self):
        """Heuristic must be consistent (monotonic): for any edge u -> v and any goal g,
        h(u, g) <= weight(u, v) + h(v, g).
        """
        for u in CAMPUS_GRAPH:
            for v, weight in CAMPUS_GRAPH[u].items():
                for goal in CAMPUS_BUILDINGS:
                    h_u = heuristic(u, goal)
                    h_v = heuristic(v, goal)
                    self.assertLessEqual(
                        h_u,
                        weight + h_v,
                        f"Consistency violated on edge {u}->{v} (weight={weight}) for goal {goal}: h({u})={h_u} > {weight} + h({v})={weight + h_v}",
                    )


if __name__ == "__main__":
    unittest.main()

