from pathlib import Path
from main import parse_package_json, parse_requirements_txt, _strip_version_prefix

def test_strip_version_prefix():
    assert _strip_version_prefix("^4.17.11") == "4.17.11"
    assert _strip_version_prefix("~1.2.3") == "1.2.3"
    assert _strip_version_prefix(">=2.0.0") == "2.0.0"

def test_parse_package_json(tmp_path):
    pkg = tmp_path / "package.json"
    pkg.write_text('{"dependencies": {"lodash": "^4.17.11"}, "devDependencies": {"jest": "~29.0.0"}}', encoding='utf8')
    deps = parse_package_json(pkg)
    assert deps == {"lodash": "4.17.11", "jest": "29.0.0"}

def test_parse_package_json_missing_file(tmp_path):
    assert parse_package_json(tmp_path / "nope.json") is None

def test_parse_package_json_malformed(tmp_path):
    pkg = tmp_path / "package.json"
    pkg.write_text("{not valid json", encoding='utf8')
    assert parse_package_json(pkg) is None  # should degrade, not crash

def test_parse_requirements_txt(tmp_path):
    req = tmp_path / "requirements.txt"
    req.write_text("flask==2.0.1\n# a comment\nrequests>=2.28.0\n\nunpinned_package\n", encoding='utf8')
    deps = parse_requirements_txt(req)
    assert deps == {"flask": "2.0.1", "requests": "2.28.0", "unpinned_package": "unknown"}
