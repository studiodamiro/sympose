"""Serving the built web app from the API's own process (docs/decisions/028): the files in
`sympose/webui/`, and `index.html` for any path the app handles in the browser. Added after every
API route, so the API always wins; an unknown `/api/...` stays a 404 and is never answered with the page."""

import os

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse

from sympose.security import is_safe_path

WEBUI_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "webui")


class WebAppMissing(Exception):
    """There is no built web app to serve (a checkout that never ran `npm run build` in `ui/`)."""


def mount_web_app(app: FastAPI, directory: str | None = None) -> None:
    directory = directory or WEBUI_DIR  # looked up now, so it can be pointed elsewhere
    index = os.path.join(directory, "index.html")
    if not os.path.isfile(index):
        raise WebAppMissing(
            f"no built web app in {directory}. Build it with `npm run build` in ui/, or use `npm run dev` there."
        )

    @app.api_route("/{path:path}", methods=["GET", "HEAD"], include_in_schema=False)
    def web_app(path: str) -> FileResponse:
        if path == "api" or path.startswith("api/"):
            raise HTTPException(status_code=404, detail="Not Found")
        candidate = os.path.join(directory, path)
        if path and os.path.isfile(candidate) and is_safe_path(candidate, directory):
            return FileResponse(candidate)
        if path.startswith("assets/"):
            # a build file that is gone (a cached page from before a rebuild): a clean 404, not a page
            # a browser would refuse to run as a script
            raise HTTPException(status_code=404, detail="Not Found")
        return FileResponse(index)  # a route of the app itself: the page decides what to show
