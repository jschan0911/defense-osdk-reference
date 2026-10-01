PYTHON ?= python3
SNAPSHOT ?= data/snapshots/2026-10-01
REFERENCE ?= $(SNAPSHOT)/normalized/defense_osdk_reference.json

.PHONY: setup validate crawl crawl-oob

setup:
	$(PYTHON) -m pip install -r requirements.txt

validate:
	$(PYTHON) tools/validate_reference.py $(REFERENCE)

crawl:
	$(PYTHON) tools/crawl_defense_osdk.py --out out/full

crawl-oob:
	$(PYTHON) tools/crawl_defense_osdk.py --out out/oob --domains common orderOfBattle
