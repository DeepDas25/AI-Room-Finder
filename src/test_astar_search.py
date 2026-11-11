"""Unit tests for A* Search Campus Route Finding."""

import unittest
from pathlib import Path
import sys

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from src.campus_graph import CAMPUS_GRAPH, CAMPUS_BUILDINGS
from src.astar_search import find_shortest_route


class TestAStarSearch(unittest.TestCase):

    def _calculate_path_sum(self, path: list) -> float:
        """Helper to calculate the sum of edge weights along a path directly from CAMPUS_GRAPH."""
        if len(path) <= 1:
            return 0.0
        total = 0.0
        for i in range(len(path) - 1):
            u, v = path[i], path[i + 1]
            self.assertIn(v, CAMPUS_GRAPH[u], f"Edge {u} -> {v} does not exist in CAMPUS_GRAPH")
            total += CAMPUS_GRAPH[u][v]
        return total

    def test_same_source_and_destination(self):
        """Same source and destination returns single-node path and distance 0."""
        for b in CAMPUS_BUILDINGS:
            result = find_shortest_route(b, b)
            self.assertEqual(result["path"], [b])
            self.assertEqual(result["total_distance"], 0.0)

    def test_eb2_to_tb(self):
        """EB2 to TB: expected path EB2 -> EB1 -> TB, distance 15 metres."""
        result = find_shortest_route("EB2", "TB")
        self.assertEqual(result["path"], ["EB2", "EB1", "TB"])
        self.assertEqual(result["total_distance"], 15.0)
        self.assertEqual(self._calculate_path_sum(result["path"]), 15.0)

    def test_tb_to_eb2(self):
        """TB to EB2: expected path TB -> EB1 -> EB2, distance 15 metres."""
        result = find_shortest_route("TB", "EB2")
        self.assertEqual(result["path"], ["TB", "EB1", "EB2"])
        self.assertEqual(result["total_distance"], 15.0)
        self.assertEqual(self._calculate_path_sum(result["path"]), 15.0)

    def test_eb2_to_im(self):
        """EB2 to IM: direct edge is 50 metres; EB2 -> EB1 -> IM is 5 + 40 = 45 metres.
        A* finds the shortest weighted path. Verify returned path and cost."""
        result = find_shortest_route("EB2", "IM")
        self.assertIn(result["total_distance"], [45.0, 50.0])
        # The shortest path between EB2 and IM is EB2 -> EB1 -> IM with cost 5 + 40 = 45m,
        # which is shorter than the direct edge EB2 -> IM (50m).
        self.assertEqual(result["path"], ["EB2", "EB1", "IM"])
        self.assertEqual(result["total_distance"], 45.0)
        self.assertEqual(self._calculate_path_sum(result["path"]), 45.0)

    def test_tb_to_im(self):
        """TB to IM: TB -> EB1 (10) -> IM (40) = 50 metres total distance."""
        result = find_shortest_route("TB", "IM")
        self.assertEqual(result["path"], ["TB", "EB1", "IM"])
        self.assertEqual(result["total_distance"], 50.0)
        self.assertEqual(self._calculate_path_sum(result["path"]), 50.0)

    def test_all_pairs_path_distance_consistency(self):
        """Verify that for every building pair, route total_distance matches the sum of edge weights."""
        buildings = sorted(CAMPUS_BUILDINGS)
        for u in buildings:
            for v in buildings:
                result = find_shortest_route(u, v)
                path = result["path"]
                dist = result["total_distance"]
                # Must start at u and end at v
                self.assertEqual(path[0], u)
                self.assertEqual(path[-1], v)
                # Distance must equal sum of edges
                self.assertEqual(dist, self._calculate_path_sum(path))

    def test_invalid_building_codes(self):
        """Invalid or unknown building codes raise ValueError."""
        invalid_codes = ["", "XYZ", "EB3", "LIB", None, 999]
        for code in invalid_codes:
            with self.assertRaises(ValueError):
                find_shortest_route(code, "EB1")
            with self.assertRaises(ValueError):
                find_shortest_route("EB1", code)


if __name__ == "__main__":
    unittest.main()

