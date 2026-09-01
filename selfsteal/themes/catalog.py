"""The eleven technical service archetypes, expressed as data.

Adding a twelfth service means appending one ``TechTheme`` here.  No installer,
Caddyfile, validator or template change is required — that is the property the
registry exists to guarantee.

Coherence rule: a theme's resources, status components and vocabulary must all
belong to the same domain.  A "Media API" that exposes ``/api/v1/buckets`` is
worse than no decoy, because incoherence is exactly what a human reviewer
notices first.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass(frozen=True)
class TechResource:
    name: str                     # URL segment, e.g. "media"
    title: str                    # "Media"
    summary: str
    factory: str                  # key into payloads.FACTORIES
    args: Dict[str, Any] = field(default_factory=dict)
    params: List[tuple] = field(default_factory=list)  # (name, type, required, desc)
    cache: str = "public, max-age=60"


@dataclass(frozen=True)
class TechTheme:
    key: str
    label: str
    description: str
    noun: str
    resources: List[TechResource]
    components: List[str]
    quickstart: str               # resource name used in the quick-start example
    aliases: List[str] = field(default_factory=list)


_LIMIT = ("limit", "integer", False, "Maximum number of items to return.")
_CURSOR = ("cursor", "string", False, "Opaque pagination cursor from a previous response.")
_REGION = ("region", "string", False, "Restrict results to a single region code.")


TECHNICAL_THEMES: List[TechTheme] = [
    TechTheme(
        key="media-api",
        label="Media API",
        description="Programmatic media ingest, transcoding and delivery.",
        noun="Media",
        quickstart="media",
        components=["API", "Media Processing", "Delivery", "Storage"],
        resources=[
            TechResource("media", "Media", "List media objects in the current project.",
                         "collection", {"object_name": "media", "item": "media"},
                         [_LIMIT, _CURSOR]),
            TechResource("assets", "Assets", "List delivered assets and their cache state.",
                         "collection", {"object_name": "asset", "item": "asset"},
                         [_LIMIT]),
            TechResource("formats", "Formats", "Container and codec formats accepted on ingest.",
                         "enumeration",
                         {"key": "formats",
                          "values": ["image/jpeg", "image/png", "image/webp", "image/avif",
                                     "image/gif", "video/mp4", "video/webm", "audio/mpeg"]},
                         [], "public, max-age=3600"),
            TechResource("renditions", "Renditions", "Rendition presets applied during processing.",
                         "enumeration",
                         {"key": "renditions",
                          "values": ["thumb", "small", "medium", "large", "original",
                                     "poster", "preview"]},
                         [], "public, max-age=3600"),
        ],
    ),
    TechTheme(
        key="data-api",
        label="Data API",
        description="Structured collections, schemas and record access over HTTP.",
        noun="Data",
        quickstart="records",
        components=["API", "Query Engine", "Storage", "Replication"],
        resources=[
            TechResource("collections", "Collections", "List collections available to the project.",
                         "enumeration",
                         {"key": "collections",
                          "values": ["events", "documents", "entries", "metrics",
                                     "sessions", "profiles", "audit"]}),
            TechResource("records", "Records", "List records within a collection.",
                         "collection", {"object_name": "record", "item": "record"},
                         [_LIMIT, _CURSOR]),
            TechResource("schema", "Schema", "Field definitions for each collection.",
                         "schema_doc",
                         {"collections": ["events", "documents", "entries"]},
                         [], "public, max-age=3600"),
            TechResource("limits", "Limits", "Rate limits and request size ceilings.",
                         "limits", {}, [], "public, max-age=3600"),
        ],
    ),
    TechTheme(
        key="developer-api",
        label="Developer API",
        description="Application registration, scopes and usage reporting.",
        noun="Platform",
        quickstart="applications",
        components=["API", "Authentication", "Webhooks", "Usage Reporting"],
        resources=[
            TechResource("applications", "Applications", "Applications registered to the account.",
                         "collection", {"object_name": "application", "item": "app"},
                         [_LIMIT]),
            TechResource("scopes", "Scopes", "Permission scopes that may be granted to an application.",
                         "enumeration",
                         {"key": "scopes",
                          "values": ["read", "write", "admin", "events:read",
                                     "events:write", "usage:read", "webhooks"]},
                         [], "public, max-age=3600"),
            TechResource("usage", "Usage", "Aggregate request volume for the current period.",
                         "usage", {"unit": "requests"}, [], "no-store"),
            TechResource("limits", "Limits", "Rate limits applied per application.",
                         "limits", {}, [], "public, max-age=3600"),
        ],
    ),
    TechTheme(
        key="cdn",
        label="CDN Platform",
        description="Edge caching and asset delivery across regional points of presence.",
        noun="Edge",
        quickstart="assets",
        components=["Edge Network", "Cache", "Origin Shield", "Control API"],
        resources=[
            TechResource("regions", "Regions", "Points of presence and their current state.",
                         "regions", {}, [], "public, max-age=300"),
            TechResource("cache", "Cache", "Cache configuration and current hit ratio.",
                         "usage", {"unit": "requests"}, [], "no-store"),
            TechResource("assets", "Assets", "Recently requested assets and their cache status.",
                         "collection", {"object_name": "asset", "item": "asset"},
                         [_LIMIT, _REGION]),
            TechResource("limits", "Limits", "Request ceilings enforced at the edge.",
                         "limits", {}, [], "public, max-age=3600"),
        ],
    ),
    TechTheme(
        key="storage",
        label="Storage API",
        description="Object storage with regional buckets and lifecycle classes.",
        noun="Storage",
        quickstart="buckets",
        components=["API", "Object Store", "Replication", "Lifecycle"],
        resources=[
            TechResource("buckets", "Buckets", "Buckets owned by the account.",
                         "collection", {"object_name": "bucket", "item": "bucket"},
                         [_LIMIT, _REGION]),
            TechResource("objects", "Objects", "Objects within a bucket.",
                         "collection", {"object_name": "object", "item": "object"},
                         [_LIMIT, _CURSOR]),
            TechResource("regions", "Regions", "Regions in which buckets may be created.",
                         "regions", {}, [], "public, max-age=300"),
            TechResource("usage", "Usage", "Stored bytes and request counts for the period.",
                         "usage", {"unit": "bytes"}, [], "no-store"),
        ],
    ),
    TechTheme(
        key="image-api",
        label="Image API",
        description="On-the-fly image transformation and format negotiation.",
        noun="Image",
        quickstart="images",
        components=["API", "Transform Pipeline", "Cache", "Delivery"],
        resources=[
            TechResource("images", "Images", "Source images available for transformation.",
                         "collection", {"object_name": "image", "item": "media"},
                         [_LIMIT]),
            TechResource("transforms", "Transforms", "Supported transform operations.",
                         "enumeration",
                         {"key": "transforms",
                          "values": ["resize", "crop", "rotate", "blur", "sharpen",
                                     "grayscale", "quality", "format"]},
                         [], "public, max-age=3600"),
            TechResource("formats", "Formats", "Output formats available to the transform pipeline.",
                         "enumeration",
                         {"key": "formats",
                          "values": ["image/jpeg", "image/png", "image/webp",
                                     "image/avif", "image/gif"]},
                         [], "public, max-age=3600"),
            TechResource("presets", "Presets", "Named transform presets defined for the project.",
                         "enumeration",
                         {"key": "presets",
                          "values": ["thumbnail", "card", "hero", "avatar", "banner",
                                     "og-image"]},
                         [], "public, max-age=3600"),
        ],
    ),
    TechTheme(
        key="file-api",
        label="File API",
        description="File upload, retrieval and integrity verification.",
        noun="Files",
        quickstart="files",
        components=["API", "Upload Service", "Storage", "Virus Scanning"],
        resources=[
            TechResource("files", "Files", "Files stored under the current project.",
                         "collection", {"object_name": "file", "item": "file"},
                         [_LIMIT, _CURSOR]),
            TechResource("types", "Types", "Content types accepted on upload.",
                         "enumeration",
                         {"key": "types",
                          "values": ["application/pdf", "text/csv", "application/zip",
                                     "application/json", "text/plain", "image/png"]},
                         [], "public, max-age=3600"),
            TechResource("quota", "Quota", "Storage quota and current consumption.",
                         "usage", {"unit": "bytes"}, [], "no-store"),
            TechResource("limits", "Limits", "Upload size and rate limits.",
                         "limits", {}, [], "public, max-age=3600"),
        ],
    ),
    TechTheme(
        key="analytics",
        label="Analytics API",
        description="Event ingest and aggregate reporting.",
        noun="Analytics",
        quickstart="events",
        components=["Ingest", "Query Engine", "API", "Export"],
        resources=[
            TechResource("events", "Events", "Event types and their volume for the period.",
                         "collection", {"object_name": "event", "item": "event"},
                         [_LIMIT]),
            TechResource("metrics", "Metrics", "Metrics available for aggregation.",
                         "enumeration",
                         {"key": "metrics",
                          "values": ["sessions", "users", "events", "conversions",
                                     "duration", "bounce_rate"]},
                         [], "public, max-age=3600"),
            TechResource("dimensions", "Dimensions", "Dimensions by which metrics may be grouped.",
                         "enumeration",
                         {"key": "dimensions",
                          "values": ["country", "referrer", "device", "browser",
                                     "path", "source", "campaign"]},
                         [], "public, max-age=3600"),
            TechResource("usage", "Usage", "Ingested event volume for the period.",
                         "usage", {"unit": "events"}, [], "no-store"),
        ],
    ),
    TechTheme(
        key="platform",
        label="Developer Platform",
        description="Service deployment, environments and regional placement.",
        noun="Platform",
        quickstart="services",
        components=["Control API", "Scheduler", "Build Service", "Registry"],
        resources=[
            TechResource("services", "Services", "Services deployed under the account.",
                         "collection", {"object_name": "service", "item": "service"},
                         [_LIMIT]),
            TechResource("environments", "Environments", "Environments available for deployment.",
                         "enumeration",
                         {"key": "environments",
                          "values": ["production", "staging", "preview", "development"]},
                         [], "public, max-age=3600"),
            TechResource("regions", "Regions", "Regions in which services may be scheduled.",
                         "regions", {}, [], "public, max-age=300"),
            TechResource("limits", "Limits", "Platform quotas and request limits.",
                         "limits", {}, [], "public, max-age=3600"),
        ],
    ),
    TechTheme(
        key="status",
        label="Status Platform",
        description="Component status, incident history and uptime reporting.",
        noun="Status",
        quickstart="components",
        components=["Status API", "Monitoring", "Notifications", "Incident History"],
        resources=[
            TechResource("components", "Components", "Monitored components and their state.",
                         "enumeration",
                         {"key": "components",
                          "values": ["api", "dashboard", "ingest", "delivery",
                                     "notifications", "webhooks"]},
                         [], "public, max-age=60"),
            TechResource("incidents", "Incidents", "Recent incidents and their resolution.",
                         "collection", {"object_name": "incident", "item": "incident"},
                         [_LIMIT], "public, max-age=60"),
            TechResource("uptime", "Uptime", "Availability figures for the trailing period.",
                         "usage", {"unit": "checks"}, [], "no-store"),
            TechResource("regions", "Regions", "Regions from which checks are performed.",
                         "regions", {}, [], "public, max-age=300"),
        ],
    ),
    TechTheme(
        key="edge-network",
        label="Edge Network",
        description="Anycast edge nodes, routing and regional health.",
        noun="Edge",
        quickstart="nodes",
        components=["Edge Nodes", "Routing", "Control API", "Telemetry"],
        resources=[
            TechResource("nodes", "Nodes", "Edge nodes and their advertised capacity.",
                         "collection", {"object_name": "node", "item": "node"},
                         [_LIMIT, _REGION]),
            TechResource("regions", "Regions", "Regions served by the edge network.",
                         "regions", {}, [], "public, max-age=300"),
            TechResource("routes", "Routes", "Routing policies applied at the edge.",
                         "enumeration",
                         {"key": "routes",
                          "values": ["anycast", "geo", "latency", "weighted", "failover"]},
                         [], "public, max-age=3600"),
            TechResource("limits", "Limits", "Connection and request limits per node.",
                         "limits", {}, [], "public, max-age=3600"),
        ],
    ),
]

BY_KEY = {theme.key: theme for theme in TECHNICAL_THEMES}
