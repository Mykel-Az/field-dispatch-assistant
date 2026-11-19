"""Save real Nominatim answers as test fixtures (run by hand, never in CI).

    NOMINATIM_USER_AGENT="field-dispatch-assistant (contact: <your contact>)" \
        python -m geocoding.capture_real_fixtures

Writes `fixtures/real_<kind>.json`, the raw response body, unedited. The tests in
`api/tests/test_geocoding_real_responses.py` read every `real_*.json` and check
what the parser makes of it, so a change in Nominatim's answers shows up as a
failing test and not as a wrong pin. Only public landmarks are looked up, never
customer addresses. One request per second, as the usage policy asks.
"""

import os
import pathlib
import sys
import time
import urllib.parse
import urllib.request

from .nominatim import DEFAULT_URL

FIXTURES = pathlib.Path(__file__).resolve().parent / "fixtures"

# kind -> query. The kind is what the parser should make of the answer.
CASES = {
    "house": "1100 Congress Avenue, Austin, TX",
    "street": "Congress Avenue, Austin, TX",
    "postcode": "78701",
    "empty": "zzqx qqwv 00000 nowhere at all",
}


def main() -> int:
    agent = os.environ.get("NOMINATIM_USER_AGENT", "")
    if not agent or "set NOMINATIM_USER_AGENT" in agent:
        print(
            "Set NOMINATIM_USER_AGENT to an identifying string first.", file=sys.stderr
        )
        return 2
    FIXTURES.mkdir(exist_ok=True)
    for kind, query in CASES.items():
        params = {
            "q": query,
            "format": "jsonv2",
            "limit": 1,
            "addressdetails": 1,
            "countrycodes": "us",
        }
        url = f"{os.environ.get('NOMINATIM_URL', DEFAULT_URL)}?{urllib.parse.urlencode(params)}"
        request = urllib.request.Request(
            url, headers={"User-Agent": agent, "Accept": "application/json"}
        )
        with urllib.request.urlopen(request, timeout=15) as response:
            body = response.read().decode("utf-8")
        (FIXTURES / f"real_{kind}.json").write_text(body + "\n", encoding="utf-8")
        print(f"saved real_{kind}.json  ({len(body)} bytes)  <- {query}")
        time.sleep(1.1)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
