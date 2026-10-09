"""Shows a quilt on the Looking Glass Portrait, through StepIt Holo's server.

show() uploads the quilt to the server of display.url, e.g. on the Raspberry
Pi the Portrait is plugged into: POST /quilt, a multipart form with the file
and its layout. The server turns the quilt into the image the Portrait's
screen shows, with the Portrait's own calibration, and shows it until the next
quilt replaces it, also after a restart. See
https://github.com/kineticsystem/stepit-holo/blob/main/docs/API.md.

The server answers once the quilt is shown. When it cannot show it yet, e.g.
the Portrait is switched off, it answers 503 and keeps the quilt, to show it as
soon as it can: that is not an error here.
"""

import json
import logging
import urllib.error
import urllib.request
import uuid
from pathlib import Path

log = logging.getLogger(__name__)

# The first quilt of a layout also works out the server's table: a few seconds on a Raspberry Pi.
TIMEOUT = 60
TYPES = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg"}


def form(fields, name, data):
    """A multipart/form-data body with the text fields and the file: (body, content type)."""
    boundary = uuid.uuid4().hex
    parts = [f'--{boundary}\r\nContent-Disposition: form-data; name="{key}"\r\n\r\n{value}\r\n'.encode()
             for key, value in fields.items()]
    content_type = TYPES.get(Path(name).suffix.lower(), "application/octet-stream")
    parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="{name}"\r\n'
                 f"Content-Type: {content_type}\r\n\r\n".encode() + data + b"\r\n")
    parts.append(f"--{boundary}--\r\n".encode())
    return b"".join(parts), f"multipart/form-data; boundary={boundary}"


def detail(error):
    """The server's own message in an HTTP error, e.g. no Looking Glass found."""
    try:
        return json.loads(error.read())["detail"]
    except (ValueError, KeyError, TypeError, OSError):
        return f"{error.code} {error.reason}"


def show(quilt_path, quilt, url):
    """Shows the quilt on the Portrait, replacing the quilt shown before. Raises RuntimeError if the server cannot
    be reached or refuses the quilt."""
    if not url:
        raise RuntimeError("no display.url in config/pipeline.toml")
    path = Path(quilt_path)
    # The quilt is built in the order of the views already: the server keeps it.
    body, content_type = form({"columns": quilt.columns, "rows": quilt.rows, "reverse": "false"}, path.name,
                              path.read_bytes())
    request = urllib.request.Request(f"{url.rstrip('/')}/quilt", data=body, method="POST",
                                     headers={"Content-Type": content_type})
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
            shown = json.loads(response.read())
    except urllib.error.HTTPError as error:
        if error.code == 503:
            log.warning("StepIt Holo keeps %s, and shows it once it can: %s", path.name, detail(error))
            return
        raise RuntimeError(f"StepIt Holo at {url} refused {path.name}: {detail(error)}") from error
    except (urllib.error.URLError, OSError) as error:
        reason = getattr(error, "reason", error)
        raise RuntimeError(f"cannot reach StepIt Holo at {url}: {reason}") from error
    log.info("Showing %s on the Looking Glass, %s", path.name, shown.get("shown_on"))
