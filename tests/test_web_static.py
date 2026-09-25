"""Serving the built web app from the API's process (docs/decisions/028)."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from sympose import web_static


@pytest.fixture
def built(tmp_path):
    root = tmp_path / "webui"
    (root / "assets").mkdir(parents=True)
    (root / "index.html").write_text("<html>the web app</html>")
    (root / "assets" / "app.js").write_text("console.log('app')")
    (root / "sympose.svg").write_text("<svg/>")
    (tmp_path / "secret.txt").write_text("not for the browser")
    return root


def _client(root) -> TestClient:
    app = FastAPI()

    @app.get("/health")
    def health():
        return {"status": "healthy"}

    @app.get("/api/thing")
    def thing():
        return {"thing": 1}

    @app.post("/api/thing")
    def post_thing():
        return {"posted": True}

    web_static.mount_web_app(app, str(root))
    return TestClient(app)


def test_the_root_and_a_route_of_the_app_get_the_page(built):
    client = _client(built)

    for path in ("/", "/notes/some/deep/route", "/graph"):
        response = client.get(path)
        assert response.status_code == 200 and response.text == "<html>the web app</html>"
        assert response.headers["content-type"].startswith("text/html")


def test_files_of_the_built_app_are_served_as_themselves(built):
    client = _client(built)

    script = client.get("/assets/app.js")
    icon = client.get("/sympose.svg")

    assert script.text == "console.log('app')" and "javascript" in script.headers["content-type"]
    assert icon.text == "<svg/>" and icon.headers["content-type"] == "image/svg+xml"


def test_the_api_is_never_shadowed_by_the_page(built):
    client = _client(built)

    assert client.get("/health").json() == {"status": "healthy"}
    assert client.get("/api/thing").json() == {"thing": 1}
    assert client.post("/api/thing").json() == {"posted": True}


def test_an_unknown_api_path_is_a_404_not_the_page(built):
    client = _client(built)

    for path in ("/api/no-such-route", "/api/thing/extra", "/api"):
        response = client.get(path)
        assert response.status_code == 404 and "the web app" not in response.text


def test_a_path_that_climbs_out_of_the_folder_is_not_a_file_of_it(built):
    client = _client(built)

    for path in ("/../secret.txt", "/%2e%2e/secret.txt", "/assets/../../secret.txt", "//etc/passwd"):
        response = client.get(path)
        assert "not for the browser" not in response.text and "root:" not in response.text


def test_a_symlink_out_of_the_folder_is_not_followed(built, tmp_path):
    (built / "leak.txt").symlink_to(tmp_path / "secret.txt")

    assert "not for the browser" not in _client(built).get("/leak.txt").text


def test_a_folder_is_not_a_file_and_gets_the_page(built):
    assert _client(built).get("/assets").text == "<html>the web app</html>"


def test_no_built_app_is_an_error_that_says_how_to_build_it(tmp_path):
    with pytest.raises(web_static.WebAppMissing, match=r"npm run build"):
        web_static.mount_web_app(FastAPI(), str(tmp_path / "nothing"))
    (tmp_path / "empty").mkdir()
    with pytest.raises(web_static.WebAppMissing):
        web_static.mount_web_app(FastAPI(), str(tmp_path / "empty"))


def test_the_app_the_package_ships_is_where_the_server_looks():
    import os

    assert os.path.isfile(os.path.join(web_static.WEBUI_DIR, "index.html"))


def test_a_head_request_works_like_a_get_without_the_body(built):
    client = _client(built)

    for path in ("/", "/assets/app.js", "/some/route"):
        response = client.head(path)
        assert response.status_code == 200 and response.content == b""


def test_a_build_file_that_is_gone_is_a_404_not_the_page(built):
    client = _client(built)

    for path in ("/assets/old-hash.js", "/assets/deeper/old.css"):
        response = client.get(path)
        assert response.status_code == 404 and "the web app" not in response.text
    assert client.head("/assets/old-hash.js").status_code == 404


def test_a_route_of_the_app_with_a_dot_in_it_still_gets_the_page(built):
    assert _client(built).get("/note/Projects/Atlas.md").text == "<html>the web app</html>"
