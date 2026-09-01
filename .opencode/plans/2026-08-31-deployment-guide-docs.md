# Deployment Guide & Documentation Updates Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create a comprehensive deployment guide and update all documentation to reflect production-ready features.

**Architecture:** Create a new deployment.md with all deployment options, update existing docs to reference new features (--workers, PostgreSQL, security), add deployment page to mkdocs nav.

**Tech Stack:** Markdown, MkDocs Material

**Spec:** User requested comprehensive deployment guide with every option explored, then update all docs.

## Global Constraints

- Markdown must be valid MkDocs Material syntax
- All code blocks must have language tags
- Tables must be properly formatted
- All internal links must work

---

## File Map

| File | Action | Purpose |
|------|--------|---------|
| `docs/deployment.md` | Create | Comprehensive deployment guide |
| `mkdocs.yml` | Modify | Add deployment page to nav |
| `docs/install.md` | Modify | Add deployment options |
| `docs/config.md` | Modify | Add production config, security notes |
| `docs/cli.md` | Modify | Add --workers and --log-level flags |
| `README.md` | Modify | Add deployment section |
| `CONTRIBUTING.md` | Modify | Update project structure |

---

### Task 1: Create docs/deployment.md

**Files:**
- Create: `docs/deployment.md`

**Interfaces:**
- Consumes: existing codebase features (Dockerfile, docker-compose.yml, gunicorn, Alembic)
- Produces: Complete deployment documentation

- [ ] **Step 1: Create deployment.md with full content**

Write the complete deployment guide covering all sections listed below.

- [ ] **Step 2: Verify markdown syntax**

- [ ] **Step 3: Commit**

```bash
git add docs/deployment.md
git commit -m "docs: add comprehensive production deployment guide"
```

---

### Task 2: Update mkdocs.yml

**Files:**
- Modify: `mkdocs.yml:52-59`

**Interfaces:**
- Consumes: new deployment.md
- Produces: Updated nav with deployment page

- [ ] **Step 1: Add deployment to nav**

Add `- Deployment: deployment.md` to the nav section after Quick Start.

- [ ] **Step 2: Commit**

```bash
git add mkdocs.yml
git commit -m "docs: add deployment page to mkdocs nav"
```

---

### Task 3: Update docs/install.md

**Files:**
- Modify: `docs/install.md`

**Interfaces:**
- Consumes: Docker features from Phase 1
- Produces: Updated installation docs with Docker options

- [ ] **Step 1: Update Docker section in install.md**

Expand the Docker section to include building with dashboard, docker-compose usage, and bare metal options.

- [ ] **Step 2: Commit**

```bash
git add docs/install.md
git commit -m "docs: update install.md with Docker and deployment options"
```

---

### Task 4: Update docs/config.md

**Files:**
- Modify: `docs/config.md`

**Interfaces:**
- Consumes: PostgreSQL config, production env vars, security settings
- Produces: Updated configuration docs

- [ ] **Step 1: Update config.md**

Add production env vars, PostgreSQL configuration, security notes (DEBUG, dev auth), and WORKERS setting.

- [ ] **Step 2: Commit**

```bash
git add docs/config.md
git commit -m "docs: update config.md with production and security settings"
```

---

### Task 5: Update docs/cli.md

**Files:**
- Modify: `docs/cli.md:159-173`

**Interfaces:**
- Consumes: --workers and --log-level flags from Phase 1
- Produces: Updated CLI docs

- [ ] **Step 1: Update serve command docs**

Add --workers and --log-level flags to the serve command section.

- [ ] **Step 2: Commit**

```bash
git add docs/cli.md
git commit -m "docs: update cli.md with --workers and --log-level flags"
```

---

### Task 6: Update README.md

**Files:**
- Modify: `README.md`

**Interfaces:**
- Consumes: deployment features
- Produces: Updated README with deployment section

- [ ] **Step 1: Add deployment section to README.md**

Add a brief deployment section after Quick Start, pointing to the full deployment guide.

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: add deployment section to README.md"
```

---

### Task 7: Update CONTRIBUTING.md

**Files:**
- Modify: `CONTRIBUTING.md`

**Interfaces:**
- Consumes: updated project structure
- Produces: Updated contributing docs

- [ ] **Step 1: Update project structure in CONTRIBUTING.md**

Add alembic/, docker-compose.yml, .dockerignore to the project structure.

- [ ] **Step 2: Commit**

```bash
git add CONTRIBUTING.md
git commit -m "docs: update CONTRIBUTING.md with new project structure"
```

---

### Task 8: Final verification

- [ ] **Step 1: Verify all markdown files exist**

- [ ] **Step 2: Verify mkdocs.yml is valid**

- [ ] **Step 3: Check git log**

- [ ] **Step 4: Push to origin**

```bash
git push origin main
```
