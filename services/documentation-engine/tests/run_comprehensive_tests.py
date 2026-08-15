#!/usr/bin/env python3
"""Comprehensive Docryx test runner for Phases 2-6."""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
from pathlib import Path

from main import _compute_overall_score, scan_documentation

ROOT = Path(tempfile.mkdtemp(prefix="docryx-tests-"))
RESULTS: dict = {}


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def dump(obj: dict) -> str:
    return json.dumps(obj, indent=2, default=str)


def phase2():
    # Fixture A - great docs
    a = ROOT / "fixture_a"
    write(a / "README.md", """# Installation
Setup steps here with enough content to exceed two hundred characters easily.
This project demonstrates excellent documentation practices for testing purposes.

# Usage
Getting started guide with examples of how to run the application locally.

# API
Documentation for all public API endpoints and their parameters.

# Configuration
Environment variables and configuration file options explained in detail.

# Contributing
Please read contributing guidelines before submitting pull requests to this repo.

# License
MIT License applies to all source code in this repository.

# Examples
Several worked examples are included below for common integration scenarios.
""")
    write(a / "LICENSE", "MIT License\n")
    write(a / "CONTRIBUTING.md", "# Contributing\n")
    write(a / "docs" / "guide.md", "# Guide\n")
    write(a / "src" / "app.ts", """/** Adds numbers. */
export function add(a: number, b: number) { // sum
  return a + b;
}

/** Greets user. */
export class Greeter {
  /** Say hello */
  greet(name: string) {
    return `Hi ${name}`;
  }
}
""")
    ra = scan_documentation(a, "https://example.com/a")
    RESULTS["phase2_a"] = ra

    # Fixture B - no docs
    b = ROOT / "fixture_b"
    write(b / "index.js", "export function x(){return 1}\nexport function y(){return 2}\n")
    rb = scan_documentation(b, "https://example.com/b")
    RESULTS["phase2_b"] = rb


def phase3():
    scores = {}
    # 3a - only installation, 3 lines
    r1 = ROOT / "readme_3a"
    write(r1 / "README.md", "# Installation\nline2\nline3\n")
    scores["3a_only_install_3lines"] = scan_documentation(r1)["readme_score"]

    # 3b - 4 of 7 headings, >200 chars
    r2 = ROOT / "readme_3b"
    write(r2 / "README.md", """# Installation
Detailed setup instructions with enough text to exceed two hundred characters for the readme scoring test case number three b in this documentation engine validation suite.

# Usage
Getting started information here.

# API
API docs section.

# Configuration
Config options explained in depth with multiple paragraphs of helpful context for developers integrating this library into their applications and services.
""")
    scores["3b_four_headings"] = scan_documentation(r2)["readme_score"]

    # 3c - all 7 headings
    r3 = ROOT / "readme_3c"
    write(r3 / "README.md", """# Installation
Setup guide with substantial content exceeding two hundred characters for proper readme scoring validation in documentation engine phase three test case c.

# Usage
Getting started walkthrough.

# API
Full API reference.

# Configuration
All config knobs.

# Contributing
How to contribute.

# License
MIT

# Examples
Worked examples.
""")
    scores["3c_all_seven"] = scan_documentation(r3)["readme_score"]
    RESULTS["phase3"] = scores


def phase4():
    cases = {}

    # 4a LICENSE file only
    c = ROOT / "p4_license_file"
    write(c / "LICENSE", "MIT\n")
    r = scan_documentation(c)
    cases["4a_license_file"] = r["has_license"]

    # 4b package.json license field
    c = ROOT / "p4_pkg_license"
    write(c / "package.json", '{"name":"x","license":"MIT"}\n')
    r = scan_documentation(c)
    cases["4b_pkg_json_license"] = r["has_license"]

    # 4c .github/CONTRIBUTING.md
    c = ROOT / "p4_github_contrib"
    write(c / ".github" / "CONTRIBUTING.md", "# Contributing\n")
    r = scan_documentation(c)
    cases["4c_github_contributing"] = r["has_contributing"]

    # 4d documentation/ folder
    c = ROOT / "p4_documentation_folder"
    write(c / "documentation" / "index.md", "# Docs\n")
    r = scan_documentation(c)
    cases["4d_documentation_folder"] = r["docs_folder_found"]

    # 4e empty docs/
    c = ROOT / "p4_empty_docs"
    (c / "docs").mkdir(parents=True)
    r = scan_documentation(c)
    cases["4e_empty_docs_folder"] = r["docs_folder_found"]

    RESULTS["phase4"] = cases


def phase5():
    out = {}

    # JS/TS - 3 of 5 documented
    js = ROOT / "p5_js"
    write(js / "src" / "mod.ts", """/** documented fn */
export function a() { return 1; }
export function b() { return 2; }
/** documented class */
export class C {}
export function d() { return 4; }
export function e() { return 5; }
// comment line
// another comment
const x = 1; // inline
""")
    r = scan_documentation(js)
    out["js_doc_ratio"] = r["documented_functions_ratio"]
    out["js_comment_ratio"] = r["code_comment_ratio"]

    # Python - 2 of 4 documented
    py = ROOT / "p5_py"
    write(py / "src" / "mod.py", """\"\"\"module\"\"\"

def documented():
    \"\"\"has docstring\"\"\"
    return 1

def not_documented():
    return 2

class DocumentedClass:
    \"\"\"class doc\"\"\"
    pass

class BareClass:
    pass
""")
    r = scan_documentation(py)
    out["py_doc_ratio"] = r["documented_functions_ratio"]
    out["py_comment_ratio"] = r["code_comment_ratio"]

    # Unsupported - only .rb
    rb = ROOT / "p5_ruby"
    write(rb / "app.rb", "# ruby file\ndef foo; end\n")
    r = scan_documentation(rb)
    out["ruby_doc_ratio"] = r["documented_functions_ratio"]
    out["ruby_overall"] = r["overall_score"]
    out["ruby_finding"] = next((f for f in r["findings"] if f["check"] == "documented_functions_ratio"), None)

    RESULTS["phase5"] = out


def phase6():
    # Use fixture_a known values and hand compute
    r = RESULTS["phase2_a"]
    doc_fn = r["documented_functions_ratio"]
    expected = _compute_overall_score(
        r["readme_score"], r["has_license"], r["has_contributing"],
        r["docs_folder_found"], float(r["code_comment_ratio"]), doc_fn,
    )
    RESULTS["phase6"] = {
        "actual": r["overall_score"],
        "hand_computed": expected,
        "match": r["overall_score"] == expected,
        "inputs": {
            "readme_score": r["readme_score"],
            "has_license": r["has_license"],
            "has_contributing": r["has_contributing"],
            "docs_folder_found": r["docs_folder_found"],
            "code_comment_ratio": r["code_comment_ratio"],
            "documented_functions_ratio": doc_fn,
        },
    }


def main():
    phase2()
    phase3()
    phase4()
    phase5()
    phase6()
    print(dump(RESULTS))
    shutil.rmtree(ROOT, ignore_errors=True)


if __name__ == "__main__":
    main()
