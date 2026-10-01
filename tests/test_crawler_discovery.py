import importlib.util
import sys
import unittest
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "tools" / "crawl_defense_osdk.py"
spec = importlib.util.spec_from_file_location("crawler", MODULE_PATH)
crawler = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = crawler
spec.loader.exec_module(crawler)

ROOT = "https://www.palantir.com/docs/defense-osdk/api"
BASE = "https://www.palantir.com"

def interface_url(name):
    return f"{BASE}/docs/defense-osdk/api/orderOfBattle/interfaceTypes/com-palantir-ontology-defense-types-{name}"

def page(name, body="", links=None):
    links = links or []
    anchors = "\n".join(f'<a href="{u}">{label}</a>' for label, u in links)
    return f"""<html><body><main>
    <h1>{name}</h1>
    <p>[Palantir Defense Ontology] {body or name}</p>
    {anchors}
    </main></body></html>"""

class FixedPointDiscoveryTests(unittest.TestCase):
    def setUp(self):
        self.unit = interface_url("unit")
        self.org = interface_url("organization")
        self.mt = interface_url("materielType")
        self.materiel = interface_url("materiel")
        self.equipment = interface_url("equipment")

        # Simulate the exact bug class: root/sidebar does NOT list Materiel/Equipment.
        self.html = {
            ROOT: f"""<html><body>
              <a href="{self.unit}">Unit</a>
              <a href="{self.org}">Organization</a>
              <a href="{self.mt}">Materiel Type</a>
            </body></html>""",
            self.unit: page("Unit", "A unit."),
            self.org: page("Organization", "An organization.", [
                ("Assigned Materiel (Item)", self.materiel),
            ]),
            self.mt: page("Materiel Type", "A materiel type.", [
                ("Materiel (Item)", self.materiel),
                ("Equipment (Item)", self.equipment),
            ]),
            self.materiel: page("Materiel", "An individual item of materiel.", [
                ("Materiel Type", self.mt),
                ("Assigned Organization", self.org),
            ]),
            self.equipment: page("Equipment", "Equipment as a specialization of materiel type.", [
                ("Materiel Type", self.mt),
            ]),
        }

    def fetch(self, url):
        url = crawler.canonical_url(url)
        if url not in self.html:
            raise KeyError(url)
        return self.html[url]

    def test_root_only_would_miss_two(self):
        seeds = crawler.discover_interfaces(self.html[ROOT], ROOT)
        ids = {x["sdk_id"] for x in seeds}
        self.assertEqual(len(ids), 3)
        self.assertNotIn("com.palantir.ontology.defense-types.materiel", ids)
        self.assertNotIn("com.palantir.ontology.defense-types.equipment", ids)

    def test_fixed_point_discovers_cross_link_only_interfaces(self):
        result = crawler.discover_fixed_point(self.fetch, ROOT, include_overviews=False)
        self.assertTrue(result["fixed_point_reached"])
        self.assertEqual(result["root_discovered_count"], 3)
        self.assertEqual(result["cross_link_only_count"], 2)
        self.assertEqual(result["total_unique_sdk_ids"], 5)
        self.assertIn("com.palantir.ontology.defense-types.materiel", result["cross_link_only_sdk_ids"])
        self.assertIn("com.palantir.ontology.defense-types.equipment", result["cross_link_only_sdk_ids"])
        self.assertEqual(result["fetched_interface_count"], 5)

    def test_discovery_provenance_records_cross_links(self):
        result = crawler.discover_fixed_point(self.fetch, ROOT, include_overviews=False)
        materiel = result["interfaces"]["com.palantir.ontology.defense-types.materiel"]
        kinds = {x["kind"] for x in materiel["discovery_sources"]}
        sources = {x["source_url"] for x in materiel["discovery_sources"]}
        self.assertIn("interface_cross_link", kinds)
        self.assertIn(crawler.canonical_url(self.org), sources)
        self.assertIn(crawler.canonical_url(self.mt), sources)

    def test_domain_filter_still_allows_fixed_point_inside_domain(self):
        result = crawler.discover_fixed_point(
            self.fetch, ROOT, allowed_domains={"orderOfBattle"}, include_overviews=False
        )
        self.assertTrue(result["fixed_point_reached"])
        self.assertEqual(result["total_unique_sdk_ids"], 5)

    def test_limit_marks_snapshot_incomplete(self):
        result = crawler.discover_fixed_point(
            self.fetch, ROOT, include_overviews=False, max_interface_pages=2
        )
        self.assertFalse(result["fixed_point_reached"])
        self.assertTrue(result["limit_hit"])

class ParserSmokeTests(unittest.TestCase):
    def test_equipment_extends_section(self):
        url = interface_url("equipment")
        html = """<html><body><main>
        <h1>Equipment</h1>
        <p>[Palantir Defense Ontology] Equipment as a specialization of materiel type.</p>
        <h2>Extended interfaces</h2>
        <a href="%s">Materiel Type ↗</a>
        <h2>OSDK Examples</h2>
        </main></body></html>""" % interface_url("materielType")
        meta = crawler.interface_meta_from_url(url, "Equipment")
        iface = crawler.parse_interface(html, meta)
        self.assertEqual(iface.extends, ["Materiel Type"])

    def test_materiel_link_parser(self):
        url = interface_url("materiel")
        html = """<html><body><main>
        <h1>Materiel</h1>
        <p>[Palantir Defense Ontology] An individual item of materiel.</p>
        <h2>Properties</h2>
        <span>Serial Number</span><span>string</span><span>optional</span>
        <p>[Palantir Defense Ontology] The serial number of the materiel item.</p>
        <h2>Link constraints</h2>
        <span>Materiel Type→ Materiel Type ↗·</span><span>One To One</span><span>optional</span>
        <p>[Palantir Defense Ontology] Links a materiel item to its materiel type.</p>
        <span>Assigned Organization→ Organization ↗·</span><span>One To One</span><span>optional</span>
        <p>[Palantir Defense Ontology] Links a materiel item to its assigned organization.</p>
        <h2>OSDK Examples</h2>
        </main></body></html>"""
        meta = crawler.interface_meta_from_url(url, "Materiel")
        iface = crawler.parse_interface(html, meta)
        self.assertEqual(len(iface.declared_properties), 1)
        self.assertEqual(iface.declared_properties[0].name, "Serial Number")
        self.assertEqual(len(iface.outgoing_link_constraints), 2)
        self.assertEqual(iface.outgoing_link_constraints[0].target_interface, "Materiel Type")
        self.assertEqual(iface.outgoing_link_constraints[1].target_interface, "Organization")


class SitemapDiscoveryTests(unittest.TestCase):
    def test_sitemap_can_seed_interface_absent_from_root_and_crosslinks(self):
        root = ROOT
        hidden = interface_url("hiddenNewInterface")
        sitemap = "https://www.palantir.com/sitemap.xml"
        html_map = {
            root: "<html><body></body></html>",
            sitemap: f"<?xml version='1.0'?><urlset><url><loc>{hidden}</loc></url></urlset>",
            hidden: page("Hidden New Interface", "A newly deployed interface."),
        }
        def fetch(url):
            url = crawler.canonical_url(url)
            if url not in html_map:
                raise KeyError(url)
            return html_map[url]
        result = crawler.discover_fixed_point(fetch, root, include_overviews=False, include_sitemap=True)
        self.assertTrue(result["fixed_point_reached"])
        self.assertEqual(result["root_discovered_count"], 0)
        self.assertEqual(result["sitemap_only_count"], 1)
        self.assertEqual(result["total_unique_sdk_ids"], 1)
        self.assertIn("com.palantir.ontology.defense-types.hiddenNewInterface", result["sitemap_only_sdk_ids"])
    def test_nested_heading_boundary_does_not_leak_into_extends(self):
        url = interface_url("equipment")
        html = """<html><body><main>
        <h1>Equipment</h1>
        <p>[Palantir Defense Ontology] Equipment as a specialization of materiel type.</p>
        <h2><a><span>Extended interfaces</span></a></h2>
        <div><a href="%s"><span>Materiel Type ↗</span></a></div>
        <h2><a><span>OSDK Examples</span></a></h2>
        <div><a><span>Load Equipment metadata</span></a></div>
        </main></body></html>""" % interface_url("materielType")
        meta = crawler.interface_meta_from_url(url, "Equipment")
        iface = crawler.parse_interface(html, meta)
        self.assertEqual(iface.extends, ["Materiel Type"])

    def test_live_dom_duplicate_target_cleanup(self):
        header = [
            "Materiel Type→ Materiel Type Materiel Type optional optional",
            "One To One optional",
        ]
        name, target, card, required, _ = crawler.parse_link_header(header)
        self.assertEqual(name, "Materiel Type")
        self.assertEqual(target, "Materiel Type")
        self.assertEqual(card, "One To One")
        self.assertFalse(required)

    def test_live_dom_concatenated_optional_cleanup(self):
        header = [
            "Munition Effectiveness Assessments→ Munition Effectiveness Assessment "
            "Munition Effectiveness Assessment optionaloptional",
            "One To Many optional",
        ]
        name, target, card, required, _ = crawler.parse_link_header(header)
        self.assertEqual(name, "Munition Effectiveness Assessments")
        self.assertEqual(target, "Munition Effectiveness Assessment")
        self.assertEqual(card, "One To Many")
        self.assertFalse(required)

    def test_deprecated_target_label_is_preserved(self):
        header = [
            "Change Assessments→ [DEPRECATED] Change Assessment "
            "[DEPRECATED] Change Assessment optional optional",
            "One To Many optional",
        ]
        name, target, card, required, _ = crawler.parse_link_header(header)
        self.assertEqual(name, "Change Assessments")
        self.assertEqual(target, "[DEPRECATED] Change Assessment")
        self.assertEqual(card, "One To Many")
        self.assertFalse(required)

    def test_engagement_target_effect_solution_cleanup(self):
        header = [
            "Target Effect Solution→ Target Effect Solution "
            "Target Effect Solution optional optional",
            "One To One optional",
        ]
        name, target, card, required, _ = crawler.parse_link_header(header)
        self.assertEqual(name, "Target Effect Solution")
        self.assertEqual(target, "Target Effect Solution")
        self.assertEqual(card, "One To One")
        self.assertFalse(required)


if __name__ == "__main__":
    unittest.main()
