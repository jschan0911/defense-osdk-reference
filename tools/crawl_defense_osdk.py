#!/usr/bin/env python3
"""Palantir Defense OSDK public API reference crawler (v0.1).

Purpose
-------
Create a reproducible snapshot of the public Defense OSDK interface reference:
  domain -> interface -> properties -> inheritance -> link constraints.

The crawler intentionally separates RAW capture from NORMALIZED parsing so that
parser mistakes never destroy the source snapshot. It discovers interface pages
from the official API root rather than recursively crawling the whole site.

Usage
-----
  python crawl_defense_osdk.py --out ./out
  python crawl_defense_osdk.py --out ./out --domains common orderOfBattle

Dependencies
------------
  requests beautifulsoup4
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Optional
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup, Tag

ROOT = "https://www.palantir.com/docs/defense-osdk/api"
UA = "DefenseOSDKReferenceCrawler/0.1 (+ontology research; low-rate public-doc snapshot)"
INTERFACE_RE = re.compile(
    r"^/docs/defense-osdk/api/(?P<domain>[^/]+)/interfaceTypes/(?P<slug>[^/?#]+)/?$"
)
SECTION_NAMES = {
    "properties": "Properties",
    "extended_interfaces": "Extended interfaces",
    "extended_by": "Extended by",
    "link_constraints": "Link constraints",
    "incoming_link_constraints": "Incoming link constraints",
}
CARDINALITIES = {"One To One", "One To Many", "Many To One", "Many To Many"}
REQ_TOKENS = {"optional", "required"}


@dataclass
class Property:
    name: Optional[str] = None
    type: Optional[str] = None
    required: Optional[bool] = None
    description: Optional[str] = None
    raw_header: list[str] = field(default_factory=list)


@dataclass
class LinkConstraint:
    name: Optional[str] = None
    target_interface: Optional[str] = None
    cardinality: Optional[str] = None
    required: Optional[bool] = None
    description: Optional[str] = None
    direction: str = "outgoing"
    raw_header: list[str] = field(default_factory=list)


@dataclass
class Interface:
    domain: str
    name: str
    slug: str
    sdk_id: str
    url: str
    description: Optional[str] = None
    declared_properties: list[Property] = field(default_factory=list)
    extends: list[str] = field(default_factory=list)
    extended_by: list[str] = field(default_factory=list)
    outgoing_link_constraints: list[LinkConstraint] = field(default_factory=list)
    incoming_link_constraints: list[LinkConstraint] = field(default_factory=list)
    parser_warnings: list[str] = field(default_factory=list)
    parser_status: str = "ok"
    source_sha256: Optional[str] = None


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def clean(s: str) -> str:
    return re.sub(r"\s+", " ", s or "").strip()


def sdk_id_from_slug(slug: str) -> str:
    prefix = "com-palantir-ontology-defense-types-"
    if slug.startswith(prefix):
        return "com.palantir.ontology.defense-types." + slug[len(prefix):]
    return slug


def request(session: requests.Session, url: str, timeout: int, retries: int, delay: float) -> requests.Response:
    last = None
    for attempt in range(retries + 1):
        try:
            r = session.get(url, timeout=timeout)
            r.raise_for_status()
            if delay:
                time.sleep(delay)
            return r
        except requests.RequestException as exc:
            last = exc
            if attempt < retries:
                time.sleep(min(2 ** attempt, 8))
    raise RuntimeError(f"Failed GET {url}: {last}")


def discover_interfaces(html: str, root_url: str = ROOT) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    found: dict[str, dict] = {}
    for a in soup.find_all("a", href=True):
        href = a.get("href", "")
        absolute = urljoin(root_url + "/", href)
        p = urlparse(absolute)
        m = INTERFACE_RE.match(p.path)
        if not m:
            continue
        url = f"{p.scheme}://{p.netloc}{p.path.rstrip('/')}"
        found[url] = {
            "domain": m.group("domain"),
            "slug": m.group("slug"),
            "name_hint": clean(a.get_text(" ", strip=True)),
            "url": url,
        }
    return sorted(found.values(), key=lambda x: (x["domain"], x["name_hint"], x["url"]))


def main_node(soup: BeautifulSoup) -> Tag:
    return soup.find("main") or soup.find("article") or soup.body or soup


def first_h1(main: Tag) -> Optional[Tag]:
    return main.find("h1")


def description_after_h1(main: Tag, h1: Optional[Tag]) -> Optional[str]:
    if not h1:
        return None
    chunks: list[str] = []
    for el in h1.find_all_next():
        if el is h1:
            continue
        if isinstance(el, Tag) and el.name == "h2":
            break
        if isinstance(el, Tag) and el.name in {"p"}:
            t = clean(el.get_text(" ", strip=True))
            if t and t != "Palantir Defense OSDK":
                chunks.append(t)
    if chunks:
        return clean(" ".join(chunks))
    return None


def section_node(main: Tag, heading: str) -> Optional[Tag]:
    for h in main.find_all("h2"):
        if clean(h.get_text(" ", strip=True)).lower() == heading.lower():
            return h
    return None


def section_text_lines(h2: Optional[Tag]) -> list[str]:
    """Collect text blocks after an h2 until the next h2.

    This preserves element-level text and deduplicates adjacent duplicates. Raw
    headers are retained in output when a heuristic cannot confidently split a
    property/link name and type/target.
    """
    if not h2:
        return []
    out: list[str] = []
    # Iterate document order. Only keep relatively small text-bearing elements
    # to avoid repeating a whole wrapper's concatenated text.
    for el in h2.find_all_next():
        if el is h2:
            continue
        if isinstance(el, Tag) and el.name == "h2":
            break
        if not isinstance(el, Tag):
            continue
        if el.name in {"p", "a", "button", "code", "span", "div", "li"}:
            # Skip wrappers that have block children: their text will be emitted by children.
            if any(isinstance(c, Tag) and c.name in {"div", "p", "li"} for c in el.children):
                continue
            t = clean(el.get_text(" ", strip=True))
            if not t:
                continue
            # Exclude common UI/noise.
            if t in {"↗", "·", "Copied!", "TypeScript"}:
                continue
            if not out or out[-1] != t:
                out.append(t)
    return out


def is_description(s: str) -> bool:
    return s.startswith("[Palantir Defense Ontology]")


def groups_ending_in_description(lines: list[str]) -> list[tuple[list[str], str]]:
    groups: list[tuple[list[str], str]] = []
    buf: list[str] = []
    for line in lines:
        if is_description(line):
            groups.append((buf[:], line))
            buf.clear()
        else:
            buf.append(line)
    return groups


def parse_properties(lines: list[str]) -> tuple[list[Property], list[str]]:
    props: list[Property] = []
    warnings: list[str] = []
    for header, desc in groups_ending_in_description(lines):
        header = [x for x in header if x not in {"Properties"}]
        # Remove accidental repeats while preserving order.
        compact: list[str] = []
        for x in header:
            if not compact or compact[-1] != x:
                compact.append(x)
        header = compact
        req: Optional[bool] = None
        for x in list(header):
            xl = x.lower()
            if xl in REQ_TOKENS:
                req = xl == "required"
                header.remove(x)
        # Common scalar types. Non-scalar button/enum types may be multiword.
        scalar = {"string", "date", "datetime", "timestamp", "boolean", "integer", "long", "double", "float", "decimal"}
        name = typ = None
        scalar_idx = next((i for i, x in enumerate(header) if x.lower() in scalar), None)
        if scalar_idx is not None:
            name = " ".join(header[:scalar_idx]) or None
            typ = header[scalar_idx]
        elif len(header) >= 2:
            # Best effort: page often repeats the display label for an enum/interface type.
            half = len(header) // 2
            if len(header) % 2 == 0 and header[:half] == header[half:]:
                name = " ".join(header[:half])
                typ = " ".join(header[half:])
            else:
                name = header[0]
                typ = " ".join(header[1:])
        elif len(header) == 1:
            name = header[0]
            warnings.append(f"Property type unresolved for: {name}")
        else:
            warnings.append(f"Property header missing before description: {desc[:80]}")
        props.append(Property(name=name, type=typ, required=req, description=desc, raw_header=header))
    return props, warnings


def parse_interface_list(lines: list[str]) -> list[str]:
    out: list[str] = []
    for x in lines:
        if x in {"Extended interfaces", "Extended by"} or is_description(x):
            continue
        # Ignore UI/SDK example noise if any leaks in.
        if x.startswith("Load ") or x == "Code snippets":
            continue
        if x not in out:
            out.append(x)
    return out


def parse_link_header(header: list[str]) -> tuple[Optional[str], Optional[str], Optional[str], Optional[bool], list[str]]:
    raw = header[:]
    header = [x for x in header if x not in {"Link constraints", "Incoming link constraints"}]
    req: Optional[bool] = None
    card: Optional[str] = None
    # Normalize cardinality strings if split across nodes.
    joined = " ".join(header)
    for c in CARDINALITIES:
        if c in joined:
            card = c
            # remove exact cardinality element if present
            header = [x for x in header if x != c]
            if c not in header and c in " ".join(header):
                joined2 = " ".join(header).replace(c, " ")
                header = [clean(joined2)] if clean(joined2) else []
            break
    cleaned: list[str] = []
    for x in header:
        xl = x.lower()
        if xl in REQ_TOKENS:
            req = xl == "required"
        elif x not in {"↗", "·"}:
            cleaned.append(x)
    header = cleaned
    name = target = None
    if header:
        # Preferred rendered pattern: Relation→Target or Source→Relation for incoming.
        arrow_line = next((x for x in header if "→" in x), None)
        if arrow_line:
            left, right = arrow_line.split("→", 1)
            name = clean(left.replace("↗", "").replace("·", "")) or None
            target = clean(right.replace("↗", "").replace("·", "")) or None
        elif len(header) >= 2:
            name, target = header[0], header[1]
        else:
            name = header[0]
    return name, target, card, req, raw


def parse_links(lines: list[str], direction: str) -> tuple[list[LinkConstraint], list[str]]:
    links: list[LinkConstraint] = []
    warnings: list[str] = []
    for header, desc in groups_ending_in_description(lines):
        name, target, card, req, raw = parse_link_header(header)
        if target is None:
            warnings.append(f"Link target unresolved ({direction}): {name or raw}")
        if card is None:
            warnings.append(f"Cardinality unresolved ({direction}): {name or raw}")
        links.append(LinkConstraint(
            name=name,
            target_interface=target,
            cardinality=card,
            required=req,
            description=desc,
            direction=direction,
            raw_header=raw,
        ))
    return links, warnings


def parse_interface(html: str, meta: dict) -> Interface:
    soup = BeautifulSoup(html, "html.parser")
    main = main_node(soup)
    h1 = first_h1(main)
    name = clean(h1.get_text(" ", strip=True)) if h1 else (meta.get("name_hint") or meta["slug"])
    iface = Interface(
        domain=meta["domain"],
        name=name,
        slug=meta["slug"],
        sdk_id=sdk_id_from_slug(meta["slug"]),
        url=meta["url"],
        description=description_after_h1(main, h1),
        source_sha256=hashlib.sha256(html.encode("utf-8")).hexdigest(),
    )
    props_h = section_node(main, SECTION_NAMES["properties"])
    ext_h = section_node(main, SECTION_NAMES["extended_interfaces"])
    by_h = section_node(main, SECTION_NAMES["extended_by"])
    out_h = section_node(main, SECTION_NAMES["link_constraints"])
    in_h = section_node(main, SECTION_NAMES["incoming_link_constraints"])

    iface.declared_properties, w = parse_properties(section_text_lines(props_h))
    iface.parser_warnings.extend(w)
    iface.extends = parse_interface_list(section_text_lines(ext_h))
    iface.extended_by = parse_interface_list(section_text_lines(by_h))
    iface.outgoing_link_constraints, w = parse_links(section_text_lines(out_h), "outgoing")
    iface.parser_warnings.extend(w)
    iface.incoming_link_constraints, w = parse_links(section_text_lines(in_h), "incoming")
    iface.parser_warnings.extend(w)

    if not h1:
        iface.parser_warnings.append("Missing h1")
    if not iface.description:
        iface.parser_warnings.append("Missing interface description")
    if iface.parser_warnings:
        iface.parser_status = "warning"
    return iface


def validate(interfaces: list[Interface]) -> dict:
    by_name = {i.name: i for i in interfaces}
    by_slug_name = set(by_name)
    unresolved_extends = []
    unresolved_links = []
    for i in interfaces:
        for parent in i.extends:
            # Cross-domain/base interfaces may not be listed on the Defense OSDK root.
            if parent not in by_slug_name:
                unresolved_extends.append({"interface": i.name, "extends": parent, "note": "may be external/base interface"})
        for link in i.outgoing_link_constraints:
            if link.target_interface and link.target_interface not in by_slug_name:
                unresolved_links.append({"interface": i.name, "link": link.name, "target": link.target_interface})
    return {
        "interface_count": len(interfaces),
        "domain_counts": _domain_counts(interfaces),
        "parser_warning_count": sum(1 for i in interfaces if i.parser_warnings),
        "unresolved_extends": unresolved_extends,
        "unresolved_outgoing_targets": unresolved_links,
    }


def _domain_counts(interfaces: Iterable[Interface]) -> dict[str, int]:
    d: dict[str, int] = {}
    for i in interfaces:
        d[i.domain] = d.get(i.domain, 0) + 1
    return dict(sorted(d.items()))


def write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def main_cli() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="defense_osdk_snapshot", help="Output directory")
    ap.add_argument("--root", default=ROOT)
    ap.add_argument("--domains", nargs="*", help="Optional domain slugs to include, e.g. common orderOfBattle")
    ap.add_argument("--delay", type=float, default=0.5, help="Delay after each request (seconds)")
    ap.add_argument("--timeout", type=int, default=30)
    ap.add_argument("--retries", type=int, default=2)
    ap.add_argument("--limit", type=int, default=0, help="Optional interface limit for pilot runs")
    args = ap.parse_args()

    out = Path(args.out)
    raw_dir = out / "raw" / "pages"
    raw_dir.mkdir(parents=True, exist_ok=True)

    s = requests.Session()
    s.headers.update({"User-Agent": UA, "Accept": "text/html,application/xhtml+xml"})

    root_r = request(s, args.root, args.timeout, args.retries, args.delay)
    (out / "raw" / "root.html").write_text(root_r.text, encoding="utf-8")
    discovered = discover_interfaces(root_r.text, args.root)
    if args.domains:
        allowed = set(args.domains)
        discovered = [x for x in discovered if x["domain"] in allowed]
    if args.limit:
        discovered = discovered[: args.limit]

    snapshot = {
        "source": "Palantir Defense OSDK public API Reference",
        "root_url": args.root,
        "captured_at_utc": utc_now(),
        "interface_pages_discovered": len(discovered),
        "domains_requested": args.domains or "all",
        "items": discovered,
    }
    write_json(out / "raw" / "manifest.json", snapshot)

    parsed: list[Interface] = []
    failures: list[dict] = []
    for idx, meta in enumerate(discovered, 1):
        print(f"[{idx}/{len(discovered)}] {meta['domain']} :: {meta['name_hint'] or meta['slug']}", file=sys.stderr)
        try:
            r = request(s, meta["url"], args.timeout, args.retries, args.delay)
            raw_path = raw_dir / f"{meta['domain']}__{meta['slug']}.html"
            raw_path.write_text(r.text, encoding="utf-8")
            parsed.append(parse_interface(r.text, meta))
        except Exception as exc:
            failures.append({**meta, "error": repr(exc)})

    normalized = {
        "snapshot": {
            "source": snapshot["source"],
            "root_url": args.root,
            "captured_at_utc": snapshot["captured_at_utc"],
            "note": "Interfaces are abstract API shapes; they are not instantiable object types/backing datasets.",
        },
        "interfaces": [asdict(i) for i in parsed],
    }
    write_json(out / "normalized" / "defense_osdk.json", normalized)
    write_json(out / "validation" / "crawl_failures.json", failures)
    write_json(out / "validation" / "integrity_report.json", validate(parsed))

    # Flat relationship export useful for graph import/comparison.
    rels = []
    for i in parsed:
        for link in i.outgoing_link_constraints:
            rels.append({
                "source_interface": i.name,
                "source_sdk_id": i.sdk_id,
                "relation": link.name,
                "target_interface": link.target_interface,
                "cardinality": link.cardinality,
                "required": link.required,
                "description": link.description,
            })
    write_json(out / "normalized" / "relations.json", rels)

    print(json.dumps({
        "discovered": len(discovered),
        "parsed": len(parsed),
        "failures": len(failures),
        "warnings": sum(1 for i in parsed if i.parser_warnings),
        "domain_counts": _domain_counts(parsed),
    }, ensure_ascii=False, indent=2))
    return 0 if not failures else 2


if __name__ == "__main__":
    raise SystemExit(main_cli())
