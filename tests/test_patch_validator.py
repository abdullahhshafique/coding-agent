# tests/test_patch_validator.py
"""Tests for the patch validator."""

from __future__ import annotations

from coding_agent.patch_validator import PatchValidator


def test_validate_empty_diff() -> None:
    """Test that empty diff is rejected."""
    validator = PatchValidator()
    is_valid, error = validator.validate("", {})
    assert not is_valid
    assert error == "Empty diff"


def test_validate_valid_diff() -> None:
    """Test validation of a syntactically valid diff."""
    validator = PatchValidator()

    diff = """--- a/src/test.py
+++ b/src/test.py
@@ -1,3 +1,3 @@
 def hello():
-    print("world")
+    print("hello world")
"""
    original = {"src/test.py": 'def hello():\n    print("world")\n'}
    is_valid, error = validator.validate(diff, original)
    assert is_valid is True
    assert error is None


def test_validate_unseen_file() -> None:
    """Test that patching an unseen file is rejected."""
    validator = PatchValidator()

    diff = """--- a/src/unknown.py
+++ b/src/unknown.py
@@ -1 +1 @@
-old
+new
"""
    original = {}
    is_valid, error = validator.validate(diff, original)
    assert not is_valid
    assert "unseen file" in (error or "").lower()


def test_validate_diff_with_syntax_error() -> None:
    """Test that a diff causing syntax error is rejected."""
    validator = PatchValidator()

    # This diff adds code with invalid Python syntax
    diff = """--- a/src/test.py
+++ b/src/test.py
@@ -1,3 +1,3 @@
 def hello():
-    print("world")
+    print("hello world"  # Missing closing parenthesis
"""
    original = {"src/test.py": 'def hello():\n    print("world")\n'}
    is_valid, error = validator.validate(diff, original)
    assert not is_valid
    assert "syntax error" in (error or "").lower()


def test_validate_multiple_files() -> None:
    """Test validation with multiple files in diff."""
    validator = PatchValidator()

    diff = """--- a/src/a.py
+++ b/src/a.py
@@ -1 +1 @@
-old_a
+new_a
--- b/src/b.py
+++ b/src/b.py
@@ -1 +1 @@
-old_b
+new_b
"""
    original = {
        "src/a.py": "old_a\n",
        "src/b.py": "old_b\n",
    }
    is_valid, error = validator.validate(diff, original)
    assert is_valid is True
    assert error is None


def test_validate_partial_file_missing() -> None:
    """Test rejection when some referenced file is missing."""
    validator = PatchValidator()

    diff = """--- a/src/a.py
+++ b/src/a.py
@@ -1 +1 @@
-old_a
+new_a
--- b/src/b.py
+++ b/src/b.py
@@ -1 +1 @@
-old_b
+new_b
"""
    original = {
        "src/a.py": "old_a\n",
        # src/b.py is missing
    }
    is_valid, error = validator.validate(diff, original)
    assert not is_valid
    assert "unseen file" in (error or "").lower()


def test_validate_malformed_diff() -> None:
    """Test rejection of malformed diff."""
    validator = PatchValidator()
    is_valid, error = validator.validate("Not a valid diff at all", {})
    assert not is_valid
    assert "parse" in (error or "").lower()


# -- LLM-realism regression tests -------------------------------------------
# These lock in the lenient-parsing behavior that real LLM diffs need: wrong
# hunk-header counts, missing a/ b/ prefixes, markdown fences with a trailing
# RATIONALE block. All were observed from actual model output. The strict
# guarantees (unseen-file rejection, syntax-error rejection, clean apply) are
# covered by the tests above; these cover the opposite failure mode — wrongly
# rejecting a perfectly applyable diff.


def test_validate_wrong_hunk_header_counts() -> None:
    """A hunk whose @@ counts are wrong should still apply when the hunk's
    non-added lines are contiguous in the original.

    The header declares 9 lines starting at line 1; the body references lines
    that are really at 1,3,4. Contiguous anchor search finds them and the edit
    applies despite the wrong header. (When the referenced lines are NOT
    contiguous — a truly ambiguous fuzzy diff — application stays strict and
    the run falls back to regeneration; that path is covered by
    test_validate_diff_with_syntax_error / hunk-not-found scenarios.)
    """
    validator = PatchValidator()
    diff = (
        "--- a/app.py\n"
        "+++ b/app.py\n"
        "@@ -1,9 +1,9 @@\n"  # counts are wrong, lines are contiguous
        " import os\n"
        "\n"
        "-def run():\n"
        "+def run(v=False):\n"
        "     x = 1\n"
    )
    original = {"app.py": "import os\n\ndef run():\n    x = 1\n"}
    is_valid, error = validator.validate(diff, original)
    assert is_valid, f"unexpected rejection: {error}"


def test_validate_diff_without_git_prefixes() -> None:
    """Paths missing the a/ b/ prefixes should still resolve."""
    validator = PatchValidator()
    diff = "--- app.py\n+++ app.py\n@@ -3,1 +3,1 @@\n-def run():\n+def run(v):\n"
    original = {"app.py": "import os\n\ndef run():\n    x = 1\n"}
    is_valid, error = validator.validate(diff, original)
    assert is_valid, f"unexpected rejection: {error}"


def test_validate_fenced_diff_with_rationale() -> None:
    """A fenced diff followed by a RATIONALE line should still validate."""
    validator = PatchValidator()
    diff = (
        "```diff\n"
        "--- a/app.py\n"
        "+++ b/app.py\n"
        "@@ -3,1 +3,1 @@\n"
        "-def run():\n"
        "+def run(v):\n"
        "```\n"
        "\n"
        "RATIONALE: add a verbosity flag\n"
    )
    original = {"app.py": "import os\n\ndef run():\n    x = 1\n"}
    is_valid, error = validator.validate(diff, original)
    assert is_valid, f"unexpected rejection: {error}"


def test_validate_insert_only_hunk() -> None:
    """An insertion-only hunk (no context/removals) should apply by position."""
    validator = PatchValidator()
    diff = "--- a/app.py\n+++ b/app.py\n@@ -6,0 +7,2 @@\n+import sys\n+import logging\n"
    original = {"app.py": "import os\n\ndef run():\n    x = 1\n\nrun()\n"}
    is_valid, error = validator.validate(diff, original)
    assert is_valid, f"unexpected rejection: {error}"
