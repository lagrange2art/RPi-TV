import pytest
import os
import signal
import threading

from rpitv.start_app import (
    RPiTV,
    # FakePixels,
    # FakeADC,
    # FakeRotate,
    # FakeStrobo,
    # FakeAudioVisual,
    Flask
)


def test_create_app():
    rpitv = RPiTV(
        Flask("rpitv.start_app"),
        brightness=0.5,
        testing=True,
    )    
    assert rpitv.pixels.brightness == 0.5
    assert rpitv.pixels is not None
    assert rpitv.adc is not None
    assert rpitv.rotate is not None
    assert rpitv.strobo is not None
    assert rpitv.audiovisual is not None


def test_restart_server_schedules_sigterm_and_returns_accepted(monkeypatch):
    scheduled = {}
    sent_signals = []

    class ImmediateTimer:
        def __init__(self, interval, function):
            scheduled["interval"] = interval
            scheduled["function"] = function

        def start(self):
            scheduled["started"] = True

    monkeypatch.setattr("rpitv.start_app.threading.Timer", ImmediateTimer)
    monkeypatch.setattr(
        "rpitv.start_app.os.kill",
        lambda process_id, signum: sent_signals.append((process_id, signum)),
    )
    rpitv = RPiTV(Flask("rpitv.start_app"), testing=True)
    try:
        response = rpitv.app.test_client().post("/restart")

        assert response.status_code == 202
        assert b"Restarting the server" in response.data
        assert scheduled["interval"] == 1.0
        assert scheduled["started"]
        scheduled["function"]()
        assert sent_signals == [(os.getpid(), signal.SIGTERM)]
    finally:
        rpitv.close()


def test_restart_server_requires_post():
    rpitv = RPiTV(Flask("rpitv.start_app"), testing=True)
    try:
        response = rpitv.app.test_client().get("/restart")

        assert response.status_code == 405
    finally:
        rpitv.close()


def test_index_page_contains_restart_button():
    rpitv = RPiTV(Flask("rpitv.start_app"), testing=True)
    try:
        response = rpitv.app.test_client().get("/")

        assert response.status_code == 200
        assert b'action="/restart" method="post"' in response.data
        assert b"Restart Flask server" in response.data
    finally:
        rpitv.close()

@pytest.mark.parametrize(
    "route", [
        "/animation/strobo/",
        "/animation/",
        "/fillstrip/255,128,64",
        pytest.param("/audiovisual/ladder", id="audiovisual_ladder",),
        pytest.param("/audiovisual/pulse", id="audiovisual_pulse"),
]
)
def test_app_route(route):
    print(__name__)

    rpitv = RPiTV(
        Flask("rpitv.start_app"),
        brightness=0.5,
        testing=True,
    )
    try:
        client = rpitv.app.test_client()
        response = client.get(route)
        assert response.status_code == 200
    finally:
        rpitv.close()


@pytest.mark.parametrize("brightness", [0, 0.25, 0.5, 0.825, 1])
def test_adjust_brightness(brightness):
    rpitv = RPiTV(
        Flask("rpitv.start_app"),
        brightness=0.5,
        testing=True,
    )
    try:
        client = rpitv.app.test_client()
        response = client.post(
            "/fillstrip/255,128,64",
            data={"Brightness": brightness},
        )

        assert response.status_code == 200
        assert rpitv.pixels.brightness == brightness
    finally:
        rpitv.close()


def test_logs_route(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    log_file = tmp_path / "logs" / "rpitv.log"
    log_file.parent.mkdir()
    log_file.write_text("INFO test: \033[36mGET /static/style.css HTTP/1.1\033[0m\n")

    rpitv = RPiTV(
        Flask("rpitv.start_app"),
        testing=True,
    )
    try:
        response = rpitv.app.test_client().get("/logs")

        assert response.status_code == 200
        assert b"GET /static/style.css HTTP/1.1" in response.data
        assert b"\x1b" not in response.data
    finally:
        rpitv.close()