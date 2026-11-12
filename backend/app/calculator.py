"""Simple calculator app created by Sina AI OS."""


def add(a, b):
    return a + b


def sub(a, b):
    return a - b


def mul(a, b):
    return a * b


def div(a, b):
    if b == 0:
        raise ValueError('division by zero')
    return a / b


if __name__ == '__main__':
    print('calculator ready:', add(2, 3))
