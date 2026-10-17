"""Per-manual metadata: which subsystem entity and series/RVU entity each HPE manual is tagged with (ADR-004).

Honesty notes (also in docs/RAG_SPIKE.md): every manual here is a J/H-era edition. `version_id` holds ONE
series, but most manuals state support for several (e.g. "J06.03 and subsequent J-series, H06.03 and
subsequent H-series"). We tag the lowest-risk single value and keep the full statement in `supports`.
The TMF Reference is H-series only (H06.03+), so it is tagged rvu:H. L-series (NonStop X) is not
covered by any of these editions - behaviour there is UNKNOWN.

ADR-005: because the PROD node is L-series, an exact `version_id` filter would return nothing. Manual chunks are
therefore stored with version_id NULL / all_versions TRUE (explicit, ADR-001) and the REAL edition is kept in
`doc_chunk.edition` (see `edition_label`) so citations can say "J/H-series edition; L-series not verified".
`version_id` below is only the series the manual's cover page names first (documentation, not a filter).
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class Manual:
    key: str            # file stem in data/raw/hpe, also the doc id prefix
    system_id: str      # subsystem entity (kind 'system')
    system_name: str
    version_id: str     # series entity (kind 'version')
    supports: str       # what the cover page claims
    published: str      # ISO date (day is arbitrary: cover gives month only)
    edition: str
    title: str = ""     # manual title for citations
    series_label: str = "J/H-series"  # which series the cover page names

    @property
    def doc_version(self):
        """Publisher part number, e.g. '540138-001'."""
        return self.edition.split(",")[0].strip()

    @property
    def edition_label(self):
        """Stored in doc_chunk.edition, e.g. 'TMF Reference Manual, H-series edition (540138-001, July 2005)'."""
        return f"{self.title}, {self.series_label} edition ({self.edition})"


MANUALS = [
    Manual("TMF-Reference", "sub:TMF", "TMF (TMFCOM)", "rvu:H",
           "H06.03 and subsequent H-series RVUs", "2005-07-01", "540138-001, July 2005", title="TMF Reference Manual", series_label="H-series"),
    Manual("Pathway", "sub:PATHWAY", "Pathway/iTS (PATHCOM, TCP)", "rvu:J",
           "J06.03+ and H06.03+", "2009-05-01", "426748-005, May 2009", title="Pathway/iTS manual", series_label="J/H-series"),
    Manual("SCF-Storage", "sub:SCF-STORAGE", "SCF Storage subsystem", "rvu:J",
           "J06.03+, H06.05+, G06.28+", "2014-02-01", "529937-022, Feb 2014", title="SCF Reference Manual for the Storage Subsystem", series_label="J/H-series"),
    Manual("TACL-Reference", "sub:TACL", "TACL", "rvu:J",
           "J06.03+, H06.03+, G06.20+, D46.00+", "2013-08-01", "429513-017, Aug 2013", title="TACL Reference Manual", series_label="J/H-series"),
    Manual("PEEK", "sub:PEEK", "PEEK", "rvu:J",
           "J06.03+, H06.03+, G06.12+", "2010-05-01", "529657-005, May 2010", title="PEEK Utility Reference", series_label="J/H-series"),
    Manual("measure", "sub:MEASURE", "Measure (MEASCOM)", "rvu:J",
           "J06.03+, H06.03+, G06.03+, D40.00+", "2010-03-01", "523324-013, Mar 2010", title="Measure Reference Manual", series_label="J/H-series"),
    Manual("FUP", "sub:FUP", "FUP", "rvu:J",
           "J06.03+, H06.03+, G06.23+, D46.00+", "2009-10-01", "523323-012, Oct 2009", title="FUP Reference Manual", series_label="J/H-series"),
]
BY_KEY = {m.key: m for m in MANUALS}

# Entities the loader guarantees exist (kind per the schema CHECK; see ADR-004).
VERSION_ENTITIES = [("rvu:J", "J-series (Itanium)"), ("rvu:H", "H-series"), ("rvu:L", "L-series (NonStop X)")]
SITE_ENTITIES = [("node:PROD", "PROD"), ("node:DR", "DR")]
