"""Print compact per-case summary for all 41 unsaved cases."""
import json
from pathlib import Path

CACHE = Path("/home/nn/SOTA-agents/analysis/4-middleware/v4_forensic/cache")

# helper
def trunc(s, n=200):
    if not s: return ""
    s = s.replace("\n", " ").strip()
    return s[:n] + ("..." if len(s) > n else "")

unsaved = []
for f in sorted(CACHE.glob("*.json"), key=lambda p: int(p.stem)):
    o = json.loads(f.read_text())
    if o["transition"] != "wrong->wrong":
        continue
    unsaved.append(o)

print(f"=== {len(unsaved)} unsaved cases ===\n")
for o in unsaved:
    di = o["dataset_index"]
    theme = o["primary_theme"]
    fault = f"{o['fault_category']}/{o['fault_type']}"
    tier = o["tier"]
    gt = o["gt"]["rc_service"]
    bl_pred = o["baseline"]["predicted_rc"]
    v4_pred = o["v4"]["predicted_rc"]
    bl_qpf = o["baseline"]["n_qpf"]
    v4_qpf = o["v4"]["n_qpf"]
    interv = o["v4"]["interventions"]
    n_int = len(interv)
    same_pred = bl_pred == v4_pred
    print(f"--- Case {di} | {theme} | {fault} | {tier} ---")
    print(f"  GT: {gt}")
    print(f"  baseline qpf={bl_qpf} pred={bl_pred}")
    print(f"  v4 qpf={v4_qpf} pred={v4_pred} | same_pred={same_pred} | n_interv={n_int}")
    for i, iv in enumerate(interv):
        sec = ",".join(iv.get("secondary", [])) or "-"
        rounds = iv["round_at_inject"]
        post = iv.get("post_intervention_tool_rounds", 0)
        resp = iv.get("agent_response_excerpt") or "(empty)"
        print(f"  [{iv['phase']:10s}] {iv['primary']}+[{sec}] @round={rounds} post={post}rounds")
        print(f"     resp: {trunc(resp, 250)}")
    # last 2 v4 reflections (final reasoning)
    final = o["v4"].get("final_reasoning_excerpts") or []
    if final:
        print(f"  v4 last reflection: {trunc(final[-1], 350)}")
    # last baseline reasoning to compare
    bl_refs = o["baseline"].get("reasoning_excerpts") or []
    if bl_refs:
        print(f"  baseline last  : {trunc(bl_refs[-1], 250)}")
    print()
