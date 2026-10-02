"""The seed's HTTP client: stdlib only, one cookie jar per instance."""
import json
import sys
import urllib.error
import urllib.parse
import urllib.request


class Api:
    def __init__(self, base: str) -> None:
        self.base = base.rstrip("/")
        # One cookie jar per instance: the admin and the manager never share a session.
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor())

    def _call(self, method, path, body=None, form=None, fatal=True):
        url = f"{self.base}{path}"
        headers = {}
        if form is not None:
            data = urllib.parse.urlencode(form).encode()
            headers["Content-Type"] = "application/x-www-form-urlencoded"
        elif body is not None:
            data = json.dumps(body).encode()
            headers["Content-Type"] = "application/json"
        else:
            data = None
        request = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with self.opener.open(request, timeout=30) as response:
                raw = response.read()
                return response.status, (json.loads(raw) if raw else None)
        except urllib.error.HTTPError as error:
            raw = error.read()
            try:
                return error.code, json.loads(raw)
            except ValueError:
                return error.code, {"raw": raw.decode(errors="replace")}
        except urllib.error.URLError as error:
            if not fatal:
                raise
            die(f"no se alcanza {url}: {error.reason}\n  ¿está levantada la pila? docker compose up -d")

    def get(self, path):
        return self._call("GET", path)

    def post(self, path, body=None, form=None):
        return self._call("POST", path, body=body, form=form)

    def logout(self):
        """Best effort: an unclosed session expires by itself and must not fail a finished seed."""
        try:
            self._call("POST", "/auth/logout", fatal=False)
        except OSError as error:
            print(f"  ! no se pudo cerrar la sesión (caducará sola): {error}", file=sys.stderr)

    def login(self, email, password):
        status, data = self.post("/auth/login", form={"username": email, "password": password})
        if status == 200 and data.get("status") == "MFA_REQUIRED":
            die(f"{email} tiene MFA activo y este cliente no lo soporta")
        return status == 200 and data.get("status") == "AUTHENTICATED"


def die(message):
    print(f"\033[31m✗\033[0m {message}", file=sys.stderr)
    sys.exit(1)
