import pytest


class FakeResp:
    def __init__(self, status=200, payload=None, headers=None):
        self.status_code = status
        self._payload = payload
        self.headers = headers or {}
        self.text = str(payload)

    def json(self):
        if self._payload is None:
            raise ValueError("no json")
        return self._payload


class FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def get(self, url, params=None, timeout=None, headers=None):
        self.calls.append((url, params))
        r = self.responses.pop(0)
        if isinstance(r, Exception):
            raise r
        return r


@pytest.fixture
def daily_payload():
    return {
        "geometry": {"type": "Point", "coordinates": [29.92, 31.2, 12.5]},
        "properties": {"parameter": {
            "PRECTOTCORR": {"20240101": 0.02, "20240102": -999.0, "20240103": 1.5},
            "T2M": {"20240101": 14.1, "20240102": 13.9, "20240103": -999.0},
        }},
        "parameters": {"PRECTOTCORR": {"units": "mm/day"}, "T2M": {"units": "C"}},
    }


@pytest.fixture
def monthly_payload():
    return {
        "geometry": {"type": "Point", "coordinates": [29.92, 31.2, 12.5]},
        "properties": {"parameter": {
            "PRECTOTCORR": {"202401": 0.5, "202402": 0.7, "202413": 0.6},
        }},
        "parameters": {"PRECTOTCORR": {"units": "mm/day"}},
    }
