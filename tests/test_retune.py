"""The realistic-adapter sweep starts below the old grid."""
from experiments.retune_stage1 import GRID


def test_grid_covers_the_requested_range():
    assert GRID[0] == 0.1
    assert GRID[-1] == 3.0
    assert 1.5 in GRID
