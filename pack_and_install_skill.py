#!/usr/bin/env python3
"""
Auto-package and install skill to WorkBuddy
Usage: python pack_and_install_skill.py <skill_directory> [--zip-only] [--backup] [--backup-only] [--update-local] [--diff]
"""

import os
import sys
import shutil
import time
import zipfile
import hashlib
import re
import stat
from collections.abc import Callable
from pathlib import Path

# Type aliases
PathLike = str | Path



class GitignoreMatcher:
    """
    Parse ``.gitignore`` files (walking up from *skill_dir* to the repository
    root) and test whether a relative path is ignored.

    Uses only stdlib ``re`` – no external dependency on ``pathspec``.
    """

    def __init__(self, skill_dir: Path) -> None:
        # (compiled_regex, is_dir_only, is_negation)
        self._anchored: list[tuple[re.Pattern[str], bool, bool]] = []
        self._unanchored: list[tuple[re.Pattern[str], bool, bool]] = []
        self._load(skill_dir)

    # ------------------------------------------------------------------
    # Loading
    # ------------------------------------------------------------------
    def _load(self, skill_dir: Path) -> None:
        """Walk up from *skill_dir* to the repo root, collecting
        ``.gitignore`` files.  Parent-directory rules are processed first
        so that closer (child) rules correctly override them."""
        dirs: list[Path] = []
        cur = skill_dir.resolve()
        while True:
            dirs.append(cur)
            if (cur / ".git").is_dir() or cur.parent == cur:
                break
            cur = cur.parent
        # The deepest directory should have the *last* say
        dirs.reverse()

        seen: set[Path] = set()
        for d in dirs:
            gi = d / ".gitignore"
            if gi.exists() and gi.resolve() not in seen:
                seen.add(gi.resolve())
                self._parse(gi)

    def _parse(self, path: Path) -> None:
        with path.open("r", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                raw = line.rstrip("\n\r")
                # Strip trailing whitespace (simplified – not handling
                # escaped trailing space, which is rare)
                raw = raw.rstrip()
                if not raw or raw.startswith("#"):
                    continue

                is_negation = raw.startswith("!")
                if is_negation:
                    pat_str = raw[1:]
                else:
                    pat_str = raw

                is_dir_only = pat_str.endswith("/")
                pat_str = pat_str.rstrip("/")
                if not pat_str:
                    continue

                regex, anchored = self._pattern_to_regex(pat_str)
                rule = (regex, is_dir_only, is_negation)
                if anchored:
                    self._anchored.append(rule)
                else:
                    self._unanchored.append(rule)

    # ------------------------------------------------------------------
    # Pattern → compiled regex
    # ------------------------------------------------------------------
    @staticmethod
    def _pattern_to_regex(pattern: str) -> tuple[re.Pattern[str], bool]:
        """
        Convert a gitignore glob pattern to a compiled regex.

        Returns ``(compiled_regex, is_anchored)``.
        """
        # A leading ``/`` anchors the pattern to the repo root
        if pattern.startswith("/"):
            pattern = pattern[1:]
            anchored = True
        else:
            anchored = "/" in pattern

        parts: list[str] = []
        i = 0
        while i < len(pattern):
            ch = pattern[i]
            if ch == "*":
                if i + 1 < len(pattern) and pattern[i + 1] == "*":
                    # ``**`` matches everything, including path separators
                    parts.append(".*")
                    i += 2
                    # Optionally absorb a following ``/``
                    if i < len(pattern) and pattern[i] == "/":
                        i += 1
                else:
                    # ``*`` matches everything except ``/``
                    parts.append("[^/]*")
                    i += 1
            elif ch == "?":
                parts.append("[^/]")
                i += 1
            elif ch in ".+^${}()|\\":
                parts.append("\\" + ch)
                i += 1
            else:
                parts.append(ch)
                i += 1

        regex_str = "".join(parts)
        return re.compile("^" + regex_str + "$"), anchored

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def is_ignored(self, rel_path: str, is_dir: bool = False) -> bool:
        """
        Return ``True`` if *rel_path* (a POSIX-style path relative to the
        skill directory) is matched by any ``.gitignore`` rule.
        """
        _rel = Path(rel_path)
        basename = _rel.name
        ignored = False

        # Anchored rules match against the full relative path
        for regex, dir_only, negation in self._anchored:
            if dir_only and not is_dir:
                continue
            if regex.fullmatch(rel_path):
                ignored = not negation

        # Unanchored rules match against the basename at any nesting level
        for regex, dir_only, negation in self._unanchored:
            if dir_only and not is_dir:
                continue
            if regex.fullmatch(basename):
                ignored = not negation

        return ignored

    def is_dir_ignored(self, rel_path: str) -> bool:
        """Convenience: call :meth:`is_ignored` with ``is_dir=True``."""
        return self.is_ignored(rel_path, is_dir=True)


def should_exclude(path: Path,
                  skill_dir: Path,
                  gitignore_matcher: GitignoreMatcher) -> bool:
    """
    Check if a file or directory should be excluded based on ``.gitignore`` rules.

    Args:
        path: File or directory path
        skill_dir: Skill directory path
        gitignore_matcher: GitignoreMatcher for .gitignore-based exclusion

    Returns:
        True if should be excluded, False otherwise
    """
    rel_path = path.relative_to(skill_dir)
    rel_path_str = rel_path.as_posix()
    return gitignore_matcher.is_ignored(rel_path_str, is_dir=path.is_dir())

def remove_path(path: PathLike, max_retries: int = 10, delay: float = 1.0) -> None:
    """
    Remove a file or directory, with retry logic to handle OneDrive locks.

    OneDrive holds file locks during sync, causing PermissionError on removal.
    This function makes all files writable first, then retries on failure.

    Args:
        path: File or directory path to remove
        max_retries: Maximum number of retry attempts (default 10)
        delay: Delay in seconds between retries (default 1.0)
    """
    path = Path(path)
    if not path.exists():
        return

    # Make all files writable to avoid permission issues
    if path.is_dir():
        for root, dirs, files in os.walk(path):
            for name in dirs + files:
                fp = Path(root) / name
                try:
                    fp.chmod(fp.stat().st_mode | stat.S_IWRITE)
                except OSError:
                    pass

    # Remove with retry
    for attempt in range(1, max_retries + 1):
        try:
            if path.is_dir():
                shutil.rmtree(path, onexc=_handle_remove_readonly)
            else:
                path.unlink()
            return
        except (OSError, PermissionError) as e:
            if attempt < max_retries:
                print(f"   ⏳ Removal locked (attempt {attempt}/{max_retries}), retrying in {delay}s…")
                time.sleep(delay)
            else:
                raise OSError(
                    f"Failed to remove {path} after {max_retries} attempts. "
                    + f"OneDrive may still be syncing. Try closing OneDrive or waiting. "
                    + f"Last error: {e}"
                ) from e


def _handle_remove_readonly(func: Callable[[str], object], path: str, exc: BaseException) -> None:
    """
    Callback for ``shutil.rmtree(onexc=...)`` — makes a read-only file writable
    and retries the failed operation.
    """
    path_obj = Path(path)
    try:
        path_obj.chmod(path_obj.stat().st_mode | stat.S_IWRITE)
        _ = func(path)
    except Exception:
        raise exc


def get_workbuddy_skills_path() -> Path:
    """Get WorkBuddy skills installation path"""
    username = os.getenv('USERNAME')
    if not username:
        raise EnvironmentError("Unable to get username, please set USERNAME environment variable")
    
    # WorkBuddy skills path
    skills_path = Path(f"C:/Users/{username}/.workbuddy/skills/")
    return skills_path

def package_skill(skill_dir: PathLike, output_zip: PathLike | None = None) -> Path:
    """
    Package skill directory into a zip file
    
    Args:
        skill_dir: Skill directory path
        output_zip: Output zip file path (optional, defaults to skill_name.zip in the same directory as skill directory)
    
    Returns:
        Generated zip file path
    """
    skill_dir = Path(skill_dir).resolve()
    
    if not skill_dir.exists():
        raise FileNotFoundError(f"Skill directory does not exist: {skill_dir}")
    
    if not skill_dir.is_dir():
        raise NotADirectoryError(f"Not a directory: {skill_dir}")
    
    # Get skill name (directory name)
    skill_name = skill_dir.name
    
    # Determine output zip path
    if output_zip is None:
        output_zip = skill_dir.parent / f"{skill_name}.zip"
    else:
        output_zip = Path(output_zip).resolve()
    
    # Remove existing zip file if it exists
    if output_zip.exists():
        print(f"🗑️  Removing existing package: {output_zip}")
        remove_path(output_zip)
    
    # Create zip file
    print(f"📦 Packaging skill: {skill_name}")
    print(f"   Source directory: {skill_dir}")
    print(f"   Output file: {output_zip}")
    
    excluded_count = 0
    
    # Load .gitignore rules for automatic exclusion
    gitignore_matcher = GitignoreMatcher(skill_dir)
    
    with zipfile.ZipFile(output_zip, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(skill_dir, topdown=True):
            # Compute relative path of the current root for gitignore checks
            root_rel = Path(root).relative_to(skill_dir)
            
            # Modify dirs list in-place to skip excluded directories
            # (gitignore rules, plus a hard-coded exclusion of a top-level
            #  "tests" directory — see collect_included_files for the same guard)
            dirs[:] = [
                d
                for d in dirs
                if not gitignore_matcher.is_dir_ignored(
                    (root_rel / d).as_posix() if str(root_rel) != "." else d
                )
                and not (str(root_rel) == "." and d == "tests")
            ]
            
            for file in files:
                file_path = Path(root) / file
                
                # Check if should be excluded
                if should_exclude(file_path, skill_dir, gitignore_matcher):
                    excluded_count += 1
                    continue
                
                # Calculate relative path (path in zip)
                arcname = file_path.relative_to(skill_dir.parent)
                zipf.write(file_path, arcname)
                print(f"   ✓ {arcname}")
    
    print(f"✅ Packaging complete: {output_zip}")
    if excluded_count > 0:
        print(f"   Excluded {excluded_count} files/directories")
    
    return output_zip

def install_skill(zip_path: PathLike,
                  workbuddy_skills_path: PathLike | None = None, 
                  backup: bool = False) -> Path:
    """
    Install skill to WorkBuddy by unzipping the package
    
    Args:
        zip_path: Path to the zip package (required)
        workbuddy_skills_path: WorkBuddy skills path (optional, auto-detect)
        backup: Whether to backup existing skill (default False)
    
    Returns:
        Installation target path
    """
    zip_path = Path(zip_path).resolve()
    
    if not zip_path.exists():
        raise FileNotFoundError(f"Zip package does not exist: {zip_path}")
    
    # Get skill name from zip file name
    skill_name = zip_path.stem
    
    # Get WorkBuddy skills path
    if workbuddy_skills_path is None:
        workbuddy_skills_path = get_workbuddy_skills_path()
    else:
        workbuddy_skills_path = Path(workbuddy_skills_path)
    
    # Ensure WorkBuddy skills directory exists
    workbuddy_skills_path.mkdir(parents=True, exist_ok=True)
    
    # Target installation path
    target_path = workbuddy_skills_path / skill_name
    
    # Check if already exists
    if target_path.exists():
        if backup:
            # Create backup
            backup_path = workbuddy_skills_path / f"{skill_name}.backup"
            if backup_path.exists():
                remove_path(backup_path)
            _ = shutil.copytree(target_path, backup_path)
            print(f"📦 Backed up existing skill to: {backup_path}")
        
        # Delete existing skill
        print(f"🗑️  Deleting existing skill: {target_path}")
        remove_path(target_path)
    
    # Create target directory
    target_path.mkdir(parents=True, exist_ok=True)
    
    # Unzip package to WorkBuddy
    print(f"📥 Installing skill: {skill_name}")
    print(f"   Source package: {zip_path}")
    print(f"   Target: {target_path}")
    
    with zipfile.ZipFile(zip_path, 'r') as zipf:
        zipf.extractall(target_path.parent)
    
    # Display installed files
    installed_files = list(target_path.rglob("*"))
    for file in installed_files:
        if file.is_file():
            rel_path = file.relative_to(target_path)
            print(f"   ✓ {rel_path}")
    
    print(f"✅ Installation complete: {target_path}")
    return target_path

def backup_skill(skill_dir: PathLike, workbuddy_skills_path: PathLike | None = None) -> Path | None:
    """
    Backup an already-installed skill (packaging + installation skipped).
    
    Args:
        skill_dir: Skill directory (used to derive skill name)
        workbuddy_skills_path: WorkBuddy skills path (optional, auto-detect)
    
    Returns:
        Backup path if the skill was backed up, None if it didn't exist.
    """
    skill_name = Path(skill_dir).name

    # Get WorkBuddy skills path
    if workbuddy_skills_path is None:
        workbuddy_skills_path = get_workbuddy_skills_path()
    else:
        workbuddy_skills_path = Path(workbuddy_skills_path)

    target_path = workbuddy_skills_path / skill_name

    if not target_path.exists():
        print(f"⚠️  No existing skill found to back up: {target_path}")
        return None

    backup_path = workbuddy_skills_path / f"{skill_name}.backup"
    if backup_path.exists():
        print(f"🗑️  Removing old backup: {backup_path}")
        remove_path(backup_path)

    print(f"📦 Backing up skill: {skill_name}")
    print(f"   Source: {target_path}")
    print(f"   Backup: {backup_path}")
    _ = shutil.copytree(target_path, backup_path)

    print(f"✅ Backup complete: {backup_path}")
    return backup_path


def update_local_from_workbuddy(skill_dir: PathLike,
                                workbuddy_skills_path: PathLike | None = None) -> Path:
    """
    Update local skill directory from the installed version in WorkBuddy.
    This first backs up the installed version in WorkBuddy, then copies it back
    to the local source directory.  A copy of the old local files is kept as
    ``<skill_name>.local.backup`` for safety.

    Args:
        skill_dir: Local skill directory (used to derive skill name and as the
                   update target)
        workbuddy_skills_path: WorkBuddy skills path (optional, auto-detect)

    Returns:
        Updated local skill directory path
    """
    skill_dir = Path(skill_dir).resolve()
    skill_name = skill_dir.name

    # Get WorkBuddy skills path (resolve early so we can check existence first)
    if workbuddy_skills_path is None:
        workbuddy_skills_path = get_workbuddy_skills_path()
    else:
        workbuddy_skills_path = Path(workbuddy_skills_path)

    installed_path = workbuddy_skills_path / skill_name

    # Ensure the WorkBuddy skill exists before proceeding
    if not installed_path.exists():
        print(f"⚠️  No installed skill found in WorkBuddy: {installed_path}")
        print("   Cannot update local skill.")
        return skill_dir

    # Create local skill directory if it does not exist
    local_existed = skill_dir.exists()
    if not local_existed:
        print(f"📁 Creating local skill directory: {skill_dir}")
        skill_dir.mkdir(parents=True, exist_ok=True)

    # Step 1: Backup the installed version using existing backup_skill()
    print(f"\n🔄 Step 1: Backing up installed version from WorkBuddy…")
    _ = backup_skill(skill_dir, workbuddy_skills_path)

    # Step 2: Backup local source directory (only if it already existed)
    local_backup: Path | None = None
    if local_existed:
        local_backup = skill_dir.parent / f"{skill_name}.local.backup"
        print(f"\n🔄 Step 2: Backing up local source directory…")
        if local_backup.exists():
            print(f"   🗑️  Removing old local backup: {local_backup}")
            remove_path(local_backup)
        _ = shutil.copytree(skill_dir, local_backup)
        print(f"   ✅ Local source backed up to: {local_backup}")
        remove_path(skill_dir)
    else:
        # Remove the empty directory we just created
        remove_path(skill_dir)

    # Step 3: Copy installed version to local source
    print(f"\n🔄 Step 3: Copying installed version back to local source…")
    print(f"   From: {installed_path}")
    print(f"   To:   {skill_dir}")

    _ = shutil.copytree(installed_path, skill_dir)

    # Display updated files
    updated_files = sorted(skill_dir.rglob("*"))
    for file in updated_files:
        if file.is_file():
            rel_path = file.relative_to(skill_dir)
            print(f"      ✓ {rel_path}")

    print(f"\n✅ Update complete: {skill_dir}")
    if local_existed:
        print(f"   Local backup kept at: {local_backup}")
    return skill_dir


def collect_included_files(skill_dir: PathLike) -> set[str]:
    """
    Walk a skill directory and return the set of relative file paths that the
    packaging process would actually include (i.e. excluding the same
    files/directories that ``package_skill`` skips).

    Args:
        skill_dir: Skill directory path

    Returns:
        Set of relative path strings (posix-style) for included files
    """
    skill_dir = Path(skill_dir).resolve()

    if not skill_dir.exists():
        raise FileNotFoundError(f"Skill directory does not exist: {skill_dir}")

    if not skill_dir.is_dir():
        raise NotADirectoryError(f"Not a directory: {skill_dir}")

    included: set[str] = set()

    # Load .gitignore rules for automatic exclusion
    gitignore_matcher = GitignoreMatcher(skill_dir)

    for root, dirs, files in os.walk(skill_dir, topdown=True):
        # Compute relative path of the current root for gitignore checks
        root_rel = Path(root).relative_to(skill_dir)

        # Prune excluded directories in-place so we don't recurse into them
        # (gitignore rules, plus a hard-coded exclusion of a top-level "tests"
        #  directory — kept identical to package_skill so --diff stays in sync)
        dirs[:] = [
            d
            for d in dirs
            if not gitignore_matcher.is_dir_ignored(
                (root_rel / d).as_posix() if str(root_rel) != "." else d
            )
            and not (str(root_rel) == "." and d == "tests")
        ]

        for file in files:
            file_path = Path(root) / file

            # Skip files that packaging would exclude
            if should_exclude(file_path, skill_dir, gitignore_matcher):
                continue

            rel_path = file_path.relative_to(skill_dir).as_posix()
            included.add(rel_path)

    return included


def file_hash(path: PathLike) -> str:
    """
    Return the SHA-256 hex digest of a file's bytes.

    Args:
        path: File path

    Returns:
        SHA-256 hex digest string
    """
    path = Path(path)
    sha = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            sha.update(chunk)
    return sha.hexdigest()


def diff_skill(skill_dir: PathLike,
               workbuddy_skills_path: PathLike | None = None) -> dict[str, set[str]]:
    """
    Compare the installed skill (in WorkBuddy) with the current local source
    skill directory, excluding the files/directories that the packaging process
    would skip.

    Detects three kinds of drift:
      - only_local:    files present locally but not installed (will be packaged)
      - only_installed: files present in the installed version but not locally
      - modified:      files present in both but with different content (hash)

    Args:
        skill_dir: Local skill directory (used to derive skill name and as the
                   comparison source)
        workbuddy_skills_path: WorkBuddy skills path (optional, auto-detect)

    Returns:
        Dict with keys ``only_local``, ``only_installed``, ``modified`` mapping
        to sets of relative path strings.
    """
    skill_dir = Path(skill_dir).resolve()
    skill_name = skill_dir.name

    # Get WorkBuddy skills path
    if workbuddy_skills_path is None:
        workbuddy_skills_path = get_workbuddy_skills_path()
    else:
        workbuddy_skills_path = Path(workbuddy_skills_path)

    installed_path = workbuddy_skills_path / skill_name

    # Either side (local source or installed) may be missing — the diff should
    # still run and report what it can rather than aborting with an error.
    local_exists = skill_dir.exists() and skill_dir.is_dir()
    installed_exists = installed_path.exists() and installed_path.is_dir()

    if not local_exists and not installed_exists:
        print(f"\n⚠️  Neither side found — nothing to compare:")
        print(f"   Local source:    {skill_dir}")
        print(f"   Installed (WB):  {installed_path}")
        print("=" * 60)
        return {"only_local": set(), "only_installed": set(), "modified": set()}

    # Collect files that packaging would include, for whichever side exists
    local_files: set[str] = collect_included_files(skill_dir) if local_exists else set()
    installed_files: set[str] = collect_included_files(installed_path) if installed_exists else set()

    only_local = local_files - installed_files
    only_installed = installed_files - local_files

    # For files present on both sides, compare content via hash
    modified: set[str] = set()
    common = local_files & installed_files
    for rel in common:
        local_fp = skill_dir / rel
        installed_fp = installed_path / rel
        try:
            if local_fp.stat().st_size != installed_fp.stat().st_size:
                modified.add(rel)
                continue
            if file_hash(local_fp) != file_hash(installed_fp):
                modified.add(rel)
        except OSError:
            # If we can't read one side, treat as modified to be safe
            modified.add(rel)

    # ---- Print report ----
    print(f"\n📊 Comparing skill: {skill_name}")
    print(f"   Local source:    {skill_dir}{'' if local_exists else '  (not found)'}")
    print(f"   Installed (WB):  {installed_path}{'' if installed_exists else '  (not found)'}")

    if not only_local and not only_installed and not modified:
        print("\n✅ No differences found — installed matches local source.")
        print("="*60)
        return {"only_local": only_local, "only_installed": only_installed, "modified": modified}

    print("\n" + "="*60)
    if only_local:
        print(f"➕ Only in local source (not installed) — {len(only_local)} file(s):")
        for rel in sorted(only_local):
            print(f"      + {rel}")
    if only_installed:
        print(f"➖ Only in installed version (not local) — {len(only_installed)} file(s):")
        for rel in sorted(only_installed):
            print(f"      - {rel}")
    if modified:
        print(f"✏️  Modified (content differs) — {len(modified)} file(s):")
        for rel in sorted(modified):
            print(f"      ~ {rel}")

    print("\n" + "="*60)
    print(f"📋 Summary: {len(only_local)} added, {len(only_installed)} removed, {len(modified)} modified (packaging-excluded files ignored).")
    print("="*60)

    return {"only_local": only_local, "only_installed": only_installed, "modified": modified}


def main() -> None:
    """Main function"""
    if len(sys.argv) < 2:
        print("Usage: python pack_and_install_skill.py <skill_directory> [--zip-only] [--backup] [--backup-only] [--update-local] [--diff]")
        print("\nExamples:")
        print("  python pack_and_install_skill.py ./pptx-translate")
        print("  python pack_and_install_skill.py ./pptx-translate --zip-only         # Package only, no installation")
        print("  python pack_and_install_skill.py ./pptx-translate --backup           # Backup before installation")
        print("  python pack_and_install_skill.py ./pptx-translate --backup-only      # Only backup, no packaging/installation")
        print("  python pack_and_install_skill.py ./pptx-translate --update-local     # Sync WorkBuddy installed version back to local source")
        print("  python pack_and_install_skill.py ./pptx-translate --diff             # Compare installed skill vs local source (excludes packaging files)")
        sys.exit(1)
    
    skill_dir = sys.argv[1]
    zip_only = "--zip-only" in sys.argv
    backup = "--backup" in sys.argv
    backup_only = "--backup-only" in sys.argv
    update_local = "--update-local" in sys.argv
    diff = "--diff" in sys.argv
    zip_path: Path | None = None
    
    try:
        if backup_only:
            _ = backup_skill(skill_dir)
            return
        
        if update_local:
            _ = update_local_from_workbuddy(skill_dir)
            return
        
        if diff:
            _ = diff_skill(skill_dir)
            return
        
        # Package skill
        zip_path = package_skill(skill_dir)
        print()
        
        # Install skill (unless zip-only mode)
        if not zip_only:
            target_path = install_skill(zip_path=zip_path, backup=backup)
            
            print("\n" + "="*60)
            print("🎉 Skill installed successfully!")
            print("="*60)
            print(f"Skill name: {Path(skill_dir).name}")
            print(f"Installation path: {target_path}")
            print(f"Package file: {zip_path}")
            print("\nPlease restart WorkBuddy to load the new skill.")
            print("="*60)
        else:
            print("\n" + "="*60)
            print("🎉 Skill packaged successfully!")
            print("="*60)
            print(f"Skill name: {Path(skill_dir).name}")
            print(f"Package file: {zip_path}")
            print("="*60)
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
