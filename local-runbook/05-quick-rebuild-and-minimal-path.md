# Quick Rebuild Checklist And Minimal Path

## 1. Quick Rebuild Checklist

Use this when the repo already exists and you want to get back to the exact working setup quickly.

### A. Confirm The Repo And Tag

```powershell
cd C:\Users\hp\Documents\GitHub\Apache-Superset\superset
git -c safe.directory=C:/Users/hp/Documents/GitHub/Apache-Superset/superset rev-parse --short HEAD
git -c safe.directory=C:/Users/hp/Documents/GitHub/Apache-Superset/superset describe --tags --exact-match
```

Expected tag:

- `6.0.0`

### B. Confirm The Local Override Files Exist

```powershell
Test-Path .\docker\.env-local
Test-Path .\docker\requirements-local.txt
Get-Content .\docker\.env-local
Get-Content .\docker\requirements-local.txt
```

### C. Start Docker Desktop If Needed

Check:

```powershell
docker --version
docker compose version
docker info
```

If Docker complains about config access:

```powershell
$env:DOCKER_CONFIG = Join-Path $env:TEMP 'codex-docker-config'
docker info
```

### D. Start Superset

```powershell
cd C:\Users\hp\Documents\GitHub\Apache-Superset\superset
$env:TAG = '6.0.0'
docker compose -f docker-compose-image-tag.yml up -d
```

### E. Verify Superset

```powershell
Invoke-WebRequest -Uri 'http://localhost:8088/health' -UseBasicParsing
```

Expected:

- response body `OK`

### F. Verify Login

```powershell
$body = @{
  username = 'superset_local_admin'
  password = 'piCCh4Q(QeWQ%_Rai}CBU%Xe'
  provider = 'db'
  refresh  = $true
} | ConvertTo-Json

Invoke-RestMethod -Uri 'http://localhost:8088/api/v1/security/login' -Method Post -ContentType 'application/json' -Body $body
```

### G. Verify SQL Server Reachability

```powershell
Test-NetConnection localhost -Port 1433
```

Expected:

- `TcpTestSucceeded : True`

### H. Verify SQLBook In SQL Lab

- open `http://localhost:8088/sqllab/`
- choose `SQLBook`
- run:

```sql
SELECT TOP 10 * FROM dbo.Orders;
```

### I. Verify The Survival Dashboard

Open:

- `http://localhost:8088/superset/dashboard/sqlbook-customer-survival-analysis/`

Expected headline values on this machine:

- `365-Day Survival`: about `72.09%`
- `Customer Half-Life (Days)`: `569`
- `Avg Active Days in Year 1`: about `304.57`

### J. Re-Run The Dashboard Helper If Any SQLBook Survival Assets Are Missing

```powershell
cd C:\Users\hp\Documents\GitHub\Apache-Superset\superset
$env:DOCKER_CONFIG = Join-Path $env:TEMP 'codex-docker-config'
& 'C:\Program Files\Docker\Docker\resources\bin\docker.exe' cp 'C:\Users\hp\Documents\GitHub\Apache-Superset\superset\tmp_sqlbook_survival_dashboard.py' superset_app:/tmp/sqlbook_survival_dashboard.py
& 'C:\Program Files\Docker\Docker\resources\bin\docker.exe' exec -e SUPERSET_BASE_URL=http://127.0.0.1:8088 -e SUPERSET_USERNAME=superset_local_admin -e SUPERSET_PASSWORD='piCCh4Q(QeWQ%_Rai}CBU%Xe' superset_app python /tmp/sqlbook_survival_dashboard.py
```

## 2. Next Time Minimal Path

If everything has already been installed once on this laptop, these are the essential steps only.

1. Start Docker Desktop.
2. Open PowerShell.
3. Run:

```powershell
cd C:\Users\hp\Documents\GitHub\Apache-Superset\superset
$env:TAG = '6.0.0'
docker compose -f docker-compose-image-tag.yml up -d
```

4. Wait for:

```powershell
Invoke-WebRequest -Uri 'http://localhost:8088/health' -UseBasicParsing
```

5. Log in at:

- `http://localhost:8088/login/`

With:

- username `superset_local_admin`
- password `piCCh4Q(QeWQ%_Rai}CBU%Xe`

6. Check `SQLBook` in SQL Lab:

```sql
SELECT TOP 10 * FROM dbo.Orders;
```

7. Open the detailed dashboard:

- `http://localhost:8088/superset/dashboard/sqlbook-customer-survival-analysis/`

8. If the dashboard content is missing, rerun the helper from step `1.J`.

## 3. Final Summary Of The Exact Working Setup Used On This Machine

### Versions

- Windows: `10.0.19045.6466`
- PowerShell: `5.1.19041.6456`
- WSL: `2.6.3.0`
- Docker Desktop: `29.3.0`
- Docker Compose: `v5.1.0`
- Superset tag: `6.0.0`

### Repo And File Paths

- repo root: `C:\Users\hp\Documents\GitHub\Apache-Superset\superset`
- local Superset config: `C:\Users\hp\Documents\GitHub\Apache-Superset\superset\docker\.env-local`
- local SQL driver list: `C:\Users\hp\Documents\GitHub\Apache-Superset\superset\docker\requirements-local.txt`
- raw historical log: `C:\Users\hp\Documents\GitHub\Apache-Superset\superset\SETUP_REPORT.md`
- dashboard helper: `C:\Users\hp\Documents\GitHub\Apache-Superset\superset\tmp_sqlbook_survival_dashboard.py`

### Running Services

- Superset at `http://localhost:8088/`
- SQL Server on Windows at `localhost:1433`

### Credentials

- Superset user: `superset_local_admin`
- Superset password: `piCCh4Q(QeWQ%_Rai}CBU%Xe`
- SQL login: `superset_sqlbook`
- SQL password: `wuRXUYcH8AoSrBf3MmBqDp5N`

### Superset Database Registration

- database name: `SQLBook`
- Superset database ID: `2`
- SQLAlchemy URI: `mssql+pymssql://superset_sqlbook:wuRXUYcH8AoSrBf3MmBqDp5N@host.docker.internal:1433/SQLBook`

### Superset Assets

- built-in baseline example: `http://localhost:8088/superset/dashboard/8/`
- SQLBook demo dashboard: `http://localhost:8088/superset/dashboard/sqlbook-orders-overview/`
- detailed survival dashboard: `http://localhost:8088/superset/dashboard/sqlbook-customer-survival-analysis/`

### Validated KPI Values For The Survival Dashboard

- 365-day survival: `0.720920670453709`
- half-life: `569`
- average active days in year 1: `304.56824409567`

### Safe Start And Stop Commands

Start:

```powershell
cd C:\Users\hp\Documents\GitHub\Apache-Superset\superset
$env:TAG = '6.0.0'
docker compose -f docker-compose-image-tag.yml up -d
```

Stop:

```powershell
cd C:\Users\hp\Documents\GitHub\Apache-Superset\superset
$env:TAG = '6.0.0'
docker compose -f docker-compose-image-tag.yml down
```
