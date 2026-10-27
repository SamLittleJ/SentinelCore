"""`make screenshots`: the README's four pictures, taken from a running
`make demo` (start it first, in another terminal).

Headless Firefox is driven over WebDriver BiDi with `websockets`, which the
backend's environment already has. The accounts come from .demo/ and their
passwords are never printed. The pictures land in docs/images/: dark theme,
English, 1440x900, reduced to 256 colours when ImageMagick is installed.
"""

import asyncio
import base64
import itertools
import json
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

from websockets.asyncio.client import connect

ROOT = Path(__file__).resolve().parent.parent
DEMO = ROOT / ".demo"
IMAGES = ROOT / "docs" / "images"
APP = "http://localhost:5173"
PORT = 9333
VIEWPORT = {"width": 1440, "height": 900}
# Runs in every page before the app: the theme and language it starts with.
PREFERENCES = """() => {
  localStorage.setItem('sentinelcore.theme', 'dark')
  localStorage.setItem('sentinelcore.language', 'en')
}"""
# A page has loaded once its heading shows and no skeleton is left.
LOADED = (
    "!!document.querySelector('main h1') && !document.querySelector('.animate-pulse')"
)
SIGN_IN = """(email, password) => {
  const field = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value')
  for (const [id, value] of [['login-email', email], ['login-password', password]]) {
    const input = document.getElementById(id)
    field.set.call(input, value)
    input.dispatchEvent(new Event('input', { bubbles: true }))
  }
  document.querySelector('button[type=submit]').click()
}"""


def fail(message: str) -> None:
    sys.exit(f"make screenshots: {message}")


def account(file: str) -> tuple[str, str]:
    path = DEMO / file
    if not path.exists():
        fail(f"{path.relative_to(ROOT)} is missing; run `make demo` first")
    fields = dict(
        line.split(": ", 1) for line in path.read_text().splitlines() if ": " in line
    )
    return fields["email"], fields["password"]


class Browser:
    """One WebDriver BiDi session over the browser's socket."""

    def __init__(self, socket_) -> None:
        self.socket = socket_
        self.ids = itertools.count(1)
        self.context = ""

    async def send(self, method: str, **params) -> dict:
        command = next(self.ids)
        await self.socket.send(
            json.dumps({"id": command, "method": method, "params": params})
        )
        while True:
            message = json.loads(await self.socket.recv())
            if message.get("id") == command:
                if message["type"] == "error":
                    raise RuntimeError(
                        f"{method}: {message['error']}: {message['message']}"
                    )
                return message["result"]

    async def evaluate(self, expression: str):
        result = await self.send(
            "script.evaluate",
            expression=expression,
            target={"context": self.context},
            awaitPromise=True,
        )
        if result["type"] == "exception":
            raise RuntimeError(result["exceptionDetails"]["text"])
        return result["result"].get("value")

    async def wait_for(self, expression: str, what: str) -> None:
        deadline = time.monotonic() + 30
        while not await self.evaluate(expression):
            if time.monotonic() > deadline:
                raise RuntimeError(f"timed out waiting for {what}")
            await asyncio.sleep(0.25)

    async def open(self, path: str) -> None:
        await self.send(
            "browsingContext.navigate",
            context=self.context,
            url=APP + path,
            wait="complete",
        )
        await self.wait_for(LOADED, path)
        # Charts and fonts settle after the data arrives.
        await asyncio.sleep(1.5)

    async def sign_in(self, file: str) -> None:
        email, password = account(file)
        await self.send("storage.deleteCookies")
        await self.send(
            "browsingContext.navigate",
            context=self.context,
            url=APP + "/login",
            wait="complete",
        )
        await self.wait_for(
            "!!document.getElementById('login-email')", "the sign-in form"
        )
        await self.send(
            "script.callFunction",
            functionDeclaration=SIGN_IN,
            arguments=[
                {"type": "string", "value": email},
                {"type": "string", "value": password},
            ],
            target={"context": self.context},
            awaitPromise=False,
        )
        await self.wait_for("location.pathname !== '/login'", f"{email} to sign in")

    async def shoot(self, name: str) -> None:
        result = await self.send(
            "browsingContext.captureScreenshot", context=self.context
        )
        path = IMAGES / name
        path.write_bytes(base64.b64decode(result["data"]))
        if shutil.which("magick"):
            subprocess.run(
                [
                    "magick",
                    path,
                    "-strip",
                    "-dither",
                    "None",
                    "-colors",
                    "256",
                    f"PNG8:{path}",
                ],
                check=True,
            )
        print(f"  {path.relative_to(ROOT)}  {path.stat().st_size // 1024} KB")


async def take(browser: Browser) -> None:
    await browser.sign_in("owner.txt")
    await browser.open("/org")
    await browser.shoot("platform-overview.png")

    await browser.sign_in("acme-admin.txt")
    # The detection rules' alerts, each with its MITRE ATT&CK badge.
    await browser.open("/org/events?range=30d&severity=incident")
    await browser.shoot("acme-events.png")
    # The account the analyst locked this morning, after an unfamiliar sign-in.
    locked = await browser.evaluate(
        "fetch('/api/admin/users?locked=true')"
        ".then(r => r.json()).then(p => p.items[0]?.id)"
    )
    if locked is None:
        raise RuntimeError("no locked Acme account; restart `make demo`")
    await browser.open(f"/org/users/{locked}")
    await browser.shoot("acme-locked-account.png")

    await browser.sign_in("globex-admin.txt")
    await browser.open("/org")
    await browser.shoot("globex-overview.png")


async def drive() -> None:
    async with connect(f"ws://127.0.0.1:{PORT}/session", max_size=None) as socket_:
        browser = Browser(socket_)
        await browser.send("session.new", capabilities={})
        try:
            await browser.send(
                "script.addPreloadScript", functionDeclaration=PREFERENCES
            )
            tree = await browser.send("browsingContext.getTree")
            browser.context = tree["contexts"][0]["context"]
            await browser.send(
                "browsingContext.setViewport",
                context=browser.context,
                viewport=VIEWPORT,
            )
            await take(browser)
        finally:
            await browser.send("session.end")


def main() -> None:
    try:
        urllib.request.urlopen(APP, timeout=3)
    except OSError:
        fail(f"nothing answers at {APP}; start `make demo` in another terminal first")
    with socket.socket() as probe:
        if probe.connect_ex(("127.0.0.1", PORT)) == 0:
            fail(f"port {PORT} is taken; close what uses it")
    if not shutil.which("magick"):
        print(
            "make screenshots: ImageMagick not found; the PNGs stay unreduced",
            file=sys.stderr,
        )
    IMAGES.mkdir(parents=True, exist_ok=True)

    profile = Path(tempfile.mkdtemp(prefix="sentinelcore-screenshots-"))
    log = profile / "firefox.log"
    with log.open("w") as output:
        firefox = subprocess.Popen(
            [
                "firefox",
                "--headless",
                "--no-remote",
                "--profile",
                profile,
                f"--remote-debugging-port={PORT}",
                "about:blank",
            ],
            stdout=output,
            stderr=subprocess.STDOUT,
        )
    try:
        # Probing the port instead makes Firefox refuse the session later.
        deadline = time.monotonic() + 30
        while "WebDriver BiDi listening" not in log.read_text():
            if firefox.poll() is not None or time.monotonic() > deadline:
                fail(f"Firefox did not start:\n{log.read_text()}")
            time.sleep(0.2)
        asyncio.run(drive())
    finally:
        firefox.terminate()
        firefox.wait()
        shutil.rmtree(profile)


if __name__ == "__main__":
    main()
