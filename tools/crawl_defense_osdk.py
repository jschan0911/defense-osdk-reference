#!/usr/bin/env python3
"""Palantir Defense OSDK public API reference crawler (v0.2).

Purpose
-------
Create a reproducible snapshot of the public Defense OSDK interface reference:
  domain -> interface -> properties -> inheritance -> link constraints.

v0.2 fixes the main completeness flaw in v0.1: the crawler no longer assumes
that the API root/sidebar is a complete catalogue. It starts with root-discovered
interfaces, then follows interface links from root, domain overview pages, and
each interface page until no new interface SDK IDs are discovered (a fixed point).

Raw capture and normalized parsing remain separate so parser mistakes never
destroy source evidence.

Usage
-----
  python tools/crawl_defense_osdk.py --out ./out
  python tools/crawl_defense_osdk.py --out ./out --domains common orderOfBattle

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
from collections import deque
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Iterable, Optional
import xml.etree.ElementTree as ET
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup, Tag

ROOT = "https://www.palantir.com/docs/defense-osdk/api"
UA = "DefenseOSDKReferenceCrawler/0.2 (+ontology research; low-rate public-doc snapshot)"
INTERFACE_RE = re.compile(
    r"^/docs/defense-osdk/api/(?P<domain>[^/]+)/interfaceTypes/(?P<slug>[^/?#]+)/?$"
)
OVERVIEW_RE = re.compile(
    r"^/docs/defense-osdk/api/(?P<domain>[^/]+)/overview(?:/(?P<page>[^/?#]+))?/?$"
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
    discovery_sources: list[dict] = field(default_factory=list)
    discovery_round: Optional[int] = None
    parser_warnings: list[str] = field(default_factory=list)
    parser_status: str = "ok"
    source_sha256: Optional[str] = None


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def clean(s: str) -> str:
    return re.sub(r"\s+", " ", s or "").strip()


def canonical_url(url: str) -> str:
    p = urlparse(url)
    path = re.sub(r"/+", "/", p.path).rstrip("/")
    return f"{p.scheme}://{p.netloc}{path}"


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
            # requests defaults text/html without an explicit charset to ISO-8859-1,
            # which corrupts OSDK symbols such as → and ↗. Palantir docs are UTF-8;
            # prefer UTF-8 when it decodes cleanly and no explicit charset was sent.
            content_type = r.headers.get("Content-Type", "")
            has_charset = "charset=" in content_type.lower()
            if not has_charset:
                try:
                    r.content.decode("utf-8")
                    r.encoding = "utf-8"
                except UnicodeDecodeError:
                    if r.apparent_encoding:
                        r.encoding = r.apparent_encoding
            if delay:
                time.sleep(delay)
            return r
        except requests.RequestException as exc:
            last = exc
            if attempt < retries:
                time.sleep(min(2 ** attempt, 8))
    raise RuntimeError(f"Failed GET {url}: {last}")


def interface_meta_from_url(url: str, name_hint: str = "") -> Optional[dict]:
    p = urlparse(url)
    m = INTERFACE_RE.match(p.path)
    if not m:
        return None
    normalized_url = canonical_url(f"{p.scheme}://{p.netloc}{p.path}")
    slug = m.group("slug")
    return {
        "domain": m.group("domain"),
        "slug": slug,
        "sdk_id": sdk_id_from_slug(slug),
        "name_hint": clean(name_hint),
        "url": normalized_url,
    }


def discover_interfaces(html: str, page_url: str = ROOT) -> list[dict]:
    """Extract every Defense OSDK interface link present in one HTML page.

    This function is intentionally page-agnostic: it works on the API root,
    overview pages, and interface pages. v0.2 repeatedly applies it until the
    discovered SDK-ID set stops growing.
    """
    soup = BeautifulSoup(html, "html.parser")
    found: dict[str, dict] = {}
    for a in soup.find_all("a", href=True):
        href = a.get("href", "")
        absolute = urljoin(page_url.rstrip("/") + "/", href)
        meta = interface_meta_from_url(absolute, a.get_text(" ", strip=True))
        if not meta:
            continue
        # Canonical key is sdk_id, not display name or URL spelling.
        old = found.get(meta["sdk_id"])
        if old is None or (not old.get("name_hint") and meta.get("name_hint")):
            found[meta["sdk_id"]] = meta
    return sorted(found.values(), key=lambda x: (x["domain"], x["sdk_id"]))


def discover_overview_pages(html: str, page_url: str = ROOT) -> list[dict]:
    """Extract Defense OSDK domain overview links used as additional discovery seeds."""
    soup = BeautifulSoup(html, "html.parser")
    found: dict[str, dict] = {}
    for a in soup.find_all("a", href=True):
        absolute = urljoin(page_url.rstrip("/") + "/", a.get("href", ""))
        p = urlparse(absolute)
        m = OVERVIEW_RE.match(p.path)
        if not m:
            continue
        url = canonical_url(f"{p.scheme}://{p.netloc}{p.path}")
        found[url] = {"domain": m.group("domain"), "url": url}
    return sorted(found.values(), key=lambda x: (x["domain"], x["url"]))


def _source_kind(source_url: str, root_url: str) -> str:
    if canonical_url(source_url) == canonical_url(root_url):
        return "root_navigation"
    p = urlparse(source_url)
    if p.path.lower().endswith(".xml"):
        return "sitemap"
    if OVERVIEW_RE.match(p.path):
        return "domain_overview"
    if INTERFACE_RE.match(p.path):
        return "interface_cross_link"
    return "other_doc"


def default_sitemap_url(root_url: str) -> str:
    p = urlparse(root_url)
    return f"{p.scheme}://{p.netloc}/sitemap.xml"


def discover_sitemap_interfaces(
    fetch_text: Callable[[str], str],
    root_url: str = ROOT,
    *,
    max_sitemaps: int = 50,
) -> dict:
    """Discover interface URLs from the site's XML sitemap or sitemap index.

    Sitemap discovery is deliberately independent from the docs sidebar. It is a
    fallback catalogue source for deployment/cache windows where a new interface
    page exists but root/sidebar HTML has not yet been updated everywhere.
    """
    root_host = urlparse(root_url).netloc
    queue: deque[str] = deque([default_sitemap_url(root_url)])
    visited: set[str] = set()
    found: dict[str, dict] = {}
    sources: dict[str, set[str]] = {}
    failures: list[dict] = []

    while queue and len(visited) < max_sitemaps:
        sitemap_url = canonical_url(queue.popleft())
        if sitemap_url in visited:
            continue
        visited.add(sitemap_url)
        try:
            text = fetch_text(sitemap_url)
            root = ET.fromstring(text)
        except Exception as exc:
            failures.append({"url": sitemap_url, "error": repr(exc)})
            continue

        locs = []
        for el in root.iter():
            if el.tag.rsplit("}", 1)[-1].lower() == "loc" and el.text:
                locs.append(clean(el.text))

        for loc in locs:
            p = urlparse(loc)
            if p.netloc and p.netloc != root_host:
                continue
            meta = interface_meta_from_url(loc)
            if meta:
                found[meta["sdk_id"]] = meta
                sources.setdefault(meta["sdk_id"], set()).add(sitemap_url)
                continue
            if p.path.lower().endswith(".xml"):
                queue.append(loc)

    return {
        "interfaces": found,
        "sources": {k: sorted(v) for k, v in sources.items()},
        "sitemap_pages_visited": sorted(visited),
        "failures": failures,
        "limit_hit": bool(queue),
    }


def _register_interface(
    registry: dict[str, dict],
    meta: dict,
    *,
    source_url: str,
    round_no: int,
    root_url: str,
) -> bool:
    """Register discovery provenance. Return True only for a newly seen sdk_id."""
    sdk_id = meta["sdk_id"]
    source = {
        "kind": _source_kind(source_url, root_url),
        "source_url": canonical_url(source_url),
        "round": round_no,
    }
    if sdk_id not in registry:
        registry[sdk_id] = {
            **meta,
            "first_discovery_round": round_no,
            "discovery_sources": [source],
        }
        return True
    cur = registry[sdk_id]
    if meta.get("name_hint") and not cur.get("name_hint"):
        cur["name_hint"] = meta["name_hint"]
    if meta.get("url") and not cur.get("url"):
        cur["url"] = meta["url"]
    if source not in cur["discovery_sources"]:
        cur["discovery_sources"].append(source)
    return False


def discover_fixed_point(
    fetch_html: Callable[[str], str],
    root_url: str = ROOT,
    *,
    allowed_domains: Optional[set[str]] = None,
    max_interface_pages: int = 0,
    include_overviews: bool = True,
    include_sitemap: bool = True,
) -> dict:
    """Discover/fetch interface pages until the SDK-ID set reaches a fixed point.

    `fetch_html` is injected so this algorithm can be tested without network
    access. The live CLI passes a requests-backed fetcher; tests pass an in-memory
    HTML map.
    """
    root_url = canonical_url(root_url)
    registry: dict[str, dict] = {}
    fetched_pages: dict[str, str] = {}
    page_failures: list[dict] = []
    visited_pages: set[str] = set()
    queued_pages: set[str] = set()
    queue: deque[tuple[str, int, str]] = deque()
    discovery_events: list[dict] = []

    def domain_allowed(domain: str) -> bool:
        return allowed_domains is None or domain in allowed_domains

    def enqueue(url: str, round_no: int, kind: str) -> None:
        cu = canonical_url(url)
        if cu in visited_pages or cu in queued_pages:
            return
        queued_pages.add(cu)
        queue.append((cu, round_no, kind))

    # Fetch root as the initial seed document.
    root_html = fetch_html(root_url)
    fetched_pages[root_url] = root_html
    visited_pages.add(root_url)

    root_interfaces = discover_interfaces(root_html, root_url)

    sitemap_result = {
        "interfaces": {}, "sources": {}, "sitemap_pages_visited": [],
        "failures": [], "limit_hit": False,
    }
    if include_sitemap:
        sitemap_result = discover_sitemap_interfaces(fetch_html, root_url)
        for sdk_id, meta in sitemap_result["interfaces"].items():
            if not domain_allowed(meta["domain"]):
                continue
            source_urls = sitemap_result["sources"].get(sdk_id) or [default_sitemap_url(root_url)]
            for source_url in source_urls:
                is_new = _register_interface(
                    registry, meta, source_url=source_url, round_no=0, root_url=root_url
                )
                discovery_events.append({
                    "sdk_id": sdk_id, "source_url": source_url,
                    "kind": "sitemap", "round": 0, "new": is_new,
                })
            enqueue(meta["url"], 1, "interface")

    for meta in root_interfaces:
        if not domain_allowed(meta["domain"]):
            continue
        is_new = _register_interface(
            registry, meta, source_url=root_url, round_no=0, root_url=root_url
        )
        discovery_events.append({
            "sdk_id": meta["sdk_id"], "source_url": root_url,
            "kind": "root_navigation", "round": 0, "new": is_new,
        })
        enqueue(meta["url"], 1, "interface")

    if include_overviews:
        for ov in discover_overview_pages(root_html, root_url):
            if domain_allowed(ov["domain"]):
                enqueue(ov["url"], 1, "overview")

    fetched_interface_ids: set[str] = set()
    limit_hit = False
    max_round_seen = 0

    while queue:
        page_url, round_no, kind = queue.popleft()
        queued_pages.discard(page_url)
        if page_url in visited_pages:
            continue
        if kind == "interface" and max_interface_pages and len(fetched_interface_ids) >= max_interface_pages:
            limit_hit = True
            continue

        visited_pages.add(page_url)
        max_round_seen = max(max_round_seen, round_no)
        try:
            html = fetch_html(page_url)
            fetched_pages[page_url] = html
        except Exception as exc:  # keep discovery evidence even if a page fetch fails
            page_failures.append({"url": page_url, "kind": kind, "round": round_no, "error": repr(exc)})
            continue

        page_meta = interface_meta_from_url(page_url)
        if page_meta and domain_allowed(page_meta["domain"]):
            fetched_interface_ids.add(page_meta["sdk_id"])
            # A direct fetch may be the first proof of this SDK ID if the URL was seeded externally.
            _register_interface(
                registry, page_meta, source_url=page_url, round_no=round_no, root_url=root_url
            )

        # The core v0.2 behavior: every fetched page can expand the interface universe.
        linked = discover_interfaces(html, page_url)
        for meta in linked:
            if not domain_allowed(meta["domain"]):
                continue
            is_new = _register_interface(
                registry, meta, source_url=page_url, round_no=round_no, root_url=root_url
            )
            discovery_events.append({
                "sdk_id": meta["sdk_id"], "source_url": page_url,
                "kind": _source_kind(page_url, root_url), "round": round_no,
                "new": is_new,
            })
            enqueue(meta["url"], round_no + 1, "interface")

        if include_overviews:
            for ov in discover_overview_pages(html, page_url):
                if domain_allowed(ov["domain"]):
                    enqueue(ov["url"], round_no + 1, "overview")

    root_ids = {
        meta["sdk_id"] for meta in root_interfaces
        if domain_allowed(meta["domain"])
    }
    sitemap_ids = {
        sdk_id for sdk_id, meta in sitemap_result["interfaces"].items()
        if domain_allowed(meta["domain"])
    }
    non_root_ids = sorted(set(registry) - root_ids)
    cross_link_only_ids = sorted(set(registry) - root_ids - sitemap_ids)
    sitemap_only_ids = sorted(sitemap_ids - root_ids)
    fixed_point_reached = not queue and not limit_hit

    return {
        "root_url": root_url,
        "root_html": root_html,
        "interfaces": registry,
        "fetched_pages": fetched_pages,
        "page_failures": page_failures,
        "sitemap_failures": sitemap_result["failures"],
        "sitemap_pages_visited": sitemap_result["sitemap_pages_visited"],
        "sitemap_limit_hit": sitemap_result["limit_hit"],
        "discovery_events": discovery_events,
        "root_discovered_sdk_ids": sorted(root_ids),
        "cross_link_only_sdk_ids": cross_link_only_ids,
        "sitemap_only_sdk_ids": sitemap_only_ids,
        "non_root_sdk_ids": non_root_ids,
        "root_discovered_count": len(root_ids),
        "sitemap_discovered_count": len(sitemap_ids),
        "sitemap_only_count": len(sitemap_only_ids),
        "total_unique_sdk_ids": len(registry),
        "cross_link_only_count": len(cross_link_only_ids),
        "non_root_count": len(non_root_ids),
        "fetched_interface_count": len(fetched_interface_ids),
        "discovery_rounds": max_round_seen,
        "fixed_point_reached": fixed_point_reached,
        "limit_hit": limit_hit,
    }


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
        if isinstance(el, Tag) and el.name == "p":
            t = clean(el.get_text(" ", strip=True))
            if t and t != "Palantir Defense OSDK":
                chunks.append(t)
    return clean(" ".join(chunks)) if chunks else None


def section_node(main: Tag, heading: str) -> Optional[Tag]:
    for h in main.find_all("h2"):
        if clean(h.get_text(" ", strip=True)).lower() == heading.lower():
            return h
    return None


def section_text_lines(h2: Optional[Tag]) -> list[str]:
    if not h2:
        return []
    out: list[str] = []
    for el in h2.find_all_next():
        if el is h2:
            continue
        if isinstance(el, Tag) and el.name == "h2":
            break
        if not isinstance(el, Tag):
            continue
        if el.name in {"p", "a", "button", "code", "span", "div", "li"}:
            if any(isinstance(c, Tag) and c.name in {"div", "p", "li"} for c in el.children):
                continue
            t = clean(el.get_text(" ", strip=True))
            if not t or t in {"↗", "·", "Copied!", "TypeScript"}:
                continue
            if not out or out[-1] != t:
                out.append(t)
    return out


def is_description(s: str) -> bool:
    # Most current entries use this prefix. A fallback is intentionally not used
    # here because unlabeled prose can be UI/code noise; unresolved sections are
    # surfaced via warnings instead of silently guessed.
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
        header = [x for x in header if x != "Properties"]
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
        scalar = {"string", "date", "datetime", "timestamp", "boolean", "integer", "long", "double", "float", "decimal"}
        name = typ = None
        scalar_idx = next((i for i, x in enumerate(header) if x.lower() in scalar), None)
        if scalar_idx is not None:
            name = " ".join(header[:scalar_idx]) or None
            typ = header[scalar_idx]
        elif len(header) >= 2:
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
        if x.startswith("Load ") or x == "Code snippets":
            continue
        x = clean(x.replace("↗", ""))
        if x and x not in out:
            out.append(x)
    return out


def parse_link_header(header: list[str]) -> tuple[Optional[str], Optional[str], Optional[str], Optional[bool], list[str]]:
    raw = header[:]
    header = [x for x in header if x not in {"Link constraints", "Incoming link constraints"}]
    req: Optional[bool] = None
    card: Optional[str] = None
    joined = " ".join(header)
    for c in CARDINALITIES:
        if c in joined:
            card = c
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
        sdk_id=meta.get("sdk_id") or sdk_id_from_slug(meta["slug"]),
        url=meta["url"],
        description=description_after_h1(main, h1),
        discovery_sources=list(meta.get("discovery_sources", [])),
        discovery_round=meta.get("first_discovery_round"),
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


def normalize_label(label: Optional[str]) -> Optional[str]:
    """Normalize known display qualifiers for validation only, never for storage."""
    if label is None:
        return None
    x = clean(label)
    x = re.sub(r"^\[DEPRECATED\]\s*", "", x, flags=re.I)
    x = re.sub(r"\s*\(Item\)$", "", x, flags=re.I)
    return x


def validate(interfaces: list[Interface], discovery: Optional[dict] = None) -> dict:
    by_name = {i.name: i for i in interfaces}
    normalized_names = {normalize_label(i.name): i.name for i in interfaces}
    unresolved_extends = []
    unresolved_links = []
    for i in interfaces:
        for parent in i.extends:
            if normalize_label(parent) not in normalized_names:
                unresolved_extends.append({"interface": i.name, "extends": parent, "note": "may be external/base interface"})
        for link in i.outgoing_link_constraints:
            if link.target_interface and normalize_label(link.target_interface) not in normalized_names:
                unresolved_links.append({"interface": i.name, "link": link.name, "target": link.target_interface})
    result = {
        "interface_count": len(interfaces),
        "domain_counts": _domain_counts(interfaces),
        "parser_warning_count": sum(1 for i in interfaces if i.parser_warnings),
        "unresolved_extends": unresolved_extends,
        "unresolved_outgoing_targets": unresolved_links,
    }
    if discovery:
        result["discovery"] = {
            "root_discovered_count": discovery["root_discovered_count"],
            "sitemap_discovered_count": discovery.get("sitemap_discovered_count", 0),
            "sitemap_only_count": discovery.get("sitemap_only_count", 0),
            "cross_link_only_count": discovery["cross_link_only_count"],
            "non_root_count": discovery.get("non_root_count", discovery["cross_link_only_count"]),
            "total_unique_sdk_ids": discovery["total_unique_sdk_ids"],
            "fetched_interface_count": discovery["fetched_interface_count"],
            "discovery_rounds": discovery["discovery_rounds"],
            "fixed_point_reached": discovery["fixed_point_reached"],
            "limit_hit": discovery["limit_hit"],
            "page_failure_count": len(discovery["page_failures"]),
            "sitemap_failure_count": len(discovery.get("sitemap_failures", [])),
        }
    return result


def _domain_counts(interfaces: Iterable[Interface]) -> dict[str, int]:
    d: dict[str, int] = {}
    for i in interfaces:
        d[i.domain] = d.get(i.domain, 0) + 1
    return dict(sorted(d.items()))


def write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def safe_file_component(s: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", s)


def main_cli() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="defense_osdk_snapshot", help="Output directory")
    ap.add_argument("--root", default=ROOT)
    ap.add_argument("--domains", nargs="*", help="Optional domain slugs to include, e.g. common orderOfBattle")
    ap.add_argument("--delay", type=float, default=0.5, help="Delay after each network request (seconds)")
    ap.add_argument("--timeout", type=int, default=30)
    ap.add_argument("--retries", type=int, default=2)
    ap.add_argument("--limit", type=int, default=0, help="Optional maximum interface pages; disables fixed-point completeness if hit")
    ap.add_argument("--no-overviews", action="store_true", help="Do not use domain overview pages as discovery seeds")
    ap.add_argument("--no-sitemap", action="store_true", help="Do not use the site XML sitemap as an independent discovery source")
    args = ap.parse_args()

    out = Path(args.out)
    raw_dir = out / "raw" / "pages"
    raw_dir.mkdir(parents=True, exist_ok=True)

    s = requests.Session()
    s.headers.update({"User-Agent": UA, "Accept": "text/html,application/xhtml+xml"})

    def live_fetch(url: str) -> str:
        return request(s, url, args.timeout, args.retries, args.delay).text

    allowed = set(args.domains) if args.domains else None
    try:
        discovery = discover_fixed_point(
            live_fetch,
            args.root,
            allowed_domains=allowed,
            max_interface_pages=args.limit,
            include_overviews=not args.no_overviews,
            include_sitemap=not args.no_sitemap,
        )
    except Exception as exc:
        print(f"Root/discovery crawl failed: {exc}", file=sys.stderr)
        return 2

    # Save raw root and all successfully fetched interface/overview pages.
    (out / "raw" / "root.html").write_text(discovery["root_html"], encoding="utf-8")
    for url, html in discovery["fetched_pages"].items():
        if canonical_url(url) == canonical_url(args.root):
            continue
        meta = interface_meta_from_url(url)
        if meta:
            filename = f"{meta['domain']}__{meta['slug']}.html"
        else:
            p = urlparse(url)
            filename = "discovery__" + safe_file_component(p.path.strip("/").replace("/", "__")) + ".html"
        (raw_dir / filename).write_text(html, encoding="utf-8")

    registry = discovery["interfaces"]
    parsed: list[Interface] = []
    parse_failures: list[dict] = []
    for sdk_id, meta in sorted(registry.items(), key=lambda kv: (kv[1]["domain"], kv[0])):
        html = discovery["fetched_pages"].get(meta["url"])
        if html is None:
            parse_failures.append({**meta, "error": "interface page was discovered but not fetched"})
            continue
        try:
            parsed.append(parse_interface(html, meta))
        except Exception as exc:
            parse_failures.append({**meta, "error": repr(exc)})

    manifest = {
        "source": "Palantir Defense OSDK public API Reference",
        "root_url": canonical_url(args.root),
        "captured_at_utc": utc_now(),
        "domains_requested": args.domains or "all",
        "discovery": {
            "root_discovered_count": discovery["root_discovered_count"],
            "sitemap_discovered_count": discovery.get("sitemap_discovered_count", 0),
            "sitemap_only_count": discovery.get("sitemap_only_count", 0),
            "cross_link_only_count": discovery["cross_link_only_count"],
            "non_root_count": discovery.get("non_root_count", discovery["cross_link_only_count"]),
            "total_unique_sdk_ids": discovery["total_unique_sdk_ids"],
            "fetched_interface_count": discovery["fetched_interface_count"],
            "discovery_rounds": discovery["discovery_rounds"],
            "fixed_point_reached": discovery["fixed_point_reached"],
            "limit_hit": discovery["limit_hit"],
            "cross_link_only_sdk_ids": discovery["cross_link_only_sdk_ids"],
            "sitemap_only_sdk_ids": discovery.get("sitemap_only_sdk_ids", []),
            "non_root_sdk_ids": discovery.get("non_root_sdk_ids", []),
            "sitemap_pages_visited": discovery.get("sitemap_pages_visited", []),
            "sitemap_failures": discovery.get("sitemap_failures", []),
            "page_failures": discovery["page_failures"],
        },
        "items": [registry[k] for k in sorted(registry)],
    }
    write_json(out / "raw" / "manifest.json", manifest)

    normalized = {
        "snapshot": {
            "source": manifest["source"],
            "root_url": manifest["root_url"],
            "captured_at_utc": manifest["captured_at_utc"],
            "note": "Interfaces are abstract API shapes; they are not instantiable object types/backing datasets.",
            "discovery_fixed_point_reached": discovery["fixed_point_reached"],
        },
        "interfaces": [asdict(i) for i in parsed],
    }
    write_json(out / "normalized" / "defense_osdk.json", normalized)
    write_json(out / "validation" / "crawl_failures.json", discovery["page_failures"] + parse_failures)
    integrity = validate(parsed, discovery)
    write_json(out / "validation" / "integrity_report.json", integrity)

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

    summary = {
        "root_discovered": discovery["root_discovered_count"],
        "sitemap_discovered": discovery.get("sitemap_discovered_count", 0),
        "sitemap_only": discovery.get("sitemap_only_count", 0),
        "cross_link_only": discovery["cross_link_only_count"],
        "non_root_discovered": discovery.get("non_root_count", discovery["cross_link_only_count"]),
        "total_discovered": discovery["total_unique_sdk_ids"],
        "parsed": len(parsed),
        "fetch_failures": len(discovery["page_failures"]),
        "parse_failures": len(parse_failures),
        "warnings": sum(1 for i in parsed if i.parser_warnings),
        "domain_counts": _domain_counts(parsed),
        "discovery_rounds": discovery["discovery_rounds"],
        "fixed_point_reached": discovery["fixed_point_reached"],
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))

    # A non-fixed-point crawl must not be mistaken for a complete snapshot.
    if discovery["page_failures"] or parse_failures or not discovery["fixed_point_reached"]:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main_cli())
