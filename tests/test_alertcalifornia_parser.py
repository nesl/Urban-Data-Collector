from bs4 import BeautifulSoup

from extractor_modules.alertcalifornia.alertcalifornia_extract import pull_camera_id


def test_pull_camera_id_parses_rendered_gallery_element_without_driver():
    element = BeautifulSoup(
        """
        <div class="alert-ctt-root">
          <img class="alert-ctt-thumb"
               src="/public-camera-data/cam-123/latest-thumb.jpg">
          <div class="alert-ctt-name">Test Camera</div>
        </div>
        """,
        "html.parser",
    ).div

    assert pull_camera_id(element) == ("cam-123", "Test Camera")


def test_pull_camera_id_ignores_missing_thumbnail():
    element = BeautifulSoup(
        '<div class="alert-ctt-root"><div class="alert-ctt-name">Offline</div></div>',
        "html.parser",
    ).div

    assert pull_camera_id(element) == ("", "")
