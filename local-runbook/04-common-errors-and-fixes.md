# Common Errors And Fixes

This file captures the issues that actually happened during setup on this machine, plus the shortest reliable fix for each one.

## 1. `git clone` Timed Out

### Symptom

- the tool session timed out during `git clone https://github.com/apache/superset`

### Actual Cause

- the clone was slow enough to hit the tool timeout, but the repository had still completed successfully on disk

### Fix

Check whether the repo is already usable before recloning:

```powershell
Test-Path C:\Users\hp\Documents\GitHub\Apache-Superset\superset
Get-ChildItem -Force C:\Users\hp\Documents\GitHub\Apache-Superset\superset\.git
```

## 2. Git Reported Dubious Ownership

### Symptom

- `git` commands complained that the repo owner did not match the active shell token

### Fix

```powershell
git -c safe.directory=C:/Users/hp/Documents/GitHub/Apache-Superset/superset -C C:\Users\hp\Documents\GitHub\Apache-Superset\superset status --short --branch
```

### Prevent It Next Time

- run the setup from your normal `hp` user session when possible

## 3. Docker Could Not Read `C:\Users\hp\.docker\config.json`

### Symptom

- Docker reported `Access is denied`

### Fix

```powershell
$env:DOCKER_CONFIG = Join-Path $env:TEMP 'codex-docker-config'
docker info
```

### Why This Happened

- the shell token was not the same profile context that Docker expected

## 4. Docker Named-Pipe Permission Errors

### Symptom

- `permission denied while trying to connect to the docker API at npipe:////./pipe/docker_engine`

### Fix

- use a normal interactive Windows session with the `hp` user when possible
- if the problem persists, start Docker Desktop and open a fresh PowerShell window
- verify the `docker-users` group membership if you are using multiple Windows accounts

Basic checks:

```powershell
docker --version
docker compose version
docker info
```

## 5. Superset `/health` Failed Right After Startup

### Symptom

- the first request returned a closed connection rather than `OK`

### Actual Cause

- the app container was still finishing first boot

### Fix

```powershell
cd C:\Users\hp\Documents\GitHub\Apache-Superset\superset
$env:TAG = '6.0.0'
docker compose -f docker-compose-image-tag.yml logs --tail 200 superset
Invoke-WebRequest -Uri 'http://localhost:8088/health' -UseBasicParsing
```

## 6. SQL Server Was Not Listening On `1433`

### Symptom

- the container could not reach `host.docker.internal:1433`
- `Test-NetConnection localhost -Port 1433` failed

### Actual Cause

- SQL Server TCP was disabled

### Fix

```powershell
sqlcmd -S . -E -C -Q "EXEC xp_instance_regwrite N'HKEY_LOCAL_MACHINE', N'SOFTWARE\Microsoft\Microsoft SQL Server\MSSQLServer\SuperSocketNetLib\Tcp', N'Enabled', REG_DWORD, 1;"
Restart-Service MSSQLSERVER -Force
Test-NetConnection localhost -Port 1433
```

## 7. `sqlcmd` Connection Attempts Timed Out Or Hit Encryption Friction

### Symptom

- several early `sqlcmd` connection attempts failed or timed out

### Practical Fix

- prefer the local instance shortcut `-S .`
- keep `-E -C` when using trusted local Windows auth during setup
- verify the listener with `Test-NetConnection` before debugging login details

Useful checks:

```powershell
sqlcmd -S . -E -C -Q "SELECT @@SERVERNAME, @@SERVICENAME"
Test-NetConnection localhost -Port 1433
```

## 8. Superset Database Creation Through REST Hit CSRF Problems

### Symptom

- the REST call to create the SQLBook database failed even after getting a bearer token

### Actual Cause

- Superset 6.0.0 write endpoints required a session-backed CSRF flow that was awkward for this automation

### Fix

- use `superset shell` and `CreateDatabaseCommand` instead of trying to brute-force the REST path

## 9. SQL Server Virtual Datasets Failed Because Of Trailing `ORDER BY`

### Symptom

- the survival-analysis dashboard helper failed on some virtual datasets

### Actual Cause

- Superset wraps the virtual dataset SQL in an outer query
- SQL Server rejects a plain trailing `ORDER BY` in that nested shape

### Fix

- remove the trailing `ORDER BY` from the virtual dataset SQL
- order the chart or table at the visualization layer instead

## 10. Saved Charts Existed But Did Not Warm Correctly

### Symptom

- the charts were saved but some validation paths still failed

### Actual Cause

- the saved `query_context` payload was missing for some non-legacy charts

### Fix

- explicitly save the `query_context` when automating chart creation
- warm the chart cache after that

## 11. The UI Menu Said `Database Connections`, Not `Databases`

### Symptom

- trying to follow `Data -> Databases -> SQLBook` was confusing on this build

### Fix

Use:

- `Data -> Database Connections`
- or go directly to `http://localhost:8088/databaseview/list/`

## 12. The Survival Dashboard Did Not Appear In Navigation Immediately

### Symptom

- the dashboard existed but was not obvious from the left nav

### Fix

Open it directly:

- `http://localhost:8088/superset/dashboard/sqlbook-customer-survival-analysis/`

Then refresh once after login.

## 13. High-Value Checks To Run Before Panicking

```powershell
cd C:\Users\hp\Documents\GitHub\Apache-Superset\superset
$env:TAG = '6.0.0'
docker compose -f docker-compose-image-tag.yml ps
docker compose -f docker-compose-image-tag.yml logs --tail 150 superset
Invoke-WebRequest -Uri 'http://localhost:8088/health' -UseBasicParsing
Test-NetConnection localhost -Port 1433
docker compose -f docker-compose-image-tag.yml exec -T superset python -c "import pymssql; print(pymssql.__version__)"
```
