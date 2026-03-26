# MSSQL Server + SQLBook Integration

## 1. What Already Existed And What Was Added

### Already Existed

`Actual`:

- a local Windows SQL Server instance named `MSSQLSERVER`
- a sample database named `SQLBook`
- sample SQLBook tables, including:
  - `dbo.Calendar`
  - `dbo.Campaigns`
  - `dbo.Customers`
  - `dbo.OrderLines`
  - `dbo.Orders`
  - `dbo.Products`
  - `dbo.Subscribers`

### Added During This Setup

`Actual`:

- TCP/IP connectivity for the Windows SQL Server listener
- a SQL login for Superset:
  - username `superset_sqlbook`
  - password `wuRXUYcH8AoSrBf3MmBqDp5N`
- the `pymssql` Python driver inside the Superset container
- a registered Superset database connection named `SQLBook`
- a basic `dbo.Orders` dataset, charts, and dashboard inside Superset

### Why This Approach Was Chosen

- Superset was running in Docker, not directly on Windows.
- Windows integrated authentication from inside the Linux container would have been more complicated.
- A dedicated SQL login plus `host.docker.internal:1433` was the simplest reproducible path.

## 2. Check SQL Server And The Target Database

### Reusable Checks

Use these from Windows PowerShell:

```powershell
sqlcmd -S . -E -C -Q "SELECT @@SERVERNAME AS ServerName, @@SERVICENAME AS ServiceName"
sqlcmd -S . -E -C -Q "SELECT name FROM sys.databases ORDER BY name"
sqlcmd -S . -E -C -d SQLBook -Q "SELECT TOP 10 TABLE_SCHEMA, TABLE_NAME FROM INFORMATION_SCHEMA.TABLES ORDER BY TABLE_SCHEMA, TABLE_NAME"
sqlcmd -S . -E -C -d SQLBook -Q "SELECT TOP 5 * FROM dbo.Orders"
```

### What Was Confirmed On This Machine

- the SQL Server service name was `MSSQLSERVER`
- `SQLBook` existed
- the sample tables were already populated
- `SQLBook` did not need to be restored or created during this run

### Important Note About The SQLBook Sample Database

`Actual`: the setup did not load or create `SQLBook`. It reused an already present local database.

`Assumption`: if you repeat this on a different laptop and `SQLBook` does not exist, you will need to restore it from a `.bak` file or run the sample SQL from your own copy of the SQL Book materials before continuing.

## 3. Enable SQL Server Connectivity From The Dockerized Superset App

### Why This Was Needed

- the Superset app ran inside a Linux container
- the SQL Server instance ran directly on Windows
- the container needed a stable TCP endpoint it could reach

### Actual Check That Exposed The Problem

`Actual`: early container-to-host connection attempts failed because SQL Server TCP was disabled.

### Actual Commands Used To Inspect TCP State

```powershell
sqlcmd -S . -E -C -Q "EXEC xp_instance_regread N'HKEY_LOCAL_MACHINE', N'SOFTWARE\Microsoft\Microsoft SQL Server\MSSQLServer\SuperSocketNetLib\Tcp', N'Enabled';"
Test-NetConnection localhost -Port 1433
```

### Actual Commands Used To Turn TCP On

`Actual`: the registry-backed SQL Server setting was enabled through `xp_instance_regwrite`.

```powershell
sqlcmd -S . -E -C -Q "EXEC xp_instance_regwrite N'HKEY_LOCAL_MACHINE', N'SOFTWARE\Microsoft\Microsoft SQL Server\MSSQLServer\SuperSocketNetLib\Tcp', N'Enabled', REG_DWORD, 1;"
```

### Required Manual Step

`Actual`: the SQL Server service restart had to be performed manually outside the automation sandbox.

Reusable admin PowerShell command:

```powershell
Restart-Service MSSQLSERVER -Force
```

### Final Verification

```powershell
Test-NetConnection localhost -Port 1433
```

Expected result:

```text
TcpTestSucceeded : True
```

### What To Watch Next Time

- If `host.docker.internal:1433` fails from the container, check the Windows listener first.
- SQL Server Configuration Manager is a more normal UI path than registry writes if you are doing this interactively.
- If TCP is on but the port is not `1433`, either fix the SQL Server listener or update the Superset connection string.

## 4. Add The SQL Server Driver To The Superset Container

### File: `C:\Users\hp\Documents\GitHub\Apache-Superset\superset\docker\requirements-local.txt`

Purpose:

- install a local-only SQL Server driver without editing core project dependency files

Exact contents:

```text
# Local-only SQL Server driver so the Dockerized Superset app can connect to SQLBook.
pymssql
```

### Why `pymssql` Was Chosen

- it worked cleanly with Superset's SQLAlchemy URI on this machine
- it was a small local-only addition
- it avoided the extra ODBC system-driver work that `pyodbc` would have needed inside the container

### Rebuild The Superset Container After Adding The Driver

```powershell
cd C:\Users\hp\Documents\GitHub\Apache-Superset\superset
$env:TAG = '6.0.0'
docker compose -f docker-compose-image-tag.yml up -d --force-recreate
```

### Verify The Driver Inside The Container

```powershell
cd C:\Users\hp\Documents\GitHub\Apache-Superset\superset
$env:TAG = '6.0.0'
docker compose -f docker-compose-image-tag.yml exec -T superset python -c "import pymssql; print(pymssql.__version__)"
```

Expected result on this machine:

- `2.3.13`

## 5. Create The SQL Login And Database User

### Why A SQL Login Was Created

- the container could not rely on Windows integrated authentication
- Superset needed a stable username/password-based connection
- the login could be granted only the minimum needed read access

### Reusable SQL Script

This is the reusable version of the SQL that was executed during setup. The original run used the same operations in a more compact one-liner.

```sql
USE [master];
GO

IF NOT EXISTS (SELECT 1 FROM sys.sql_logins WHERE name = 'superset_sqlbook')
    CREATE LOGIN [superset_sqlbook] WITH PASSWORD = 'wuRXUYcH8AoSrBf3MmBqDp5N', CHECK_POLICY = ON;
ELSE
    ALTER LOGIN [superset_sqlbook] WITH PASSWORD = 'wuRXUYcH8AoSrBf3MmBqDp5N';
GO

USE [SQLBook];
GO

IF NOT EXISTS (SELECT 1 FROM sys.database_principals WHERE name = 'superset_sqlbook')
    CREATE USER [superset_sqlbook] FOR LOGIN [superset_sqlbook];
GO

ALTER ROLE [db_datareader] ADD MEMBER [superset_sqlbook];
GRANT VIEW DEFINITION TO [superset_sqlbook];
GO
```

### PowerShell Command To Run It

```powershell
sqlcmd -S . -E -C -d SQLBook -Q "IF NOT EXISTS (SELECT 1 FROM sys.sql_logins WHERE name = 'superset_sqlbook') BEGIN CREATE LOGIN [superset_sqlbook] WITH PASSWORD = 'wuRXUYcH8AoSrBf3MmBqDp5N', CHECK_POLICY = ON; END ELSE BEGIN ALTER LOGIN [superset_sqlbook] WITH PASSWORD = 'wuRXUYcH8AoSrBf3MmBqDp5N'; END; IF NOT EXISTS (SELECT 1 FROM sys.database_principals WHERE name = 'superset_sqlbook') BEGIN CREATE USER [superset_sqlbook] FOR LOGIN [superset_sqlbook]; END; ALTER ROLE [db_datareader] ADD MEMBER [superset_sqlbook]; GRANT VIEW DEFINITION TO [superset_sqlbook];"
```

### What To Watch Next Time

- if the `ALTER ROLE` line errors because the member already exists, remove and recreate the user or wrap the membership step in a guard condition
- the password is now documented locally, so rotate it if this laptop becomes shared

## 6. Verify Container-To-Host SQL Connectivity

### Why `host.docker.internal` Was Used

- it is the cleanest Docker Desktop hostname for reaching the Windows host from a Linux container
- it avoids hard-coding the host's local IP

### Working Connection String

```text
mssql+pymssql://superset_sqlbook:wuRXUYcH8AoSrBf3MmBqDp5N@host.docker.internal:1433/SQLBook
```

### Reusable Connectivity Probe From The Container

```powershell
cd C:\Users\hp\Documents\GitHub\Apache-Superset\superset
$env:TAG = '6.0.0'
docker compose -f docker-compose-image-tag.yml exec -T superset python -c "import pymssql; conn = pymssql.connect(server='host.docker.internal', port=1433, user='superset_sqlbook', password='wuRXUYcH8AoSrBf3MmBqDp5N', database='SQLBook'); cur = conn.cursor(); cur.execute('SELECT COUNT(*) FROM dbo.Orders'); print(cur.fetchone()[0]); conn.close()"
```

Expected success on this machine:

- `192983`

## 7. Register The Database Inside Superset

### Why The Command Layer Was Used

`Actual`: direct REST creation ran into CSRF/session friction during automation. The command layer inside `superset shell` was more reliable.

### Reusable Python Snippet

This is a reusable version of the approach used during setup.

```python
from superset import app
from superset.commands.database.create import CreateDatabaseCommand

payload = {
    "database_name": "SQLBook",
    "sqlalchemy_uri": "mssql+pymssql://superset_sqlbook:wuRXUYcH8AoSrBf3MmBqDp5N@host.docker.internal:1433/SQLBook",
    "expose_in_sqllab": True,
    "allow_ctas": False,
    "allow_cvas": False,
    "allow_dml": False,
    "extra": "{}",
    "encrypted_extra": "{}",
}

with app.app_context():
    db = CreateDatabaseCommand(payload).run()
    print(db.id, db.database_name)
```

### Reusable Command To Run That Snippet

Save the snippet to a temporary file or paste it into:

```powershell
docker compose -f docker-compose-image-tag.yml exec -T superset superset shell
```

### Actual Outcome On This Machine

- Superset database name: `SQLBook`
- Superset database ID: `2`
- Backend detected by Superset: `mssql`
- Exposed in SQL Lab: yes

## 8. Validate `SQLBook` In Superset

### Basic SQL Lab Validation

- open `http://localhost:8088/sqllab/`
- choose database `SQLBook`
- run:

```sql
SELECT TOP 10 * FROM dbo.Orders;
```

### Count Validation

```sql
SELECT COUNT(*) AS OrderCount
FROM dbo.Orders;
```

Expected result on this machine:

- `192983`

### API-Level Validation

`Actual`: the Superset database API returned `9` tables under schema `dbo`.

### Menu And Route Note

`Actual`: on this tag, the left-nav wording was `Data -> Database Connections`, not `Data -> Databases`.

Direct route:

- `http://localhost:8088/databaseview/list/`

## 9. SQLBook Sample Assets Created Inside Superset

### Dataset

- `dbo.Orders` on database `SQLBook`
- dataset ID `26`

### Charts

- `SQLBook Orders Count` with chart ID `274`
- `SQLBook Sales by Payment Type` with chart ID `275`

### Dashboard

- title `SQLBook Orders Overview`
- dashboard ID `13`
- URL `http://localhost:8088/superset/dashboard/sqlbook-orders-overview/`

## 10. What To Watch Next Time

- if SQL Server is reachable from Windows but not from the container, test `host.docker.internal:1433` from inside the container
- if the database creation API rejects your request, fall back to `superset shell` and the command layer
- if the connection exists but tables are missing, verify the SQL login still has `db_datareader` and `VIEW DEFINITION`
- if you want to rebuild the advanced customer-lifetime dashboard, continue with [Detailed Dashboard Build](./03-survival-dashboard.md)
