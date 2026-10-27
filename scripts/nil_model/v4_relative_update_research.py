#!/usr/bin/env python3
"""Research-only V4 anchored NIL updating, no live publication.

Only VERIFIED V4 ESPN-ID priors are accepted. The auxiliary pricing model's
preseason prediction is a frozen reference, never a replacement for V4.
The same frozen auxiliary model release must score current-season evidence.
No player-level Torvik dependency or private valuation is stored here.
"""
import argparse
import datetime
import json
import math
from pathlib import Path

MIN_VALUE = 20_000
MAX_VALUE = 20_000_000

def date(value):
    try:
        return datetime.date.fromisoformat(str(value)[:10])
    except (ValueError, TypeError):
        raise ValueError("Invalid date")

def money(value):
    if type(value) not in (int, float) or not math.isfinite(value) or not MIN_VALUE <= value <= MAX_VALUE:
        raise ValueError("Invalid dollar valuation")
    return float(value)

def price(row):
    return money(row["value"] if isinstance(row, dict) else row)

def evidence_weight(games, minutes, prior_minutes=0, prior_games=0):
    """Current website evidence policy; requires future historical calibration."""
    v = (games, minutes, prior_minutes, prior_games)
    if any(type(x) not in (int, float) or not math.isfinite(x) or x < 0 for x in v):
        raise ValueError("Invalid exposure")
    if not games or not minutes:
        return 0.
    if games > 42 or minutes > games * 60:
        raise ValueError("Implausible exposure")
    avg = min(42, minutes / games)
    effective = games * (.40 + .60 * min(1.55, avg / 22) ** .75)
    prior_strength = 8.5 if prior_minutes >= 300 and prior_games >= 12 else (6.5 if prior_minutes >= 90 else 5.5)
    x = effective ** 1.65
    return min(.999, x / (x + prior_strength ** 1.65))

def anchored_price(v4_price, aux_preseason, aux_current, games, minutes, prior_minutes=0, prior_games=0):
    original = money(v4_price)
    auxiliary_start = money(aux_preseason)
    weight = evidence_weight(games, minutes, prior_minutes, prior_games)
    if weight == 0:
        return round(original), weight
    auxiliary_now = money(aux_current)
    shift = math.log(auxiliary_now / auxiliary_start)
    if abs(shift) > math.log(4):
        raise ValueError("Unverified greater-than-fourfold auxiliary change")
    updated = original * math.exp(weight * shift)
    if not MIN_VALUE <= updated <= MAX_VALUE:
        raise ValueError("Updated price outside permitted range")
    return round(updated), weight

def compute(baseline, reference, current, as_of):
    for source in (baseline, reference, current):
        if source.get("schemaVersion") != 1 or source.get("season") != 2027 or not isinstance(source.get("byESPNId"), dict):
            raise ValueError("Bad research file or year")
    if baseline.get("model") != "V4_VERIFIED" or not baseline.get("provenance"):
        raise ValueError("Missing independently verified V4 provenance")
    anchor = date(baseline.get("asOf"))
    now = date(as_of)
    if now < anchor or date(reference.get("generatedAsOf")) > anchor or date(current.get("generatedAsOf")) > now:
        raise ValueError("As-of chronology failed")
    if reference.get("baselineAsOf") != baseline.get("asOf"):
        raise ValueError("Auxiliary preseason anchor mismatch")
    if not reference.get("modelVersion") or reference.get("modelVersion") != current.get("modelVersion"):
        raise ValueError("Auxiliary model was changed or retrained without rebasing")
    if not reference.get("sourceFingerprint") or reference["sourceFingerprint"] != current.get("referenceFingerprint"):
        raise ValueError("Frozen reference snapshot fingerprint mismatch")
    prices = baseline["byESPNId"]
    reference_prices = reference["byESPNId"]
    if not prices or not set(prices).issubset(reference_prices):
        raise ValueError("V4 players missing from auxiliary preseason reference")
    output = {}
    rejected = []
    for pid in sorted(prices, key=int):
        if not pid.isdigit():
            raise ValueError("Non-ESPN identity")
        v4 = price(prices[pid])
        old = price(reference_prices[pid])
        obs = current["byESPNId"].get(pid)
        if not isinstance(obs, dict):
            output[pid] = {"value": round(v4), "preseason": round(v4), "status": "FROZEN_MISSING_CURRENT", "weight": 0.}
            continue
        try:
            gp = obs["games"]
            minutes = obs["minutes"]
            if now <= anchor and gp and minutes:
                raise ValueError("Cannot report evidence before preseason anchor")
            p, w = anchored_price(v4, old, obs.get("value") if gp and minutes else old, gp, minutes,
                                  obs.get("priorMinutes", 0), obs.get("priorGames", 0))
            status = "UPDATED" if w > 0 else "PRESEASON_V4"
        except (ValueError, KeyError, TypeError) as error:
            p, w, status = round(v4), 0., "REVIEW_REQUIRED"
            rejected.append({"id": pid, "reason": str(error)})
        output[pid] = {"value": p, "preseason": round(v4), "status": status, "weight": round(w, 6)}
    return ({"schemaVersion": 1, "season": 2027, "releaseStatus": "RESEARCH_NOT_PUBLISHED",
             "asOf": now.isoformat(), "preseasonAsOf": anchor.isoformat(),
             "auxiliaryModelVersion": reference["modelVersion"],
             "playerCount": len(output), "byESPNId": output},
            {"rejected": rejected, "publishReady": False,
             "warning": "No national V4 publish until verified full baseline coverage and historical backtest"})

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    for flag in ("baseline", "reference", "current", "as-of", "output"):
        ap.add_argument("--" + flag, required=True)
    args = ap.parse_args()
    load = lambda p: json.loads(Path(p).read_text())
    result, qa = compute(load(args.baseline), load(args.reference), load(args.current), args.as_of)
    path = Path(args.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, separators=(",", ":")) + "\n")
    path.with_suffix(".qa.json").write_text(json.dumps(qa, indent=2) + "\n")
    print(json.dumps({"candidateCount": result["playerCount"], "rejected": len(qa["rejected"]), "publishReady": False}))

if __name__ == "__main__":
    main()
