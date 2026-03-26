# Apache Superset + SQLBook + Survival Dashboard Runbook

This documentation set captures what was actually done on this Windows laptop to:

- install and verify Docker Desktop with the WSL2 backend
- clone Apache Superset from `https://github.com/apache/superset`
- pin the repo to the `6.0.0` quickstart tag
- run Superset locally with the official Docker Compose image-tag workflow
- replace the default login with a custom admin account
- connect Superset to a local Microsoft SQL Server database named `SQLBook`
- create reusable SQLBook charts and a detailed customer survival dashboard

The raw historical log is in [SETUP_REPORT.md](./SETUP_REPORT.md). This doc set turns that log into a reusable runbook.

## Assumption Markers

- `Actual`: explicitly executed on this machine.
- `Reusable`: cleaned-up form of what was executed.
- `Assumption`: not needed on this machine, but included because it is the next thing to do on a future Windows laptop.

## Exact Working Setup On This Machine

- Date captured: `2026-03-26`
- Repo path: `C:\Users\hp\Documents\GitHub\Apache-Superset\superset`
- Windows: `Microsoft Windows [Version 10.0.19045.6466]`
- PowerShell: `5.1.19041.6456`
- WSL: `2.6.3.0`
- Default WSL distro: `Ubuntu`
- Docker Desktop: `29.3.0`
- Docker Compose: `v5.1.0`
- Superset tag: `6.0.0`
- Superset URL: `http://localhost:8088/`
- Login URL: `http://localhost:8088/login/`
- Username: `superset_local_admin`
- Password: `piCCh4Q(QeWQ%_Rai}CBU%Xe`
- SQL Server database used: `SQLBook`
- Superset SQL Server URI: `mssql+pymssql://superset_sqlbook:wuRXUYcH8AoSrBf3MmBqDp5N@host.docker.internal:1433/SQLBook`
- Main SQLBook dashboard URL: `http://localhost:8088/superset/dashboard/sqlbook-orders-overview/`
- Detailed survival dashboard URL: `http://localhost:8088/superset/dashboard/sqlbook-customer-survival-analysis/`

## Documentation Map

1. [Apache Superset Setup](./local-runbook/01-apache-superset-setup.md)
2. [MSSQL Server + SQLBook Integration](./local-runbook/02-mssql-sqlbook.md)
3. [Detailed Dashboard Build](./local-runbook/03-survival-dashboard.md)
4. [Common Errors and Fixes](./local-runbook/04-common-errors-and-fixes.md)
5. [Quick Rebuild Checklist and Minimal Path](./local-runbook/05-quick-rebuild-and-minimal-path.md)

## End-To-End Flow

### 1. Prepare Windows, WSL, Docker, and Git

Use the Windows-native workflow documented in [Apache Superset Setup](./local-runbook/01-apache-superset-setup.md#1-prerequisites-and-machine-checks). The key decision was to keep the repo on the Windows filesystem and run Docker Desktop with the WSL2 backend instead of attempting a native Python install.

### 2. Clone and Pin Superset

Clone the repo, fetch tags, and check out `6.0.0`. The exact commands and why that tag was chosen are documented in [Apache Superset Setup](./local-runbook/01-apache-superset-setup.md#4-clone-the-repo-and-pin-the-tag).

### 3. Add Only Local Overrides

Create these two local-only files and leave the rest of upstream Superset untouched:

- `C:\Users\hp\Documents\GitHub\Apache-Superset\superset\docker\.env-local`
- `C:\Users\hp\Documents\GitHub\Apache-Superset\superset\docker\requirements-local.txt`

The exact contents are in [Apache Superset Setup](./local-runbook/01-apache-superset-setup.md#5-local-files-created-or-modified) and [MSSQL Server + SQLBook Integration](./local-runbook/02-mssql-sqlbook.md#4-add-the-sql-server-driver-to-the-superset-container).

### 4. Start Superset and Create the Custom Login

Start with:

```powershell
cd C:\Users\hp\Documents\GitHub\Apache-Superset\superset
$env:TAG = '6.0.0'
docker compose -f docker-compose-image-tag.yml up -d
```

Then create `superset_local_admin` and rotate the default `admin` password. The exact commands and verification steps are in [Apache Superset Setup](./local-runbook/01-apache-superset-setup.md#7-create-the-custom-login-and-disable-adminadmin-as-the-user-login).

### 5. Expose SQL Server To Docker and Register `SQLBook`

The connection worked only after:

- enabling SQL Server TCP
- restarting the Windows SQL Server service
- verifying `localhost:1433`
- installing `pymssql` into the Superset container
- creating a SQL login that the container could use
- registering the database inside Superset with the command layer

The full runbook is in [MSSQL Server + SQLBook Integration](./local-runbook/02-mssql-sqlbook.md).

### 6. Create the Example Assets and the Detailed Survival Dashboard

Two levels of SQLBook content were created:

- a simple `dbo.Orders` example dashboard
- a more detailed survival-analysis dashboard backed by `dbo.Subscribers`

The automation file, virtual dataset SQL, chart design, layout choices, and rerun command are in [Detailed Dashboard Build](./local-runbook/03-survival-dashboard.md).

### 7. Validate the Whole Stack

Use the validation list in [Quick Rebuild Checklist and Minimal Path](./local-runbook/05-quick-rebuild-and-minimal-path.md#1-quick-rebuild-checklist). The important checks are:

- `http://localhost:8088/health` returns `OK`
- login works for `superset_local_admin`
- `admin/admin` fails
- `SQLBook` is visible in Superset
- `SELECT TOP 10 * FROM dbo.Orders` works in SQL Lab
- the survival dashboard opens and shows the saved charts

## Common Errors And Fixes

Go to [Common Errors and Fixes](./local-runbook/04-common-errors-and-fixes.md) for the exact issues that occurred on this machine, including:

- Docker named-pipe permission problems
- `git` dubious ownership
- SQL Server TCP disabled
- SQL Server virtual datasets failing because of trailing `ORDER BY`
- chart warmup failures caused by missing saved `query_context`

## Quick Rebuild Checklist

Use the concise checklist in [Quick Rebuild Checklist and Minimal Path](./local-runbook/05-quick-rebuild-and-minimal-path.md#1-quick-rebuild-checklist).

## Next Time Minimal Path

Use the shortest repeatable path in [Quick Rebuild Checklist and Minimal Path](./local-runbook/05-quick-rebuild-and-minimal-path.md#2-next-time-minimal-path).

## Final Summary

The exact working setup on this machine is:

- Superset `6.0.0` running from `docker-compose-image-tag.yml`
- local-only overrides in `docker/.env-local` and `docker/requirements-local.txt`
- custom admin `superset_local_admin`
- SQL Server database `SQLBook` connected through `host.docker.internal:1433`
- SQL driver `pymssql`
- a simple SQLBook orders dashboard plus a detailed survival-analysis dashboard

If you want the raw implementation evidence, keep [SETUP_REPORT.md](./SETUP_REPORT.md) beside this runbook. Use this doc set for reuse; use `SETUP_REPORT.md` for the exact historical command log.
