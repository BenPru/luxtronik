# Agent Instructions

## General

- **Unrelated changes:** Do not modify files unrelated to the current task without asking first.
- **Destructive actions:** Always ask for approval before performing destructive or hard-to-reverse actions (e.g. `git push --force`, `git reset --hard`, deleting branches/files, dropping tables).

## Branch Naming

Follow [Conventional Branch](https://conventional-branch.github.io/) format: `<type>/<description>`

- Lowercase alphanumerics and hyphens only (dots allowed in release versions)
- No consecutive, leading, or trailing hyphens or dots
- Include ticket/issue number when applicable

| prefix     | when to use                                 |
| ---------- | ------------------------------------------- |
| `feature/` | new feature (alias: `feat/`)                |
| `bugfix/`  | bug fix (alias: `fix/`)                     |
| `hotfix/`  | urgent fix                                  |
| `release/` | release preparation (e.g. `release/v1.2.0`) |
| `chore/`   | non-code tasks (deps, docs, config)         |

Examples: `feat/add-solar-cooling`, `fix/header-bug`, `feature/issue-123-evu-schedule`

## Git Commits

### Approval

- **Never commit automatically.** Always wait for explicit approval before running `git commit`.
- **Tests:** If the project has tests, run them before proposing a commit. Verify that all tests pass and that code coverage has not decreased.

### Commit Message Format

Always use the format: `<type>(<scope>): <gitmoji> <description>`

**Rules:**

- `scope` is optional but use it when the change is clearly scoped to a module
  (e.g. `sensor`, `binary_sensor`, `climate`, `config_flow`, `coordinator`, `number`, `select`, `switch`, `update`, `water_heater`, `date`, `model`, `const`, `base`, `diagnostics`)
- `description`: lowercase, imperative mood ("add", not "added"), no period at end

**Pick the type and gitmoji that best reflect the nature of the change:**

| type       | gitmoji | when to use                                        |
| ---------- | ------- | -------------------------------------------------- |
| `feat`     | ✨      | new user-facing feature                            |
| `feat!`    | 💥      | breaking change                                    |
| `fix`      | 🐛      | bug fix                                            |
| `fix`      | 🩹      | minor / non-critical fix (style, typo, off-by-one) |
| `fix`      | 🚑️      | critical hotfix                                    |
| `fix`      | 🔒️      | security / privacy fix                             |
| `docs`     | 📝      | add or update documentation or comments            |
| `style`    | 🎨      | code structure / formatting (no logic change)      |
| `style`    | 💄      | UI or style files                                  |
| `refactor` | ♻️      | refactor without behaviour change                  |
| `test`     | ✅      | add, update, or fix tests                          |
| `test`     | 🧪      | add a failing test                                 |
| `perf`     | ⚡️      | performance improvement                            |
| `chore`    | 🔧      | config or tooling update                           |
| `chore`    | 🏷️      | add or update types / labels                       |
| `chore`    | 🔖      | release or version tag                             |
| `chore`    | ⬆️      | upgrade dependency                                 |
| `chore`    | ⬇️      | downgrade dependency                               |
| `ci`       | 👷      | add or update CI build system                      |
| `ci`       | 💚      | fix CI build                                       |
| `revert`   | ⏪️      | revert a previous commit                           |

**Commit message body:**

Add a blank line after the subject line, then a bullet list covering:

- what changed (one bullet per logical change, imperative style)
- why it was changed (motivation, context)
- relevant technical detail if non-obvious

Keep bullets concise (one line each). If the commit resolves a GitHub issue, end the body with `Resolves #<issue-number>`.

```
fix(coordinator): 🐛 handle missing sensor data during initialization

- add None check before accessing sensor attributes
- prevents AttributeError when heat pump is offline during startup
- log warning instead of raising exception

Resolves #542
```

**Examples from this project:**

```
fix(misc): 🏷️ add generic type args and fix parameter types
chore(typing): 🏷️ suppress unavoidable basedpyright errors
refactor: ♻️ align with HA best practices
fix(sensor): 🐛 fix duplicate variable declaration
fix(select): 🏷️ narrow entity list type and add annotations
```

### Shell Execution

Multi-line commit messages in zsh: use multiple `-m` flags (one per paragraph) or heredoc (`git commit -F - <<'EOF' ... EOF`). A single `-m` with newlines inside quotes does NOT work reliably.

## Pull Requests

- PR description must be in **English** and **Markdown** format (ready for copy & paste into GitHub).
- **PR title** must follow the same commit message format: `<type>(<scope>): <gitmoji> <description>`.
- **PR body** should use emoji to visually categorize sections and bullet points.

## Code Quality

### Type Checking

- This project uses **basedpyright** with `typeCheckingMode: basic` (see `pyrightconfig.json`).
- Run `basedpyright` before committing and ensure **0 errors**.
- CI enforces type checking via `.github/workflows/typecheck.yml`.

### Linting & Formatting

- Use **ruff** for both linting and formatting.
- Run `ruff check` and `ruff format --check` before committing.
- CI enforces ruff checks on every PR.

### Pre-commit Checklist

Before proposing a commit, verify:

1. `basedpyright` - 0 errors
2. `ruff check` - all checks passed
3. `ruff format --check` - all files formatted
4. Tests pass (if applicable)
