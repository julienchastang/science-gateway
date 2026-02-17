#!/usr/bin/env python3
import asyncio
import hashlib
import hmac
import logging
import os
import pathlib
import re
import time
from urllib.parse import quote

import requests
import tornado.ioloop
import tornado.web
from jupyterhub.services.auth import HubOAuthenticated, HubOAuthCallbackHandler
from jupyterhub.utils import url_path_join

LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()
logging.basicConfig(level=getattr(logging, LOG_LEVEL, logging.INFO))
logger = logging.getLogger("nblaunch")


HMAC_SECRET = os.environ["SECRET"].encode("utf-8")
NBGALLERY_BASE = os.environ["NBGALLERY_BASE"].rstrip("/")
NBGALLERY_SERVICE_TOKEN = os.environ["NBGALLERY_SERVICE_TOKEN"]
HOME_ROOT = pathlib.Path(os.environ.get("HOME_ROOT", "/home"))
TTL_SECONDS = int(os.environ.get("TTL_SECONDS", "300"))
PORT = int(os.environ.get("PORT", "8080"))
SERVICE_PREFIX = os.environ.get("JUPYTERHUB_SERVICE_PREFIX", "/")
JUPYTERHUB_BASE_URL = os.environ.get("JUPYTERHUB_BASE_URL", "/")
MAX_NOTEBOOK_BYTES = int(os.environ.get("MAX_NOTEBOOK_BYTES", "20971520"))
DEV_MODE = os.environ.get("DEV_MODE", "0") == "1"
NBGALLERY_USER_AGENT = os.environ.get(
    "NBGALLERY_USER_AGENT",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
)

NB_ID_PATTERN = re.compile(r"^[A-Za-z0-9._-]+$")


class NotebookTooLargeError(Exception):
    pass


def _resolve_user_home(username: str) -> pathlib.Path:
    if not username or "/" in username or "\\" in username or "\x00" in username:
        raise tornado.web.HTTPError(400, "invalid username path")

    base_root = HOME_ROOT.resolve()

    # JupyterHub/KubeSpawner safe slug directories often look like:
    # "<slugified-username>---<hash>".
    slug = re.sub(r"[^a-z0-9]+", "-", username.lower()).strip("-")
    if slug:
        candidates = []
        for p in HOME_ROOT.glob(f"{slug}---*"):
            try:
                rp = p.resolve()
                rp.relative_to(base_root)
            except ValueError:
                continue
            if rp.is_dir():
                candidates.append(rp)
        if candidates:
            candidates.sort(key=lambda p: p.name)
            if len(candidates) > 1:
                logger.warning(
                    "Multiple home directories matched for user=%s slug=%s; using %s",
                    username,
                    slug,
                    candidates[0],
                )
            return candidates[0]

    # Backward-compatible direct username directory.
    raw_dir = (HOME_ROOT / username).resolve()
    try:
        raw_dir.relative_to(base_root)
    except ValueError as exc:
        raise tornado.web.HTTPError(400, "invalid username path") from exc
    if raw_dir.exists() and raw_dir.is_dir():
        return raw_dir

    logger.warning("No existing home directory found for user=%s; falling back to raw path %s", username, raw_dir)
    return raw_dir


class LaunchHandler(HubOAuthenticated, tornado.web.RequestHandler):
    hub_scopes = {"access:services!service=nblaunch"}

    async def get(self):
        user = self.get_current_user()
        if not user:
            self.redirect(self.get_login_url())
            return

        username = user["name"]
        nb = self.get_query_argument("nb", default="")
        ts_raw = self.get_query_argument("ts", default="")
        sig = self.get_query_argument("sig", default="")

        self._validate_request(nb=nb, ts_raw=ts_raw, sig=sig)
        notebook_bytes = await self._download_notebook(nb)
        destination = self._write_notebook(username=username, nb=nb, payload=notebook_bytes)

        logger.info("Notebook %s written for user=%s to %s", nb, username, destination)
        target = url_path_join(
            JUPYTERHUB_BASE_URL,
            "hub",
            "user-redirect",
            "lab",
            "tree",
            "nbgallery",
            f"{quote(nb, safe='')}.ipynb",
        )
        self.redirect(target, status=302)

    def _validate_request(self, nb: str, ts_raw: str, sig: str) -> None:
        if not nb or not ts_raw or not sig:
            raise tornado.web.HTTPError(400, "missing required query params: nb, ts, sig")
        if not NB_ID_PATTERN.match(nb):
            raise tornado.web.HTTPError(400, "invalid nb")

        try:
            ts = int(ts_raw)
        except ValueError as exc:
            raise tornado.web.HTTPError(400, "invalid ts") from exc

        now = int(time.time())
        if abs(now - ts) > TTL_SECONDS:
            raise tornado.web.HTTPError(403, "expired or not-yet-valid ts")

        msg = f"{nb}:{ts}".encode("utf-8")
        expected = hmac.new(HMAC_SECRET, msg, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, sig):
            raise tornado.web.HTTPError(403, "invalid sig")

    async def _download_notebook(self, nb: str) -> bytes:
        try:
            return await asyncio.to_thread(self._download_notebook_blocking, nb)
        except NotebookTooLargeError as exc:
            raise tornado.web.HTTPError(413, "notebook exceeds MAX_NOTEBOOK_BYTES") from exc
        except requests.RequestException as exc:
            url = f"{NBGALLERY_BASE}/notebooks/{quote(nb, safe='')}/download?clickstream=false"
            logger.exception("Failed downloading notebook nb=%s from %s", nb, url)
            raise tornado.web.HTTPError(502, "failed to download notebook") from exc

    def _download_notebook_blocking(self, nb: str) -> bytes:
        url = f"{NBGALLERY_BASE}/notebooks/{quote(nb, safe='')}/download"
        params = {"clickstream": "false"}
        headers = {"User-Agent": NBGALLERY_USER_AGENT}
        with requests.get(url, headers=headers, params=params, timeout=30, stream=False) as resp:
            resp.raise_for_status()

            content_type = (resp.headers.get("Content-Type") or "").lower()
            if "text/html" in content_type:
                raise requests.RequestException(f"NBGallery returned HTML for notebook download from {url}")

            content_length = resp.headers.get("Content-Length")
            if content_length is not None:
                try:
                    if int(content_length) > MAX_NOTEBOOK_BYTES:
                        raise NotebookTooLargeError("content-length exceeds limit")
                except ValueError:
                    pass

            payload = resp.content
            if len(payload) > MAX_NOTEBOOK_BYTES:
                raise NotebookTooLargeError("streamed payload exceeds limit")
            return payload

    def _write_notebook(self, username: str, nb: str, payload: bytes) -> pathlib.Path:
        user_root = _resolve_user_home(username)

        dst_dir = user_root / "nbgallery"
        dst_dir.mkdir(parents=True, exist_ok=True)
        dst_path = dst_dir / f"{nb}.ipynb"
        tmp_path = dst_dir / f"{nb}.ipynb.tmp.{os.getpid()}.{time.time_ns()}"
        with open(tmp_path, "wb") as f:
            f.write(payload)
        os.replace(tmp_path, dst_path)
        return dst_path


class HealthHandler(tornado.web.RequestHandler):
    def get(self):
        self.write({"ok": True})


def make_app() -> tornado.web.Application:
    cookie_secret = os.environ.get("COOKIE_SECRET")
    if not cookie_secret:
        if DEV_MODE:
            cookie_secret = "nblaunch-dev-cookie-secret"
            logger.warning("DEV_MODE=1 set; using insecure development COOKIE_SECRET")
        else:
            raise RuntimeError("COOKIE_SECRET must be set (or set DEV_MODE=1 for local development)")

    prefix = SERVICE_PREFIX
    return tornado.web.Application(
        [
            (url_path_join(prefix, "healthz"), HealthHandler),
            (url_path_join(prefix, "launch"), LaunchHandler),
            (url_path_join(prefix, "oauth_callback"), HubOAuthCallbackHandler),
        ],
        cookie_secret=cookie_secret,
    )


def main() -> None:
    app = make_app()
    app.listen(PORT)
    logger.info("nblaunch listening on port %s", PORT)
    logger.info("JUPYTERHUB_CLIENT_ID=%s", os.environ.get("JUPYTERHUB_CLIENT_ID", ""))
    tornado.ioloop.IOLoop.current().start()


if __name__ == "__main__":
    main()
