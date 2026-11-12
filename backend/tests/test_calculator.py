import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from app.calculator import add, sub, mul, div


def test_add():
    assert add(2, 3) == 5


def test_sub():
    assert sub(5, 3) == 2


def test_mul():
    assert mul(3, 4) == 12


def test_div_zero():
    try:
        div(1, 0)
    except ValueError:
        return
    raise AssertionError('expected ValueError')
