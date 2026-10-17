"""Research-only Torvik neutral-court efficiency baseline for RAPM possessions.
Do not apply this as a multiplier to existing player RAPM coefficients.
Requires independently checked JSON snapshot AND ESPN IDs.
"""
import json
from pathlib import Path
def load_context(path):
    source=json.loads(Path(path).read_text())
    teams=source.get("teams",[])
    if not teams or not source.get("season"):
        raise ValueError("Invalid Torvik snapshot")
    lookup={str(r["espnTeamId"]):r for r in teams if r.get("espnTeamId")}
    if not lookup:raise ValueError("No verified ESPN team IDs")
    return {"season":source["season"],"source":source.get("sourceFormat"),
            "offMean":sum(r["adjOE"] for r in teams)/len(teams),
            "defMean":sum(r["adjDE"] for r in teams)/len(teams),"byId":lookup}
def expected_points_per_100(off_id,def_id,context):
    offense=context["byId"].get(str(off_id))
    defense=context["byId"].get(str(def_id))
    if offense is None or defense is None:return None
    return offense["adjOE"]+defense["adjDE"]-context["defMean"]
def research_possession_offset(possession,context):
    """Used *inside a refit*, preserving teammate/opponent regressors."""
    p100=expected_points_per_100(possession["off_team"],possession["def_team"],context)
    if p100 is None:return None
    return float(possession["points"])-(p100-context["offMean"])/100
