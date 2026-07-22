# AI Agent Skills Repository

A collection of reusable skills for AI coding assistants and agents. These skills extend the capabilities of AI agents by providing specialized knowledge, workflows, and executable scripts for specific domains.

> **Note:** This repository uses a git submodule. Clone with `git clone --recurse-submodules` (or run `git submodule update --init` after cloning) so the `sg-bank-to-md` skill folder is populated.

## 🎯 What Are Skills?

Skills are domain-specific extensions that provide:
- **Specialized Knowledge** — Expertise in specific domains (e.g., document processing, data analysis)
- **Standardized Workflows** — Step-by-step procedures for complex tasks
- **Executable Scripts** — Tools and scripts to automate repetitive operations
- **Best Practices** — Proven methodologies and patterns

Each skill is self-contained and includes documentation (`SKILL.md`), scripts, and references needed for the AI agent to perform tasks effectively.

## 📦 Available Skills

The full, detailed catalogue (features, use cases, triggers, and tech stack for each skill) lives in **[SKILLS.md](./SKILLS.md)**.

| Skill | Type | One-line Description |
| --- | --- | --- |
| [`eddx-translate`](./eddx-translate/SKILL.md) | Basic | Translate text labels in EdrawMax/EdrawMind (.eddx) diagrams seamlessly |
| [`kb-ingest`](./kb-ingest/SKILL.md) | Orchestrator | Thin orchestrator that turns `.pptx` slides into knowledge-base-ready JSONL chunks for RAG / agent pipelines |
| [`meeting-minutes`](./meeting-minutes/SKILL.md) | Basic | Turn a meeting transcript plus a Markdown template into clean, structured meeting minutes |
| [`meeting-minutes-export`](./meeting-minutes-export/SKILL.md) | Orchestrator | Orchestrator that runs meeting-minutes and exports the result to Word (.docx) |
| [`bank-ir-consolidate`](./bank-ir-consolidate/SKILL.md) | Orchestrator | Consolidate multiple sg-bank-to-md IR JSON files into one and render a cross-bank, multi-currency Markdown summary |
| [`sg-bank-to-md`](./sg-bank-to-md/SKILL.md) *(submodule → [`sg-bank-pdf-parser`](https://github.com/shaowen310/sg-bank-pdf-parser))* | Basic | Convert Singapore bank (DBS, OCBC, UOB, ICBC) PDF statements into clean Markdown tables with auto-detection |
| [`pptx-translate`](./pptx-translate/SKILL.md) | Basic | Translate PowerPoint presentations while preserving all formatting |
| [`pptx2md`](./pptx2md/SKILL.md) | Basic | Convert `.pptx` slides to Markdown with images extracted, for editing, search, re-style, or KB ingestion |

---

## 🚀 How to Use These Skills

### For AI Agents (CodeBuddy, Claude, etc.)

1. **Install the skill** by copying the skill directory to your agent's skills folder
2. **Load the skill** — the agent reads `SKILL.md` to understand the workflow
3. **Execute tasks** — the agent follows the documented procedures and uses provided scripts

### For Developers

Each skill directory contains:
```
skill-name/
├── SKILL.md           # Skill documentation (required)
├── scripts/           # Executable scripts
├── assets/            # Static assets (if any)
└── references/        # Reference materials (if any)
```

## 🛠️ Development Tools

### `pack_and_install_skill.py` — Auto-package & Install Skills

A utility script to automatically package skills, install them to WorkBuddy, and manage bidirectional sync.

**Features:**
- 📦 **Auto-packaging**: Packages skill directory into a `.zip` file
- 📥 **Auto-installation**: Unzips the package to WorkBuddy's skills folder
- 🔒 **Respects `.gitignore`**: Excludes all files/directories matched by `.gitignore` patterns (walking up to the repo root) — in addition, always excludes a top-level `tests` directory (exact name, case-sensitive)
- 🔄 **Smart overwrite**: Automatically removes existing zip package before creating a new one
- 💾 **Backup before install**: Can backup existing skills before overwriting (with `--backup` flag)
- ☝️ **Backup-only mode**: Backup existing installed skill without any packaging/installation (with `--backup-only` flag)
- 📦 **Zip-only mode**: Package skill without installing (with `--zip-only` flag)
- 🔁 **Update local from WorkBuddy**: Reverse-sync — copy the installed version from WorkBuddy back to your local source directory, keeping both a WorkBuddy backup and a local backup (with `--update-local` flag)
- 🔍 **Diff installed vs local**: Compare the installed skill in WorkBuddy with your local source, showing files that are added, removed, or modified — automatically ignoring the same files/directories that packaging excludes (with `--diff` flag)

**Usage:**
```bash
# Full workflow: package + install (default)
python pack_and_install_skill.py <skill_directory>

# Package only, skip installation
python pack_and_install_skill.py <skill_directory> --zip-only

# Install with backup of existing skill
python pack_and_install_skill.py <skill_directory> --backup

# Backup only (no packaging/installation)
python pack_and_install_skill.py <skill_directory> --backup-only

# Sync WorkBuddy installed version back to local source
python pack_and_install_skill.py <skill_directory> --update-local

# Compare installed skill against local source (ignores packaging-excluded files)
python pack_and_install_skill.py <skill_directory> --diff
```

**How it works:**
1. **Default mode** (package + install):
   - Removes existing zip package if present
   - Packages skill directory into a `.zip` file (excluding files matched by `.gitignore` rules, plus a top-level `tests` directory)
   - Removes existing skill from WorkBuddy if present
   - Unzips the package to WorkBuddy's skills folder
   
2. **Zip-only mode** (`--zip-only`):
   - Only creates the `.zip` package
   - Skips installation to WorkBuddy

3. **Backup-only mode** (`--backup-only`):
   - Detects the skill name from the provided directory
   - Checks if a corresponding skill exists in WorkBuddy
   - Copies the installed skill to `<skill_name>.backup` in WorkBuddy's skills folder
   - No packaging or installation is performed

4. **Update local from WorkBuddy** (`--update-local`):
   - **Step 1**: Backs up the installed version in WorkBuddy to `<skill_name>.backup`
   - **Step 2**: Backs up your local source directory to `<skill_name>.local.backup`
   - **Step 3**: Removes the local source directory and copies the WorkBuddy version back
   - Safely synchronizes any changes made directly in WorkBuddy back to your source tree

5. **Diff installed vs local** (`--diff`):
   - Reads the skill name from the provided directory
   - Compares the installed version in WorkBuddy against your local source directory
   - Reports three categories of drift: files **only in local** (not yet installed), files **only in installed** (added/changed directly in WorkBuddy), and files **modified** (same path, different content)
   - Applies the same exclusion rules as packaging (`.gitignore` plus a top-level `tests` directory), so irrelevant files never appear as false differences



**WorkBuddy Installation Path:**
- Default: `C:\Users\%USERNAME%\.workbuddy\skills\`
- Auto-detected from system username

**Requirements:**
- Python 3.6+
- No additional dependencies (uses standard library only)

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
