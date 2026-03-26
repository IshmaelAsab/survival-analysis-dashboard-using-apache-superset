# Apache Superset Setup

## 1. Prerequisites And Machine Checks

### What Was Chosen

`Actual`: the setup used the official Docker Compose image-tag workflow instead of a manual Python install.

### Why This Was Chosen

- Docker Compose is the official quickstart path for local Superset.
- Python was not installed on this machine when the work started.
- Docker keeps the setup reproducible and isolated.
- Local-only overrides can be kept out of git.

### What To Watch Next Time

- Superset's Docker quickstart is convenient, but Windows is still a little less frictionless than Linux.
- If you run commands from a sandboxed or alternate Windows user token, Docker named-pipe access can fail even if Docker Desktop itself is healthy.
- Keep the repo on the Windows filesystem unless you have a specific reason to move it into WSL.

### Actual Machine Check Commands

```powershell
Get-Location
Get-ChildItem -Force
git --version
$PSVersionTable.PSVersion.ToString()
[System.Environment]::OSVersion.VersionString
node --version
cmd /c npm --version
py -0p
where.exe python
wsl --version
wsl --status
```

### Actual Results

- Git existed: `git version 2.52.0.windows.1`
- Windows version: `10.0.19045.6466`
- PowerShell version: `5.1.19041.6456`
- Node existed: `v24.11.1`
- npm existed: `11.6.2`
- Python was not installed
- WSL was already installed:
  - WSL version `2.6.3.0`
  - default distro `Ubuntu`
  - default version `2`

## 2. WSL And Windows Interoperability

### Actual State

`Actual`: WSL was already present and no Linux shell session was required for the successful setup. Docker Desktop used the WSL2 backend under the hood, but all successful operational commands were run from Windows PowerShell.

### Actual WSL Check Commands

```powershell
wsl --version
wsl --status
```

### Reusable WSL Setup If A Future Machine Does Not Already Have It

`Assumption`: this was not required on this machine because WSL was already installed.

```powershell
wsl --install -d Ubuntu
wsl --set-default-version 2
Restart-Computer
wsl --version
wsl --status
```

### Optional Linux-Shell Checks Inside WSL

`Assumption`: these are useful if Docker Desktop reports WSL problems later.

```powershell
wsl -d Ubuntu -- uname -a
wsl -d Ubuntu -- bash -lc "cat /etc/os-release"
wsl -d Ubuntu -- bash -lc "ls /mnt/c/Users/hp/Documents/GitHub/Apache-Superset"
```

### Why The Repo Stayed On The Windows Filesystem

- Docker Desktop on Windows can mount the Windows path directly.
- The rest of the workflow already depended on Windows-native tools such as `sqlcmd`, `Test-NetConnection`, and service management.
- Keeping the repo at `C:\Users\hp\Documents\GitHub\Apache-Superset\superset` avoided splitting the setup across Windows and Linux home directories.

## 3. Install Docker Desktop

### Actual Install Command

`Actual`: Docker Desktop was not installed, so it was installed with the WSL2 backend.

```powershell
$installer = Join-Path $env:TEMP 'Docker Desktop Installer.exe'
Invoke-WebRequest -Uri 'https://desktop.docker.com/win/main/amd64/Docker%20Desktop%20Installer.exe' -OutFile $installer
Start-Process -FilePath $installer -Wait -ArgumentList 'install','--accept-license','--backend=wsl-2','--always-run-service'
```

### Actual Docker Verification Commands

```powershell
docker --version
docker compose version
Get-Service -Name com.docker.service -ErrorAction SilentlyContinue | Select-Object Name,Status,StartType
```

### Actual Results

- Docker version: `29.3.0`
- Docker Compose version: `v5.1.0`
- Windows service: `com.docker.service` running with automatic start

### Important Windows-Specific Note

`Actual`: the Codex shell did not have clean named-pipe access to Docker, so successful Docker commands used a writable Docker config path:

```powershell
$env:DOCKER_CONFIG = Join-Path $env:TEMP 'codex-docker-config'
```

### What To Watch Next Time

- On a normal interactive `hp` desktop session, you may not need the `DOCKER_CONFIG` workaround.
- If `docker info` reports `Access is denied` on `C:\Users\hp\.docker\config.json`, set `DOCKER_CONFIG` to a writable temp directory first.

## 4. Clone The Repo And Pin The Tag

### Why `6.0.0` Was Chosen

`Actual`: the repo was pinned to `6.0.0` because that was the official quickstart tag referenced by the Superset docs at the time of setup.

### Actual Commands

```powershell
cd C:\Users\hp\Documents\GitHub\Apache-Superset
git clone https://github.com/apache/superset
cd .\superset
git fetch --tags
git checkout 6.0.0
```

### Actual Repo Path

`C:\Users\hp\Documents\GitHub\Apache-Superset\superset`

### Watch For This Next Time

`Actual`: `git` initially complained about dubious ownership because the repo owner was `hp` while the automation shell token was different.

Reusable safe form:

```powershell
git -c safe.directory=C:/Users/hp/Documents/GitHub/Apache-Superset/superset -C .\superset status --short --branch
```

If you are using your normal `hp` session directly, you may never see this.

## 5. Local Files Created Or Modified

### File: `C:\Users\hp\Documents\GitHub\Apache-Superset\superset\docker\.env-local`

Purpose:

- keep local-only Superset overrides out of git
- load the bundled example dashboards
- set a local secret key so sessions survive restart
- make logs readable

Exact contents:

```dotenv
# Keep the built-in examples enabled so the UI has something to verify immediately.
SUPERSET_LOAD_EXAMPLES=yes

# Use a local-only secret key so sessions survive restarts without relying on the checked-in test key.
SUPERSET_SECRET_KEY=XT[m!Yg&#nD!P6=kR6zX_XEi4LHTW_H@fTYL9f[B%U#5C5}s

# Keep container logs readable for local troubleshooting.
SUPERSET_LOG_LEVEL=info
```

### File: `C:\Users\hp\Documents\GitHub\Apache-Superset\superset\docker\requirements-local.txt`

Purpose:

- add `pymssql` into the Superset container image for SQL Server connectivity

Exact contents:

```text
# Local-only SQL Server driver so the Dockerized Superset app can connect to SQLBook.
pymssql
```

### File: `C:\Users\hp\Documents\GitHub\Apache-Superset\superset\SETUP_REPORT.md`

Purpose:

- preserve the full historical command log, issues, fixes, verification results, and runtime URLs

Relevant note:

- this file was required by the earlier setup task and intentionally remains in the repo root

## 6. Start Superset

### Actual Start Command

```powershell
cd C:\Users\hp\Documents\GitHub\Apache-Superset\superset
$env:TAG = '6.0.0'
docker compose -f docker-compose-image-tag.yml up -d
```

### Why This Compose File Was Used

- it matches the official image-tag quickstart path
- it keeps the startup process simple
- it did not require switching to the fallback non-dev compose file on this machine

### Actual Health Check

```powershell
Invoke-WebRequest -Uri 'http://localhost:8088/health' -UseBasicParsing -TimeoutSec 20
```

Expected success:

```text
OK
```

### If `/health` Fails Immediately

`Actual`: that happened once because the app was still booting. Wait and retry:

```powershell
docker compose -f docker-compose-image-tag.yml logs --tail 200 superset
Invoke-WebRequest -Uri 'http://localhost:8088/health' -UseBasicParsing -TimeoutSec 20
```

## 7. Create The Custom Login And Disable `admin/admin` As The User Login

### Why A Custom Login Was Used

- the requirement was to replace the default `admin/admin`
- the custom login is explicit, memorable, and reproducible
- it avoids leaving the instance in the default demo state

### Actual Credentials Created

- Username: `superset_local_admin`
- Password: `piCCh4Q(QeWQ%_Rai}CBU%Xe`
- Email: `superset_local_admin@example.local`
- First name: `Local`
- Last name: `Admin`

### Actual Commands

```powershell
cd C:\Users\hp\Documents\GitHub\Apache-Superset\superset
$env:TAG = '6.0.0'
docker compose -f docker-compose-image-tag.yml exec -T superset superset fab create-admin --username superset_local_admin --firstname Local --lastname Admin --email superset_local_admin@example.local --password "piCCh4Q(QeWQ%_Rai}CBU%Xe"
docker compose -f docker-compose-image-tag.yml exec -T superset superset fab reset-password --username admin --password "YN5fH9DN)SM6a6$m=%(%bSJM"
docker compose -f docker-compose-image-tag.yml exec -T superset superset fab list-users
```

### Why The Original `admin` User Was Not Deleted

- the quickstart flow expects an admin account to exist
- resetting the password was the smallest safe change
- the user-facing account is `superset_local_admin`

## 8. Verify Login And Example Content

### Verify Health

```powershell
Invoke-WebRequest -Uri 'http://localhost:8088/health' -UseBasicParsing
```

### Verify The Custom Login Through The API

```powershell
$body = @{
  username = 'superset_local_admin'
  password = 'piCCh4Q(QeWQ%_Rai}CBU%Xe'
  provider = 'db'
  refresh  = $true
} | ConvertTo-Json

Invoke-RestMethod -Uri 'http://localhost:8088/api/v1/security/login' -Method Post -ContentType 'application/json' -Body $body
```

### Verify `admin/admin` No Longer Works

```powershell
$body = @{
  username = 'admin'
  password = 'admin'
  provider = 'db'
  refresh  = $true
} | ConvertTo-Json

Invoke-WebRequest -Uri 'http://localhost:8088/api/v1/security/login' -Method Post -ContentType 'application/json' -Body $body
```

Expected result:

- HTTP `401`

### Built-In Example Content

`Actual`: the Docker init flow loaded Superset's built-in examples because `SUPERSET_LOAD_EXAMPLES=yes` was set.

Reusable quick check:

- Open `http://localhost:8088/superset/dashboard/8/`
- Expected dashboard: `Featured Charts`

## 9. Start, Stop, And Restart Commands

### Start

```powershell
cd C:\Users\hp\Documents\GitHub\Apache-Superset\superset
$env:TAG = '6.0.0'
docker compose -f docker-compose-image-tag.yml up -d
```

### Stop

```powershell
cd C:\Users\hp\Documents\GitHub\Apache-Superset\superset
$env:TAG = '6.0.0'
docker compose -f docker-compose-image-tag.yml down
```

### Restart

```powershell
cd C:\Users\hp\Documents\GitHub\Apache-Superset\superset
$env:TAG = '6.0.0'
docker compose -f docker-compose-image-tag.yml down
docker compose -f docker-compose-image-tag.yml up -d
```

## 10. What To Watch For Next Time

- Use the same tag unless the official quickstart docs move again.
- Keep `docker/.env-local` and `docker/requirements-local.txt` as the only local config overrides unless there is a compelling reason to add more.
- If you rebuild the stack and the SQL Server connection disappears, recreate the container after confirming `pymssql` is still listed in `docker/requirements-local.txt`.
- If you need the SQL Server and dashboard details, continue with:
  - [MSSQL Server + SQLBook Integration](./02-mssql-sqlbook.md)
  - [Detailed Dashboard Build](./03-survival-dashboard.md)
