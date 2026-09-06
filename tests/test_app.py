import pytest

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


@pytest.mark.parametrize("brightness", [0, 0.25, 1])
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