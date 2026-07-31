import socket

from scripts.check_local_runtime_port import port_is_available


def test_port_is_available_returns_false_while_loopback_port_is_owned():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as owner:
        owner.bind(("127.0.0.1", 0))
        assert port_is_available(owner.getsockname()[1]) is False


def test_port_is_available_returns_true_after_port_is_released():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as owner:
        owner.bind(("127.0.0.1", 0))
        port = owner.getsockname()[1]

    assert port_is_available(port) is True
