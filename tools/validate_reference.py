#!/usr/bin/env python3
import argparse, json
from collections import Counter, defaultdict
from pathlib import Path

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("reference_json")
    args = ap.parse_args()

    data = json.loads(Path(args.reference_json).read_text(encoding="utf-8"))
    records = data["interfaces"]

    names = {r["name"] for r in records}
    alias_to_name = {}
    for r in records:
        for a in r.get("aliases", []):
            alias_to_name[a] = r["name"]

    def resolve(x):
        return x if x in names else alias_to_name.get(x, x)

    dup_sdk = [k for k,v in Counter(r["sdk_id"] for r in records).items() if v > 1]
    unresolved_out = []
    unresolved_in = []
    out_pairs, in_pairs = [], []

    for r in records:
        for e in r.get("outgoing_link_constraints", []):
            t = resolve(e.get("target_interface"))
            if t not in names:
                unresolved_out.append((r["name"], e.get("name"), e.get("target_interface")))
            out_pairs.append((r["name"], t))
        for e in r.get("incoming_link_constraints", []):
            s = resolve(e.get("target_interface"))
            if s not in names:
                unresolved_in.append((e.get("target_interface"), e.get("name"), r["name"]))
            in_pairs.append((s, r["name"]))

    out_set, in_set = set(out_pairs), set(in_pairs)
    result = {
        "records": len(records),
        "duplicate_sdk_ids": dup_sdk,
        "unresolved_outgoing": unresolved_out,
        "unresolved_incoming": unresolved_in,
        "outgoing_without_incoming_pair": sorted(out_set - in_set),
        "incoming_without_outgoing_pair": sorted(in_set - out_set),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
