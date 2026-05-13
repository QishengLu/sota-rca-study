"""
Dump a trajectory as human-readable plain text with turn numbers + role + tool names + content excerpts.
Marks v4 intervention boundaries.

Usage:
    UTU_DB_URL=postgresql://... python dump_trajectory.py <exp_id> <dataset_index> [--full]
"""
import os, sys, json, re
from sqlalchemy import create_engine, text

ADV_RE = re.compile(r"\[Investigation Advisor\s*[—\-]\s*v4\]\s*phase=(\w+)\s+primary=(\w+)(?:\s+secondary=(\S+))?", re.IGNORECASE)


def short(s, n=300):
    if not s: return ""
    s = s.replace("\n", " ").strip()
    return s[:n] + ("..." if len(s) > n else "")


def main():
    exp_id = sys.argv[1]
    di = int(sys.argv[2])
    full = "--full" in sys.argv

    eng = create_engine(os.environ["UTU_DB_URL"])
    with eng.connect() as c:
        r = c.execute(text(
            "SELECT trajectories::text, response, correct, correct_answer FROM evaluation_data "
            "WHERE exp_id=:e AND dataset_index=:d"
        ), {"e": exp_id, "d": di}).fetchone()
        if not r:
            print(f"No record found for {exp_id} #{di}")
            return
        traj = json.loads(r[0]) if r[0] else []
        resp = r[1]
        correct = r[2]
        gt = r[3]

    print(f"=== exp_id={exp_id} dataset_index={di} ===")
    print(f"GT root cause: {gt}")
    print(f"Final correct: {correct}")
    print(f"Total messages: {len(traj)}")
    print()

    round_num = 0  # count assistant w/ tool_calls = 1 round
    intervention_count = 0

    for i, m in enumerate(traj):
        role = m.get("role") or m.get("type", "?")
        content = m.get("content") or ""
        tc = m.get("tool_calls") or []
        is_intervention = role == "user" and "Investigation Advisor" in content

        if is_intervention:
            intervention_count += 1
            match = ADV_RE.search(content)
            phase = match.group(1) if match else "?"
            primary = match.group(2) if match else "?"
            secondary = match.group(3) if match else "[]"
            print(f"\n{'!'*80}")
            print(f"!!! [v4 干预 #{intervention_count}] msg_idx={i}  之前 round_count={round_num}")
            print(f"!!! phase={phase}  primary={primary}  secondary={secondary}")
            print(f"!!! ↓ 完整干预文 ↓")
            print(content if full else short(content, 800))
            print(f"{'!'*80}\n")
            continue

        if role == "assistant" and tc:
            round_num += 1
            tool_names = [t.get("function", {}).get("name", "?") for t in tc]
            print(f"[Round {round_num}] (msg_idx={i}) assistant  tools={tool_names}")
            # Print tool args for each
            for t in tc:
                fname = t.get("function", {}).get("name", "?")
                args = t.get("function", {}).get("arguments", "")
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except Exception:
                        pass
                # extract sql or query if present
                hint = ""
                if isinstance(args, dict):
                    if "sql" in args:
                        hint = f"SQL: {short(args['sql'], 200 if not full else 1000)}"
                    elif "reflection" in args:
                        hint = f"reflection: {short(args['reflection'], 250 if not full else 1500)}"
                    elif "query" in args:
                        hint = f"query: {short(args['query'], 200)}"
                    else:
                        hint = short(json.dumps(args, ensure_ascii=False), 250)
                if hint:
                    print(f"    [{fname}] {hint}")
        elif role == "tool":
            tool_name = m.get("name", "?")
            short_c = short(content, 250 if not full else 1500)
            print(f"  ↳ tool result ({tool_name}): {short_c}")
        elif role == "assistant" and not tc:
            # final compress / answer
            print(f"\n[FINAL assistant @ msg_idx={i}]")
            print(short(content, 500 if not full else 5000))
        elif role == "user":
            # initial user prompt or other
            print(f"\n[user @ msg_idx={i}] {short(content, 200)}")

    print(f"\n=== 总结 ===")
    print(f"Total rounds (with tool_calls): {round_num}")
    print(f"Total v4 interventions: {intervention_count}")


if __name__ == "__main__":
    main()
