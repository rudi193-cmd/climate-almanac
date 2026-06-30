import importlib.util
import json
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent


def test_validate_passes():
    r = subprocess.run([sys.executable, "scripts/validate.py"], cwd=ROOT)
    assert r.returncode == 0


def test_build_index_sorted_and_unique():
    subprocess.run([sys.executable, "scripts/build_index.py"], cwd=ROOT, check=True)
    data = json.loads((ROOT / "catalog.json").read_text())
    assert data["count"] == len(data["entries"])
    ids = [e["id"] for e in data["entries"]]
    assert ids == sorted(ids), "entries must be sorted by id"
    assert len(ids) == len(set(ids)), "ids must be unique"


def test_schema_is_well_formed():
    from jsonschema import Draft202012Validator
    schema = json.loads((ROOT / "schema" / "catalog-entry.schema.json").read_text())
    Draft202012Validator.check_schema(schema)


def _load_checker():
    spec = importlib.util.spec_from_file_location("cl", ROOT / "scripts" / "check_links.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_checker_classifies_bot_blocks():
    mod = _load_checker()
    # Block codes are treated as "unverifiable", never as a dead-link flag.
    assert {401, 403, 406, 429} <= mod.BLOCK_CODES


def test_probe_blocked_without_headless_stays_unverifiable(monkeypatch):
    mod = _load_checker()
    # Both curl rungs blocked; headless off -> blocked code, not a dead flag.
    monkeypatch.setattr(mod, "_curl", lambda url, t, ua: (403, ""))
    code, note = mod._probe("https://bls.gov", 5, headless=False)
    assert code == 403 and "cannot auto-verify" in note


def test_probe_headless_upgrades_block_to_ok(monkeypatch):
    mod = _load_checker()
    monkeypatch.setattr(mod, "_curl", lambda url, t, ua: (403, ""))
    monkeypatch.setattr(mod, "_probe_headless", lambda url, t: (200, ""))
    code, note = mod._probe("https://bls.gov", 5, headless=True)
    assert code == 200 and "headless" in note


def test_probe_headless_failure_never_flags_dead(monkeypatch):
    mod = _load_checker()
    # Headless rung can't run / can't reach -> stay blocked, never report dead.
    monkeypatch.setattr(mod, "_curl", lambda url, t, ua: (403, ""))
    monkeypatch.setattr(mod, "_probe_headless", lambda url, t: (None, "playwright not installed"))
    code, note = mod._probe("https://bls.gov", 5, headless=True)
    assert code == 403  # block code preserved
    assert code in mod.BLOCK_CODES  # classified blocked, not dead, downstream
