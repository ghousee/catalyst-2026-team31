"""In-memory demo state shared by the API routers (single demo user; resets on restart)."""
NODES = [{"id": "node:PROD", "display": "\\PROD"}, {"id": "node:DR", "display": "\\DR"}]
SESSION = {"node": "node:PROD", "series": "rvu:L", "user": "OPS.NEWHIRE"}


def node_display(node_id):
    return "\\" + node_id.split(":", 1)[1]
