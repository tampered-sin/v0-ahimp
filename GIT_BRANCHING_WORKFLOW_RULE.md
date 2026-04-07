# Git Branching & Commit Workflow Rule

## Overview
This rule establishes the workflow for task-based branching, development, and GitHub integration across all implementation tickets (TASK-101 through TASK-502).

---

## Branch Naming Convention

**Format:** `task/{TASK_ID}/{short-description}`

**Examples:**
```
task/TASK-101/lightgbm-migration
task/TASK-202/data-ingestion-agent
task/TASK-303/supply-chain-scorecard
task/TASK-501/agent-dashboard-ui
```

**Rules:**
- ✅ Use ticket ID (TASK-101, TASK-201, etc.)
- ✅ Use lowercase letters, numbers, hyphens only
- ✅ Keep description under 40 characters
- ✅ No spaces, underscores, or special characters
- ✅ Always branch from `main` (or `develop` if using dual-branch strategy)

---

## Workflow Steps

### Phase 1: Task Initiation
1. **Create local branch** from main:
   ```bash
   git checkout main
   git pull origin main
   git checkout -b task/TASK-101/lightgbm-migration
   ```

2. **Track in IMPLEMENTATION_TICKETS.md:**
   - Update status: `Not Started` → `In Progress`
   - Add branch reference: `Branch: task/TASK-101/lightgbm-migration`

### Phase 2: Development & Commits

**Commit Message Format:** `[TASK-XXX] Brief description`

**Examples:**
```
[TASK-101] Create LightGBM model training pipeline
[TASK-101] Add feature importance calculations
[TASK-101] Implement cross-validation (5-fold)
[TASK-202] Add CSV validation rules
[TASK-202] Implement anomaly detection for ingestion
```

**Commit Guidelines:**
- ✅ Atomic commits (1 feature/fix per commit)
- ✅ Clear, descriptive messages
- ✅ Include issue/ticket reference
- ✅ One commit per logical change
- ✅ Keep commits under 400 lines per file changed

**Bad Examples:**
```
fix bugs
update
changes
wip
```

**Good Examples:**
```
[TASK-101] Implement LightGBM with hyperparameter tuning (n_estimators=200)
[TASK-202] Add column validation and duplicate detection for CSV ingestion
[TASK-301] Calculate supplier composite score with 5-factor weighting
```

### Phase 3: Testing & Validation

Before committing, ensure:
```bash
# Run unit tests
pytest backend/tests/test_lightgbm.py -v

# Run linting
flake8 backend/models/lightgbm_model.py
black --check backend/models/lightgbm_model.py

# Type checking
mypy backend/models/lightgbm_model.py
```

### Phase 4: Task Completion & Push

1. **Final commit:**
   ```bash
   git commit -m "[TASK-101] LightGBM migration complete - R²=0.97, 3.2x speedup"
   ```

2. **Verify all changes:**
   ```bash
   git log --oneline task/TASK-101/lightgbm-migration ~10..HEAD
   git diff main..task/TASK-101/lightgbm-migration --stat
   ```

3. **Push branch to GitHub:**
   ```bash
   git push origin task/TASK-101/lightgbm-migration
   ```

4. **Update ticket status:**
   - Status: `In Progress` → `Completed`
   - Mark all acceptance criteria ✅
   - Add branch push timestamp

### Phase 5: Manual PR & Merge (User Action)

User manually creates pull request on GitHub:
1. Go to `v0-ahimp` repository
2. Click "New Pull Request"
3. **Base branch:** `develop` (or `main`)
4. **Compare branch:** `task/TASK-101/lightgbm-migration`
5. **Title:** `[TASK-101] Migrate XGBoost to LightGBM for demand forecasting`
6. **Description:** Include:
   - Link to ticket
   - Key changes
   - Performance improvements
   - Testing results
7. Request code review
8. After approval, merge to develop branch

---

## Branch Lifecycle

```
main (stable)
  ↑
  ├─ PR from develop (after reviews)
  │
develop (integration)
  ↑
  ├─ PR #1: task/TASK-101/lightgbm-migration ✅ (Reviewed)
  ├─ PR #2: task/TASK-102/catboost-model (Pending Review)
  ├─ PR #3: task/TASK-201/crewai-setup (In Progress)
  └─ PR #4: task/TASK-301/supplier-scoring (Ready for Review)

Feature branches:
  task/TASK-101/lightgbm-migration → (PR merged, DELETE)
  task/TASK-102/catboost-model → (active development)
  task/TASK-201/crewai-setup → (active development)
```

---

## Simultaneous Development (Multiple Tasks)

**Example: 2 engineers working on TASK-101 and TASK-102 simultaneously**

```bash
# Engineer 1 - TASK-101
git checkout -b task/TASK-101/lightgbm-migration
# ... make commits ...
git push origin task/TASK-101/lightgbm-migration

# Engineer 2 - TASK-102
git checkout -b task/TASK-102/catboost-model
# ... make commits ...
git push origin task/TASK-102/catboost-model

# Both branches work independently until merged to develop
```

**Conflict Resolution:**
- If both modify same file, resolve in PR review
- Rebase on develop if needed: `git rebase develop`
- Test after rebase: `pytest` to ensure no breaks

---

## Commit Best Practices

### 1. Logical Grouping
```
[TASK-101] Create LightGBM model class with training method
[TASK-101] Add cross-validation and hyperparameter search
[TASK-101] Implement feature importance and model serialization
```

### 2. Include Context
```
❌ Bad:  [TASK-101] fix
✅ Good: [TASK-101] Fix feature normalization for LightGBM (scale to 0-1 range)
```

### 3. Include Metrics
```
❌ Bad:  [TASK-101] Model training complete
✅ Good: [TASK-101] Complete LightGBM training - R²=0.973, MAE=5.2, train_time=192s
```

### 4. Link Related Changes
```
[TASK-101] Update requirements.txt with lightgbm==4.0.0
[TASK-101] Add LightGBM import to backend/models/__init__.py
[TASK-101] Modify backend/main.py to use LightGBM instead of XGBoost
```

---

## Commit Frequency

**Expected frequency per task:** 3-8 commits

| Task Complexity | Expected Commits | Duration |
|---|---|---|
| **Simple (5 pts)** | 2-3 commits | 1-2 days |
| **Medium (8 pts)** | 3-5 commits | 2-3 days |
| **Large (13+ pts)** | 5-8 commits | 3-5 days |

**Example TASK-101 (13 pts) commit history:**
```
commit abc123 - [TASK-101] Create LightGBM model class with training method
commit def456 - [TASK-101] Add feature importance ranking and visualization
commit ghi789 - [TASK-101] Implement cross-validation pipeline (5-fold)
commit jkl012 - [TASK-101] Add hyperparameter tuning search space
commit mno345 - [TASK-101] Benchmark LightGBM vs XGBoost (3.2x speedup achieved)
commit pqr678 - [TASK-101] Add unit tests and documentation
```

---

## Before Pushing to GitHub

**Checklist:**
- [ ] All tests passing locally: `pytest backend/tests/test_lightgbm.py`
- [ ] Code formatted: `black backend/models/lightgbm_model.py`
- [ ] Linting clean: `flake8 backend/models/lightgbm_model.py`
- [ ] Type hints valid: `mypy backend/models/lightgbm_model.py`
- [ ] Documentation updated in README/docstrings
- [ ] No debug prints or commented code
- [ ] No hardcoded values (use config.py)
- [ ] Branch name follows convention: `task/TASK-XXX/*`
- [ ] Commit messages are descriptive and include ticket ID
- [ ] No merge conflicts with main/develop

---

## GitHub Push Command

```bash
# Ensure you're on correct branch
git branch  # Should show: * task/TASK-101/lightgbm-migration

# View commits to be pushed
git log --oneline origin/main..HEAD

# Push to GitHub
git push origin task/TASK-101/lightgbm-migration

# Verify on GitHub (opens browser)
# or manually check: https://github.com/tampered-sin/v0-ahimp/branches
```

---

## After Merge (Cleanup)

Once the PR is merged to develop by the user:

```bash
# Switch to main/develop
git checkout main

# Pull latest changes
git pull origin main

# Delete local branch
git branch -d task/TASK-101/lightgbm-migration

# Delete remote branch (can also do from GitHub UI)
git push origin --delete task/TASK-101/lightgbm-migration
```

---

## Tracking in IMPLEMENTATION_TICKETS.md

Update ticket status flow:

```markdown
## TICKET: TASK-101
**Status:** Not Started
**Branch:** (none)

↓ (Engineer starts work)

## TICKET: TASK-101
**Status:** In Progress
**Branch:** task/TASK-101/lightgbm-migration

↓ (Push to GitHub)

## TICKET: TASK-101
**Status:** In Progress
**Branch:** task/TASK-101/lightgbm-migration
**GitHub:** https://github.com/tampered-sin/v0-ahimp/tree/task/TASK-101/lightgbm-migration

↓ (PR created, awaiting review)

## TICKET: TASK-101
**Status:** In Review
**PR:** #42 (pending approval)

↓ (PR merged to develop)

## TICKET: TASK-101
**Status:** Completed
**PR:** #42 ✅ MERGED
**Merged Date:** 2026-04-15
```

---

## Parallel Development Rules

**When multiple engineers work simultaneously:**

1. Each engineer creates their own branch from `main`
2. Branches must NOT depend on each other
3. If cross-dependencies exist:
   - Engineer A pushes to GitHub first
   - Engineer B pulls that branch: `git pull origin task/TASK-101/lightgbm-migration`
   - Engineer B rebases: `git rebase task/TASK-101/lightgbm-migration`
   - Then continue development

**Example: Dependency Chain**
```
TASK-101 (LightGBM) → TASK-105 (Ensemble)

Timeline:
- Day 1-3: Both engineers start work on separate branches
- Day 3: TASK-101 completes, branch pushed, PR created
- Day 4: TASK-101 merged to develop
- Day 4: Engineer on TASK-105 pulls develop: git pull origin develop
- Day 4: Engineer on TASK-105 rebases if needed
- Day 5-6: TASK-105 completes using updated code from TASK-101
```

---

## Conflict Resolution

**If merge conflicts occur with main/develop:**

```bash
# While on task branch
git fetch origin
git rebase origin/develop

# Resolve conflicts in editor
# Files marked: <<<<<<< HEAD, =======, >>>>>>>

# After resolving:
git add .
git rebase --continue

# Push rebased branch (force if necessary)
git push origin task/TASK-101/lightgbm-migration --force-with-lease
```

---

## Quick Reference

```bash
# START NEW TASK
git checkout main
git pull origin main
git checkout -b task/TASK-101/lightgbm-migration

# DEVELOP & COMMIT
git add backend/models/lightgbm_model.py
git commit -m "[TASK-101] Implement LightGBM training with cross-validation"

# PUSH TO GITHUB
git push origin task/TASK-101/lightgbm-migration

# DELETE LOCAL BRANCH (after merge)
git branch -d task/TASK-101/lightgbm-migration

# DELETE REMOTE BRANCH (after merge)
git push origin --delete task/TASK-101/lightgbm-migration
```

---

## Exceptions & Special Cases

### Hotfix for Production (main branch)
```bash
git checkout main
git checkout -b hotfix/critical-bug-fix
# Work & test
git push origin hotfix/critical-bug-fix
# Create PR directly to main
```

### Long-Running Tasks (>2 weeks)
- Keep branch updated: `git rebase develop` weekly
- Create draft PR early to track progress
- Push intermediate changes even if not complete

### Experimental Feature (not in tickets)
```bash
git checkout -b experiment/new-feature-xyz
# If successful → convert to TASK
# If unsuccessful → delete without merging
```

---

## Enforcement & Monitoring

**Automated checks on push:**
- ✅ Branch name matches pattern: `task/TASK-\d+/.*`
- ✅ Commit messages include ticket ID
- ✅ Tests pass locally before push
- ✅ No merge to main without PR approval

**GitHub branch protection rules:**
- Require pull request before merge
- Require approving reviews (1+)
- Require status checks to pass
- Dismiss stale PR approvals when new commits pushed

---

## Summary

| Step | Action | Command |
|------|--------|---------|
| 1 | Create branch | `git checkout -b task/TASK-101/lightgbm-migration` |
| 2 | Develop & commit | `git commit -m "[TASK-101] description"` |
| 3 | Push to GitHub | `git push origin task/TASK-101/lightgbm-migration` |
| 4 | Create PR (manual) | Via GitHub UI, base → develop |
| 5 | Await review | Pull request pending approval |
| 6 | Merge (manual) | User merges PR to develop |
| 7 | Cleanup | `git branch -d` (local), `git push origin --delete` (remote) |
