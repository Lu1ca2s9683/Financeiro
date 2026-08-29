# Phase 0 Baseline Report

## Repository Context
- **Base SHA**: `45ce758b1016f5d4a3144f77e896b6348cec01bb`
- **Branch**: `fix-test-baseline-phase0`
- **Purpose**: establish a deterministic, isolated validation baseline before Phase 1 production bug fixes.

## Backend Test Environment
- Tests use the explicit `config.settings_test` settings module.
- Both `default` and `vendas` are isolated in-memory SQLite databases.
- `config.test_routers.TestRouter` permits only Django `auth` and `contenttypes` migrations on the simulated `vendas` database; Financeiro application migrations remain on `default`.
- JWT helpers derive their signing key from `settings.SECRET_KEY` rather than a production/development hard-coded token key.

## Sales Isolation Strategy
- API/DRE tests patch `VendasClientSQL.get_faturamento_por_loja` or inject a mock Sales client, so PostgreSQL-specific revenue SQL is not executed by automated tests.
- Authentication-boundary tests resolve Django `User` records from the isolated SQLite `vendas` database.
- Login tests patch the raw Sales permission lookup (`fetch_user_lojas`) so no external Sales SQL is required.
- The Sales contract command is unit-tested with mocked Django database introspection.

## Backend Test Inventory
Static discovery in the finalized Phase 0 test sources contains **26 test methods**:
- `test_api.py`: 15
- `test_auth.py`: 4
- `test_dre_service.py`: 2
- `test_sales_contract.py`: 5

Observed local result on Windows with Python 3.13.13:
- **Ordinary successes**: 22
- **Skipped**: 2
  - `test_update_status_open_month`: `KNOWN_BUG_PHASE_1` â€” production PATCH/status behavior is not implemented or its contract is not currently executable.
  - `test_update_status_closed_month`: `KNOWN_BUG_PHASE_1` â€” production PATCH/status behavior is not implemented or its contract is not currently executable.
- **Expected failures**: 2
  - `test_dashboard_summary`: `KNOWN_BUG_PHASE_1` â€” dashboard summary does not currently report delayed/upcoming expenses as asserted by the legacy test.
  - `test_post_fechamento_preserves_status`: `KNOWN_BUG_PHASE_1` â€” closing calculation currently fails with the legacy request contract under some conditions.
- **Unexpected failures**: 0
- **Unexpected errors**: 0

**Local backend validation:** `Ran 26 tests` — `OK (skipped=2, expected failures=2)`. Django `manage.py check` reported no issues. GitHub Actions must reproduce a clean result before merge.

## Sales Database Contract Checker
`check_sales_contract` validates the current read contract used by Financeiro for:
- Django `auth_user`, deriving all concrete columns from `User._meta.concrete_fields`;
- store/auth permission tables used by `fetch_user_lojas`;
- revenue tables/columns used by `VendasClientSQL.get_faturamento_por_loja`.

The command uses Django introspection only and raises `CommandError` for missing tables, missing columns, or introspection/database failures. Unit tests verify that the command itself issues no direct SQL through `cursor.execute`.

## Frontend Validation
The baseline workflow and local validation script use lockfile-driven `npm ci`, followed by:
- `npm run lint`
- `npm run build`

Local frontend validation succeeded with Node 24.15.0 and npm 11.12.1: `npm ci` completed, ESLint reported 0 errors and 32 warnings, and Next.js 16.1.4 completed the production build successfully. `npm ci` also reported 16 dependency vulnerabilities (1 low, 3 moderate, 12 high); these are recorded for later dependency/security remediation and are intentionally not auto-fixed in Phase 0. GitHub Actions will independently validate the workflow runtime.

## Infrastructure Guardrails
- **Models changed**: NO
- **Migrations created**: NO
- **Financial formulas modified**: NO
- **Production database required by automated tests**: NO
- **Render access/configuration required by automated tests**: NO
- **Phase 1 production fixes included**: NO

## Final Acceptance Commands
Run from the repository root:

```bash
DJANGO_SETTINGS_MODULE=config.settings_test python manage.py check
DJANGO_SETTINGS_MODULE=config.settings_test python manage.py test financeiro_core -v 2
./scripts/validate_baseline.sh
```

The GitHub Actions workflow must also pass on the Phase 0 pull request before merge.
