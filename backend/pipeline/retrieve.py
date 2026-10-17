"""Retrieval. Only the context filter exists so far; graph/vector search comes later.

Every query against doc_chunk or heuristic MUST include context_where() so nothing
outside the resolved system/version/site can be retrieved (CLAUDE.md rule 2).
"""


def context_where(table="", paramstyle="pyformat"):
    """SQL predicate restricting rows to the resolved context.

    NULL version_id/site_id means the row explicitly applies to all versions/sites
    (schema CHECKs tie NULL to all_versions/all_sites). system_id is never optional.
    paramstyle: "pyformat" for psycopg (%(name)s), "named" for sqlite (:name).
    """
    p = (lambda n: f"%({n})s") if paramstyle == "pyformat" else (lambda n: f":{n}")
    c = f"{table}." if table else ""
    return (f"{c}system_id = {p('system')}"
            f" AND ({c}version_id = {p('version')} OR {c}version_id IS NULL)"
            f" AND ({c}site_id = {p('site')} OR {c}site_id IS NULL)")


def context_params(ctx):
    """Params for context_where(). Refuses to run without a resolved system.

    An unresolved version/site stays None, which matches only all-versions/all-sites rows.
    """
    if not ctx or not ctx.get("system"):
        raise ValueError("context has no resolved system; clarify before retrieving")
    return {"system": ctx["system"], "version": ctx.get("version"), "site": ctx.get("site")}
