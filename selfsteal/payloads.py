"""JSON payload factories.

Every payload is a plain dict produced deterministically from the profile.  No
factory invents credentials, tokens, keys or anything resembling a secret: an
endpoint that appears to leak one would attract exactly the attention this
project exists to avoid, and a decoy is not a place to store real values.
"""

from __future__ import annotations

import datetime as _dt
from typing import Any, Callable, Dict, List

from . import data as _data
from .profile import Profile
from .rng import SeededRandom

_ID_ALPHABET = "abcdefghijklmnopqrstuvwxyz0123456789"


def _token(rng: SeededRandom, length: int = 14) -> str:
    return "".join(rng.choice(list(_ID_ALPHABET)) for _ in range(length))


def ident(rng: SeededRandom, prefix: str, length: int = 14) -> str:
    return f"{prefix}_{_token(rng, length)}"


def timestamp(profile: Profile, rng: SeededRandom, *, back_days: int = 400) -> str:
    """An ISO-8601 instant before the profile's release date."""
    base = _dt.date.fromisoformat(profile.release)
    delta = _dt.timedelta(
        days=rng.between(0, back_days),
        seconds=rng.between(0, 86399),
    )
    moment = _dt.datetime.combine(base, _dt.time()) - delta
    return moment.replace(microsecond=0).isoformat() + "Z"


def _pagination(rng: SeededRandom, count: int) -> Dict[str, Any]:
    return {
        "limit": rng.choice([20, 25, 50, 100]),
        "count": count,
        "has_more": rng.chance(45),
    }


# --- factories --------------------------------------------------------------
# Each takes (profile, rng, **args) and returns a JSON-serialisable dict.


def collection(profile: Profile, rng: SeededRandom, *, object_name: str,
               item: Callable[[Profile, SeededRandom], Dict[str, Any]],
               low: int = 2, high: int = 5) -> Dict[str, Any]:
    items = [item(profile, rng) for _ in range(rng.between(low, high))]
    body: Dict[str, Any] = {"object": "list", "data": items}
    if rng.chance(70):
        body["pagination"] = _pagination(rng, len(items))
    return body


def enumeration(profile: Profile, rng: SeededRandom, *, key: str,
                values: List[str], low: int = 3, high: int = 6) -> Dict[str, Any]:
    chosen = sorted(rng.subset(values, low, high))
    body = {key: chosen}
    if rng.chance(50):
        body["default"] = chosen[0]
    return body


def regions(profile: Profile, rng: SeededRandom, *, low: int = 3,
            high: int = 6) -> Dict[str, Any]:
    pool = rng.subset(_data.REGIONS, low, high)
    entries = []
    seen = {(profile.region.city, profile.region.zone,
             profile.region.pop, profile.region.country)}
    pool = [p for p in pool if p not in seen]
    home = (profile.region.city, profile.region.zone,
            profile.region.pop, profile.region.country)
    for city, zone, pop, country in [home] + pool:
        entries.append({
            "code": pop,
            "name": city,
            "zone": zone,
            "country": country,
            "status": "operational",
        })
    return {"object": "list", "data": entries}


def usage(profile: Profile, rng: SeededRandom, *, unit: str = "requests") -> Dict[str, Any]:
    return {
        "period": {"start": profile.release, "granularity": "day"},
        "unit": unit,
        "totals": {
            "current": rng.between(10_000, 900_000),
            "limit": rng.choice([100_000, 500_000, 1_000_000, 5_000_000]),
        },
    }


def limits(profile: Profile, rng: SeededRandom) -> Dict[str, Any]:
    window = rng.choice([60, 60, 300, 3600])
    return {
        "rate_limit": {
            "window_seconds": window,
            "max_requests": rng.choice([60, 120, 300, 600, 1200]),
            # Deliberately avoids the literal "api_key": the validator treats
            # credential-shaped strings in served content as a failure, and a
            # decoy has no reason to publish one even as a label.
            "scope": rng.choice(["application", "project", "ip"]),
        },
        "max_request_bytes": rng.choice([1_048_576, 5_242_880, 10_485_760]),
    }


def schema_doc(profile: Profile, rng: SeededRandom, *,
               collections: List[str]) -> Dict[str, Any]:
    types = ["string", "integer", "boolean", "timestamp", "float", "json"]
    out = []
    for name in collections:
        fields = [{"name": "id", "type": "string", "nullable": False}]
        for field_name in rng.subset(
            ["name", "label", "created_at", "updated_at", "size", "status",
             "checksum", "owner", "region", "tags", "content_type"], 3, 6
        ):
            fields.append({
                "name": field_name,
                "type": rng.choice(types),
                "nullable": rng.chance(35),
            })
        out.append({"name": name, "fields": fields})
    return {"object": "list", "data": out}


def index_document(profile: Profile, rng: SeededRandom, *,
                   resources: List[str]) -> Dict[str, Any]:
    body = {
        "name": profile.brand.product,
        "version": profile.api_version,
        "status": "available",
        "resources": {
            name: f"/api/{profile.api_version}/{name}" for name in resources
        },
    }
    if rng.chance(60):
        body["documentation"] = f"https://{profile.domain}/docs"
    return body


def root_document(profile: Profile, rng: SeededRandom) -> Dict[str, Any]:
    return {
        "name": profile.brand.product,
        "versions": [
            {
                "version": profile.api_version,
                "status": "stable",
                "url": f"/api/{profile.api_version}",
            }
        ],
    }


def health_document(profile: Profile, rng: SeededRandom, *,
                    ready: bool = False) -> Dict[str, Any]:
    if ready:
        return {"status": "ok", "checks": {"api": "ok", "storage": "ok"}}
    return {"status": "ok"}


def status_document(profile: Profile, rng: SeededRandom, *,
                    components: List[str]) -> Dict[str, Any]:
    return {
        "status": "operational",
        "version": profile.api_version,
        "region": profile.region.city,
        "components": [
            {"name": name, "status": "operational"} for name in components
        ],
        "updated_at": timestamp(profile, rng, back_days=2),
    }


# --- item builders ----------------------------------------------------------


def _sized_item(prefix: str, extras: Callable[[Profile, SeededRandom], Dict[str, Any]]):
    def build(profile: Profile, rng: SeededRandom) -> Dict[str, Any]:
        item = {"id": ident(rng, prefix), "created_at": timestamp(profile, rng)}
        item.update(extras(profile, rng))
        return item
    return build


def media_item(profile: Profile, rng: SeededRandom) -> Dict[str, Any]:
    return _sized_item("med", lambda p, r: {
        "content_type": r.choice(["image/jpeg", "image/png", "image/webp", "video/mp4"]),
        "bytes": r.between(24_000, 8_400_000),
        "width": r.choice([640, 800, 1024, 1280, 1920, 2560]),
        "height": r.choice([360, 600, 768, 1080, 1440]),
        "status": "ready",
    })(profile, rng)


def asset_item(profile: Profile, rng: SeededRandom) -> Dict[str, Any]:
    return _sized_item("ast", lambda p, r: {
        "path": "/" + "/".join(r.subset(
            ["static", "public", "build", "assets", "media", "dist"], 1, 2)
        ) + f"/{_token(r, 8)}",
        "bytes": r.between(1_200, 2_400_000),
        "cache_status": r.choice(["HIT", "HIT", "MISS", "REVALIDATED"]),
    })(profile, rng)


def record_item(profile: Profile, rng: SeededRandom) -> Dict[str, Any]:
    return _sized_item("rec", lambda p, r: {
        "collection": r.choice(["events", "documents", "entries", "items"]),
        "revision": r.between(1, 24),
        "updated_at": timestamp(p, r, back_days=90),
    })(profile, rng)


def bucket_item(profile: Profile, rng: SeededRandom) -> Dict[str, Any]:
    return _sized_item("bkt", lambda p, r: {
        "name": r.choice(["archive", "backups", "media", "uploads", "exports",
                          "artifacts", "snapshots"]),
        "region": p.region.pop,
        "objects": r.between(12, 48_000),
        "bytes": r.between(1_000_000, 900_000_000),
    })(profile, rng)


def object_item(profile: Profile, rng: SeededRandom) -> Dict[str, Any]:
    return _sized_item("obj", lambda p, r: {
        "key": f"{r.choice(['exports', 'daily', 'raw', 'processed'])}/{_token(r, 10)}",
        "bytes": r.between(512, 42_000_000),
        "storage_class": r.choice(["standard", "standard", "infrequent", "archive"]),
    })(profile, rng)


def file_item(profile: Profile, rng: SeededRandom) -> Dict[str, Any]:
    return _sized_item("fil", lambda p, r: {
        "filename": f"{_token(r, 8)}.{r.choice(['pdf', 'csv', 'zip', 'json', 'txt'])}",
        "bytes": r.between(1_024, 18_000_000),
        "checksum": "sha256:" + _token(r, 32),
    })(profile, rng)


def app_item(profile: Profile, rng: SeededRandom) -> Dict[str, Any]:
    # Deliberately metadata only: no key material, not even a fake one.
    return _sized_item("app", lambda p, r: {
        "name": r.choice(["production", "staging", "internal", "sandbox", "ci"]),
        "scopes": sorted(r.subset(["read", "write", "admin", "events"], 1, 3)),
        "last_used_at": timestamp(p, r, back_days=30),
    })(profile, rng)


def event_item(profile: Profile, rng: SeededRandom) -> Dict[str, Any]:
    return _sized_item("evt", lambda p, r: {
        "name": r.choice(["page_view", "session_start", "conversion", "click",
                          "signup", "purchase"]),
        "count": r.between(40, 92_000),
        "source": r.choice(["web", "api", "mobile", "server"]),
    })(profile, rng)


def node_item(profile: Profile, rng: SeededRandom) -> Dict[str, Any]:
    return _sized_item("nod", lambda p, r: {
        "pop": r.choice([reg[2] for reg in _data.REGIONS]),
        "status": "operational",
        "capacity": f"{r.between(10, 100)}G",
    })(profile, rng)


def service_item(profile: Profile, rng: SeededRandom) -> Dict[str, Any]:
    return _sized_item("svc", lambda p, r: {
        "name": r.choice(["gateway", "worker", "scheduler", "ingest", "render",
                          "indexer"]),
        "runtime": r.choice(["container", "container", "function"]),
        "replicas": r.between(1, 8),
        "status": "running",
    })(profile, rng)


def incident_item(profile: Profile, rng: SeededRandom) -> Dict[str, Any]:
    return _sized_item("inc", lambda p, r: {
        "title": r.choice([
            "Elevated latency in one region",
            "Delayed processing queue",
            "Intermittent timeouts on read requests",
            "Scheduled maintenance window",
        ]),
        "status": "resolved",
        "impact": r.choice(["minor", "minor", "none"]),
        "resolved_at": timestamp(p, r, back_days=120),
    })(profile, rng)


ITEM_BUILDERS: Dict[str, Callable[[Profile, SeededRandom], Dict[str, Any]]] = {
    "media": media_item,
    "asset": asset_item,
    "record": record_item,
    "bucket": bucket_item,
    "object": object_item,
    "file": file_item,
    "app": app_item,
    "event": event_item,
    "node": node_item,
    "service": service_item,
    "incident": incident_item,
}
