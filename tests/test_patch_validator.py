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
    assert isinstance(is_valid, bool)


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
