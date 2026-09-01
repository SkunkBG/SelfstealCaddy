"""Static word pools.

Everything here is invented.  No real company, product or trademark may enter
these lists: a decoy that borrows a recognisable brand is worse than no decoy,
because the mismatch between the name and the hosting is itself a signal.
"""

from __future__ import annotations

# --- brand composition ------------------------------------------------------
# Composed rather than enumerated: 4 shapes x these pools give a name space in
# the tens of thousands, so a 30-node fleet has no realistic collision risk.

TECH_PREFIX = [
    "Frame", "Pixel", "Asset", "Render", "Edge", "Cache", "Query", "Record",
    "Stream", "Vector", "Atlas", "Nimbus", "Quarry", "Lattice", "Beacon",
    "Harbor", "Slate", "Forge", "Delta", "Onyx", "Cinder", "Halcyon", "Vellum",
    "Kestrel", "Pivot", "Anchor", "Ridge", "Basalt", "Cobalt", "Tessera",
    "Umbra", "Verge", "Waypoint", "Zenith", "Aperture", "Bramble", "Citadel",
    "Drift", "Ember", "Fathom", "Glimmer", "Hollow", "Ingot", "Junction",
]

TECH_SUFFIX = [
    "Layer", "Grid", "Stack", "Base", "Core", "Node", "Works", "Labs",
    "Foundry", "Systems", "Point", "Line", "Bridge", "Field", "Mesh", "Frame",
    "Scale", "Path", "Depot", "Yard", "Loop", "Shift",
]

TECH_STANDALONE = [
    "Marlowe", "Verity", "Cavatica", "Peridot", "Solstice", "Ostara",
    "Thistle", "Wren", "Aurelia", "Brindle", "Corvid", "Dunlin", "Everlyn",
    "Fennec", "Gorse", "Hesper", "Ilex", "Juniper", "Kelvin", "Lumen",
    "Merle", "Nocturne", "Orrery", "Pelagic", "Quillon", "Rowan", "Sable",
]

COMPANY_SUFFIX = [
    "Technologies", "Systems", "Labs", "Networks", "Software", "Infrastructure",
    "Engineering", "Data", "Group", "Studio", "Collective", "Works",
]

LEGAL_SUFFIX = ["", "", "", " BV", " GmbH", " Ltd", " AB", " Oy", " SAS", " s.r.o."]

# --- geography --------------------------------------------------------------
# Display data only.  Nothing here is ever resolved, queried or compared
# against the machine's actual location.

REGIONS = [
    ("Frankfurt", "eu-central", "fra1", "DE"),
    ("Amsterdam", "eu-west", "ams1", "NL"),
    ("Helsinki", "eu-north", "hel1", "FI"),
    ("Stockholm", "eu-north", "sto1", "SE"),
    ("Warsaw", "eu-central", "waw1", "PL"),
    ("Vienna", "eu-central", "vie1", "AT"),
    ("Prague", "eu-central", "prg1", "CZ"),
    ("London", "eu-west", "lon1", "GB"),
    ("Paris", "eu-west", "par1", "FR"),
    ("Dublin", "eu-west", "dub1", "IE"),
    ("Zurich", "eu-central", "zrh1", "CH"),
    ("Milan", "eu-south", "mil1", "IT"),
    ("Madrid", "eu-south", "mad1", "ES"),
    ("Singapore", "ap-southeast", "sin1", "SG"),
    ("Tokyo", "ap-northeast", "nrt1", "JP"),
    ("Toronto", "na-east", "yyz1", "CA"),
    ("New York", "na-east", "nyc1", "US"),
]

CLASSIC_CITIES = [
    "Portland", "Austin", "Bristol", "Leeds", "Hamburg", "Aarhus", "Lyon",
    "Ghent", "Tallinn", "Porto", "Antwerp", "Utrecht", "Malmo", "Nantes",
    "Cork", "Bergen", "Turin", "Graz", "Leiden", "Kaunas",
]

# --- typography -------------------------------------------------------------
# Local stacks only.  A generated site must never reach a font CDN: one
# outbound request to a third party defeats the entire premise.

SANS_STACKS = [
    "system-ui,-apple-system,'Segoe UI',Roboto,Helvetica,Arial,sans-serif",
    "'Segoe UI',system-ui,Roboto,'Helvetica Neue',Arial,sans-serif",
    "Inter,system-ui,-apple-system,'Helvetica Neue',Arial,sans-serif",
    "-apple-system,BlinkMacSystemFont,'Segoe UI',Ubuntu,Cantarell,sans-serif",
    "ui-sans-serif,system-ui,'Liberation Sans',Arial,sans-serif",
]

MONO_STACKS = [
    "ui-monospace,SFMono-Regular,Menlo,Consolas,'Liberation Mono',monospace",
    "'SF Mono',Menlo,Monaco,Consolas,'DejaVu Sans Mono',monospace",
    "Consolas,'Andale Mono',Menlo,'Courier New',monospace",
    "ui-monospace,'Cascadia Mono',Menlo,'DejaVu Sans Mono',monospace",
]

SERIF_STACKS = [
    "ui-serif,Georgia,'Times New Roman',serif",
    "Georgia,'Iowan Old Style','Palatino Linotype',serif",
    "'Hoefler Text',Georgia,Cambria,'Times New Roman',serif",
]

# --- palettes ---------------------------------------------------------------
# (background, surface, ink, muted, border, accent) — technical themes.

TECH_PALETTES = [
    ("#ffffff", "#f7f8fa", "#14181f", "#5b6472", "#e3e7ed", "#2f6feb"),
    ("#ffffff", "#f6f8f7", "#12201b", "#566b62", "#dde6e1", "#1f7a5a"),
    ("#fdfdfc", "#f5f5f3", "#1b1a17", "#66625a", "#e6e4dd", "#a8541f"),
    ("#ffffff", "#f7f6fb", "#181528", "#615c78", "#e4e1ee", "#5b46c9"),
    ("#0f1419", "#171d26", "#e6e9ee", "#8b95a5", "#232b36", "#4c8dff"),
    ("#101512", "#171d19", "#e3e9e4", "#89968c", "#212a24", "#3fb27f"),
    ("#ffffff", "#f7f7f8", "#17181a", "#5e6167", "#e5e6e9", "#c2410c"),
    ("#fcfdff", "#f2f6fb", "#0f1b2a", "#54657a", "#dde6f0", "#0b6ea8"),
    ("#131316", "#1a1a1f", "#e8e8ec", "#90909c", "#26262e", "#e0a33a"),
    ("#ffffff", "#f8f7f5", "#1c1b1a", "#63605b", "#e8e5e0", "#7a3e9d"),
]

# --- shared vocabulary ------------------------------------------------------

STATUS_WORDS = ["operational", "operational", "operational", "degraded"]

TAGLINE_SHAPES = [
    "{noun} infrastructure for {audience}.",
    "{adjective} {noun} for {audience}.",
    "A {adjective} {noun} you can build on.",
    "{noun}, without the operational overhead.",
    "Built for {audience} who ship.",
]

AUDIENCES = [
    "product teams", "engineering teams", "small teams", "developers",
    "platform teams", "builders", "integration partners",
]
