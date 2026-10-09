import os
import subprocess
import unittest

WORKSPACE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def check_git_ignore(path: str) -> bool:
    """Run `git check-ignore -q <path>` from workspace root.
    Returns True if git ignores the path (exit code 0), False otherwise.
    """
    cmd = ["git", "check-ignore", "-q", path]
    res = subprocess.run(cmd, cwd=WORKSPACE_ROOT, capture_output=True)
    return res.returncode == 0


class TestGitignoreRules(unittest.TestCase):
    """Verification suite for .gitignore configuration."""

    def test_happy_path_ignored_directories_and_files(self):
        """Happy Path: ensure generated artifacts, data, external clones, and cache are ignored."""
        ignored_targets = [
            "data/",
            "data/gemini_profile/",
            "data/test_user_data_dir/",
            "browser3/",
            "browser3/launcher.py",
            "output/",
            "output/some_story/",
            "ban_win1/output/",
            "ban_win1/output/scraped_story/",
            "node_modules/",
            "ban_win1/node_modules/",
            "ban_win1/out/",
            "ban_win1/dist/",
            ".license_cache",
            "ban_win1/.license_cache",
            "license_config.json",
            "__pycache__/",
            "app.pyc",
            ".env",
            ".venv/",
            "ban_win1/ext_1562.html",
            "ban_win1/fb_external.html",
        ]
        for target in ignored_targets:
            with self.subTest(target=target):
                self.assertTrue(
                    check_git_ignore(target),
                    f"Target '{target}' should be ignored by git according to .gitignore"
                )

    def test_edge_cases_source_files_not_ignored(self):
        """Edge Cases: ensure critical source code, assets, and configs are NOT ignored."""
        tracked_targets = [
            "app.py",
            "publisher.py",
            "entry_user.py",
            "entry_admin.py",
            "version.json",
            "README.md",
            "CHANGELOG.md",
            "templates/index.html",
            "templates/index_user.html",
            "templates/index_admin.html",
            "static/img/donate_qr.png",
            "tests/test_donate_modal.py",
            "ban_win1/package.json",
            "ban_win1/electron-builder.yml",
            "ban_win1/src/main/index.ts",
            "ban_win1/src/renderer/index.html",
            "ban_win1/build/icon.ico",
            "ban_win1/build/icon.png",
            "ban_win1/build/entitlements.mac.plist",
        ]
        for target in tracked_targets:
            with self.subTest(target=target):
                self.assertFalse(
                    check_git_ignore(target),
                    f"Target '{target}' must NOT be ignored by git"
                )

    def test_error_handling_no_blank_pattern_corruption(self):
        """Error Handling: ensure .gitignore does not have corrupted empty-line patterns."""
        gitignore_path = os.path.join(WORKSPACE_ROOT, ".gitignore")
        self.assertTrue(os.path.exists(gitignore_path), ".gitignore must exist")
        
        with open(gitignore_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        for idx, line in enumerate(lines, 1):
            stripped = line.strip()
            # If line is not a comment or empty, it must have valid content
            if stripped and not stripped.startswith("#"):
                self.assertNotEqual(
                    stripped,
                    "",
                    f"Line {idx} in .gitignore has corrupted empty pattern"
                )
                self.assertFalse(
                    stripped.startswith(" "),
                    f"Line {idx} in .gitignore has accidental leading space"
                )

        # Check random non-ignored dummy paths to ensure git does not treat them as ignored
        dummy_paths = ["custom_script.py", "my_module.js", "docs/guide.md"]
        for dummy in dummy_paths:
            with self.subTest(dummy=dummy):
                self.assertFalse(
                    check_git_ignore(dummy),
                    f"Dummy file '{dummy}' should not be ignored by generic false matches"
                )


if __name__ == "__main__":
    unittest.main()
