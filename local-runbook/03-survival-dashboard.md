# Detailed Dashboard Build

## 1. Purpose And Source Material

This section documents how the detailed SQLBook dashboard was created for the question:

> How long will customers last?

### Source Material Used

`Actual`:

- `C:\Users\hp\Downloads\06 How Long Will Customers Last_ Survival Analysis to Understand Customers and Their Value.mhtml`

### Why The Dashboard Was Automated

`Actual`: a Python helper script was used instead of clicking through the UI manually.

Reasons:

- the dashboard used 5 virtual datasets and 10 saved charts
- the setup needed to be reproducible
- the chart and layout JSON were easier to keep consistent in code
- it was easier to validate by warming every saved chart programmatically

## 2. File Created For The Dashboard

### File: `C:\Users\hp\Documents\GitHub\Apache-Superset\superset\tmp_sqlbook_survival_dashboard.py`

Purpose:

- authenticate to the running Superset instance
- create or update the SQLBook virtual datasets
- create or update the saved charts
- assemble the dashboard layout
- backfill missing `query_context` blobs for the saved charts
- warm the chart cache to prove the dashboard really renders

### Environment Variables Expected By The Helper

```text
SUPERSET_BASE_URL
SUPERSET_USERNAME
SUPERSET_PASSWORD
```

### Relevant Authentication Snippet

```python
BASE_URL = os.environ.get("SUPERSET_BASE_URL", "http://127.0.0.1:8088").rstrip("/")
USERNAME = os.environ["SUPERSET_USERNAME"]
PASSWORD = os.environ["SUPERSET_PASSWORD"]
DATABASE_ID = 2
OWNER_ID = 2
DASHBOARD_TITLE = "How Long Will Customers Last? SQLBook Survival Analysis"
DASHBOARD_SLUG = "sqlbook-customer-survival-analysis"
```

### Local-Only Git Ignore Rule

File:

- `C:\Users\hp\Documents\GitHub\Apache-Superset\superset\.git\info\exclude`

Relevant snippet:

```text
tmp_sqlbook_*.py
```

Why:

- keep the helper reusable on this machine
- avoid checking a one-off local automation helper into upstream Superset

## 3. Source Table And Actual Schema

### Source Table

- `SQLBook.dbo.Subscribers`

### Actual Schema Confirmed During Setup

```text
SubscriberId int
RatePlan varchar
MonthlyFee float
Market varchar
Channel varchar
StartDate date
StopDate date
StopType char
Tenure int
IsActive int
```

## 4. Analysis Rules Used

### Core Cohort Filter

```sql
StartDate >= '2004-01-01'
AND Tenure >= 0
```

### Smallville Left Truncation

```sql
CASE
  WHEN Market = 'Smallville' THEN CAST('2004-10-27' AS date)
  ELSE CAST('2004-01-01' AS date)
END
```

### Why These Rules Were Used

- they match the logic in the source material
- they prevent mixing incomparable observation windows
- they let the market-level survival comparisons stay faithful to the original analysis

## 5. Virtual Datasets Created In Superset

All five datasets were created on the `SQLBook` database connection.

### Dataset 1: `sqlbook_customer_survival_cohort`

Dataset ID on this machine: `27`

SQL:

```sql
SELECT
  SubscriberId,
  RatePlan,
  MonthlyFee,
  Market,
  Channel,
  StartDate,
  StopDate,
  StopType,
  COALESCE(CAST(StopType AS varchar(10)), 'Active') AS StopTypeLabel,
  Tenure,
  IsActive
FROM dbo.Subscribers
WHERE StartDate >= '2004-01-01'
  AND Tenure >= 0
```

Use:

- histogram of tenure by market
- stop-type mix
- box plot of tenure spread by market

### Dataset 2: `sqlbook_customer_survival_kpis`

Dataset ID on this machine: `28`

SQL:

```sql
WITH base AS (
  SELECT
    Tenure,
    is_stop = CASE WHEN StopType IS NULL THEN 0.0 ELSE 1.0 END,
    is_active = CASE WHEN StopType IS NULL THEN 1.0 ELSE 0.0 END
  FROM dbo.Subscribers
  WHERE StartDate >= '2004-01-01'
    AND Tenure >= 0
),
h AS (
  SELECT
    Tenure,
    next_tenure = LEAD(Tenure) OVER (ORDER BY Tenure),
    hazard = SUM(is_stop) / SUM(COUNT(*)) OVER (ORDER BY Tenure DESC)
  FROM base
  GROUP BY Tenure
),
s AS (
  SELECT
    Tenure,
    next_tenure,
    survival = COALESCE(
      EXP(
        SUM(LOG(NULLIF(1 - hazard, 0))) OVER (
          ORDER BY Tenure
          ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING
        )
      ),
      1.0
    )
  FROM h
)
SELECT
  cohort_size = (SELECT COUNT(*) FROM base),
  active_rate = (SELECT AVG(is_active) FROM base),
  survival_365 = (SELECT MAX(CASE WHEN Tenure = 365 THEN survival END) FROM s),
  half_life_days = (SELECT MIN(Tenure) FROM s WHERE survival <= 0.5),
  avg_days_first_year = (
    SELECT SUM(
      survival *
      CASE
        WHEN COALESCE(next_tenure, 365) > 365 THEN 365 - Tenure
        ELSE COALESCE(next_tenure, 365) - Tenure
      END
    )
    FROM s
    WHERE Tenure BETWEEN 0 AND 365
      AND COALESCE(next_tenure, 365) > Tenure
  )
```

Use:

- active rate KPI
- 365-day survival KPI
- customer half-life KPI
- average active days in year 1 KPI

### Dataset 3: `sqlbook_customer_survival_milestones`

Dataset ID on this machine: `29`

SQL:

```sql
WITH base AS (
  SELECT
    Tenure,
    is_stop = CASE WHEN StopType IS NULL THEN 0.0 ELSE 1.0 END
  FROM dbo.Subscribers
  WHERE StartDate >= '2004-01-01'
    AND Tenure >= 0
),
h AS (
  SELECT
    Tenure,
    population_at_risk = SUM(COUNT(*)) OVER (ORDER BY Tenure DESC),
    num_stops = SUM(is_stop),
    hazard = SUM(is_stop) / SUM(COUNT(*)) OVER (ORDER BY Tenure DESC)
  FROM base
  GROUP BY Tenure
),
s AS (
  SELECT
    Tenure,
    population_at_risk,
    num_stops,
    hazard,
    survival = COALESCE(
      EXP(
        SUM(LOG(NULLIF(1 - hazard, 0))) OVER (
          ORDER BY Tenure
          ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING
        )
      ),
      1.0
    )
  FROM h
)
SELECT
  Tenure,
  PopulationAtRisk = CAST(population_at_risk AS bigint),
  NumStops = CAST(num_stops AS bigint),
  HazardPct = ROUND(hazard * 100.0, 4),
  SurvivalPct = ROUND(survival * 100.0, 4)
FROM s
WHERE Tenure IN (0, 30, 60, 90, 120, 180, 365, 540, 730, 900)
```

Use:

- milestone table at a set of important tenure checkpoints

### Dataset 4: `sqlbook_customer_survival_market_summary`

Dataset ID on this machine: `30`

SQL:

```sql
WITH survival_base AS (
  SELECT
    s.Market,
    s.Tenure,
    is_stop = CASE WHEN s.StopType IS NULL THEN 0.0 ELSE 1.0 END
  FROM (
    SELECT
      s.*,
      LeftTruncationDate = CASE
        WHEN s.Market = 'Smallville' THEN CAST('2004-10-27' AS date)
        ELSE CAST('2004-01-01' AS date)
      END
    FROM dbo.Subscribers s
  ) s
  WHERE s.StartDate >= s.LeftTruncationDate
    AND s.Tenure >= 0
),
h AS (
  SELECT
    Market,
    Tenure,
    hazard = SUM(is_stop) / SUM(COUNT(*)) OVER (PARTITION BY Market ORDER BY Tenure DESC)
  FROM survival_base
  GROUP BY Market, Tenure
),
s AS (
  SELECT
    Market,
    Tenure,
    survival = COALESCE(
      EXP(
        SUM(LOG(NULLIF(1 - hazard, 0))) OVER (
          PARTITION BY Market
          ORDER BY Tenure
          ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING
        )
      ),
      1.0
    )
  FROM h
),
cohort AS (
  SELECT
    Market,
    Customers = COUNT(*),
    ActiveRate = AVG(CASE WHEN StopType IS NULL THEN 1.0 ELSE 0.0 END),
    AvgTenureDays = AVG(CAST(Tenure AS float))
  FROM dbo.Subscribers
  WHERE StartDate >= '2004-01-01'
    AND Tenure >= 0
  GROUP BY Market
)
SELECT
  c.Market,
  c.Customers,
  ActiveRatePct = ROUND(c.ActiveRate * 100.0, 2),
  AvgTenureDays = ROUND(c.AvgTenureDays, 1),
  Survival365Pct = ROUND(MAX(CASE WHEN s.Tenure = 365 THEN s.survival END) * 100.0, 2),
  HalfLifeDays = MIN(CASE WHEN s.survival <= 0.5 THEN s.Tenure END)
FROM cohort c
LEFT JOIN s
  ON c.Market = s.Market
GROUP BY c.Market, c.Customers, c.ActiveRate, c.AvgTenureDays
```

Use:

- compare markets side by side in a compact summary table

### Dataset 5: `sqlbook_customer_survival_revenue_mc`

Dataset ID on this machine: `31`

SQL:

```sql
WITH rmc AS (
  SELECT
    s.Market,
    s.Channel,
    avgdaily = AVG(s.MonthlyFee) / 30.4
  FROM dbo.Subscribers s
  WHERE s.StartDate >= '2006-01-01'
    AND s.Tenure >= 0
  GROUP BY s.Market, s.Channel
),
hmc AS (
  SELECT
    s.Market,
    s.Channel,
    s.Tenure,
    nexttenure = LEAD(s.Tenure) OVER (PARTITION BY s.Market, s.Channel ORDER BY s.Tenure),
    hazard = SUM(1.0 - s.IsActive) /
      SUM(COUNT(*)) OVER (PARTITION BY s.Market, s.Channel ORDER BY s.Tenure DESC)
  FROM (
    SELECT
      s.*,
      LeftTruncationDate = CASE
        WHEN s.Market = 'Smallville' THEN CAST('2004-10-27' AS date)
        ELSE CAST('2004-01-01' AS date)
      END
    FROM dbo.Subscribers s
  ) s
  WHERE s.StartDate >= s.LeftTruncationDate
    AND s.Tenure >= 0
  GROUP BY s.Tenure, s.Market, s.Channel
),
smc AS (
  SELECT
    hmc.Market,
    hmc.Channel,
    hmc.Tenure,
    hmc.nexttenure,
    survival = COALESCE(
      EXP(
        SUM(LOG(NULLIF(1 - hmc.hazard, 0))) OVER (
          PARTITION BY hmc.Market, hmc.Channel
          ORDER BY hmc.Tenure
          ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING
        )
      ),
      1.0
    )
  FROM hmc
)
SELECT
  smc.Market,
  smc.Channel,
  EstimatedRevenueYear1 = ROUND(
    SUM(
      smc.survival *
      CASE
        WHEN COALESCE(smc.nexttenure, 365) > 365 THEN 365 - smc.Tenure
        ELSE COALESCE(smc.nexttenure, 365) - smc.Tenure
      END *
      rmc.avgdaily
    ),
    2
  )
FROM smc
JOIN rmc
  ON smc.Market = rmc.Market
 AND smc.Channel = rmc.Channel
WHERE smc.Tenure BETWEEN 0 AND 365
  AND COALESCE(smc.nexttenure, 365) > smc.Tenure
GROUP BY smc.Market, smc.Channel
```

Use:

- first-year revenue pivot by market and channel

## 6. Charts Created

The helper created these ten saved charts:

1. `SQLBook Active Rate` using `big_number_total`
2. `SQLBook 365-Day Survival` using `big_number_total`
3. `SQLBook Customer Half-Life (Days)` using `big_number_total`
4. `SQLBook Avg Active Days in Year 1` using `big_number_total`
5. `SQLBook Tenure Distribution by Market` using `histogram_v2`
6. `SQLBook Stop Type Mix` using `pie`
7. `SQLBook Tenure Spread by Market` using `box_plot`
8. `SQLBook Survival Milestones` using `table`
9. `SQLBook Market Survival Summary` using `table`
10. `SQLBook First-Year Revenue by Market/Channel` using `pivot_table_v2`

### Key Chart Design Choices

#### KPI Cards

- used `MAX` over the KPI dataset because each KPI dataset query returns one row
- formats:
  - percentage cards used `.1%`
  - day counts used `SMART_NUMBER`

#### Distribution Views

- histogram grouped by `Market`
- 30 bins
- `supersetAndPresetColors`

#### Stop-Type Mix

- donut pie chart
- group by `StopTypeLabel`
- metric `COUNT(SubscriberId)`

#### Revenue Matrix

- pivot rows: `Market`
- pivot columns: `Channel`
- metric: `SUM(EstimatedRevenueYear1)`
- value format: `$,.2f`

## 7. Dashboard Assembly And Layout

### Saved Dashboard

- title: `How Long Will Customers Last? SQLBook Survival Analysis`
- dashboard ID: `14`
- slug: `sqlbook-customer-survival-analysis`
- URL: `http://localhost:8088/superset/dashboard/sqlbook-customer-survival-analysis/`

### Layout Design

The dashboard is intentionally arranged from summary to detail.

#### Row 1: KPI Row

- `SQLBook Active Rate`
- `SQLBook 365-Day Survival`
- `SQLBook Customer Half-Life (Days)`
- `SQLBook Avg Active Days in Year 1`

Reason:

- put the headline retention story at the top

#### Row 2: Distribution Row

- `SQLBook Tenure Distribution by Market`
- `SQLBook Stop Type Mix`

Reason:

- show the overall churn shape before drilling into segmented tables

#### Row 3: Detail Row

- `SQLBook Tenure Spread by Market`
- `SQLBook Survival Milestones`

Reason:

- combine distribution spread with exact milestone checkpoints

#### Row 4: Summary Tables

- `SQLBook Market Survival Summary`
- `SQLBook First-Year Revenue by Market/Channel`

Reason:

- end with the two most decision-ready views: segment comparison and expected value

### Relevant Layout Snippet

```python
row_defs = [
    ("ROW-KPI", [
        ("CHART-ACTIVE-RATE", charts[0], 3, 18),
        ("CHART-SURVIVAL-365", charts[1], 3, 18),
        ("CHART-HALF-LIFE", charts[2], 3, 18),
        ("CHART-Y1-DAYS", charts[3], 3, 18),
    ]),
    ("ROW-DISTRIBUTION", [
        ("CHART-TENURE-HIST", charts[4], 8, 42),
        ("CHART-STOP-MIX", charts[5], 4, 42),
    ]),
    ("ROW-DETAILS", [
        ("CHART-TENURE-BOX", charts[6], 6, 42),
        ("CHART-MILESTONES", charts[7], 6, 42),
    ]),
    ("ROW-TABLES", [
        ("CHART-MARKET-SUMMARY", charts[8], 6, 42),
        ("CHART-REVENUE", charts[9], 6, 42),
    ]),
]
```

### Filters And Theming

`Actual`:

- no dashboard-level cross filters were enabled
- background was kept transparent
- the built-in Superset color schemes were used

Why:

- the goal was a reliable analytical dashboard, not a custom visual theme
- avoiding extra dashboard state made the saved layout easier to reproduce by script

## 8. Actual Helper Run Commands

### Copy The Helper Into The Running Container

```powershell
cd C:\Users\hp\Documents\GitHub\Apache-Superset\superset
$env:DOCKER_CONFIG = Join-Path $env:TEMP 'codex-docker-config'
& 'C:\Program Files\Docker\Docker\resources\bin\docker.exe' cp 'C:\Users\hp\Documents\GitHub\Apache-Superset\superset\tmp_sqlbook_survival_dashboard.py' superset_app:/tmp/sqlbook_survival_dashboard.py
```

### Execute The Helper

```powershell
cd C:\Users\hp\Documents\GitHub\Apache-Superset\superset
$env:DOCKER_CONFIG = Join-Path $env:TEMP 'codex-docker-config'
& 'C:\Program Files\Docker\Docker\resources\bin\docker.exe' exec -e SUPERSET_BASE_URL=http://127.0.0.1:8088 -e SUPERSET_USERNAME=superset_local_admin -e SUPERSET_PASSWORD='piCCh4Q(QeWQ%_Rai}CBU%Xe' superset_app python /tmp/sqlbook_survival_dashboard.py
```

## 9. Validation Results

### Dashboard-Level Validation

`Actual`:

- dashboard ID `14` exists
- slug `sqlbook-customer-survival-analysis` exists
- the dashboard opens at:
  - `http://localhost:8088/superset/dashboard/sqlbook-customer-survival-analysis/`

### Chart Warmup Validation

`Actual`: all ten charts warmed successfully after the final helper run.

Why this mattered:

- it proved the dashboard was not just saved metadata
- it exercised the saved query context and datasource SQL

### KPI Values Confirmed On This Machine

- 365-day survival: `0.720920670453709`
- customer half-life: `569`
- average active days in year 1: `304.56824409567`

### Market Examples Confirmed On This Machine

- `Gotham`: 365-day survival `0.681706649782283`, half-life `453`
- `Metropolis`: 365-day survival `0.709695809377703`, half-life `610`
- `Smallville`: 365-day survival `0.829547004437793`, half-life not reached in the observed window

## 10. Important Fixes Discovered While Building The Dashboard

### Fix 1: Remove Trailing `ORDER BY` From SQL Server Virtual Datasets

Problem:

- SQL Server rejected virtual dataset SQL that ended with `ORDER BY` after Superset wrapped it in an outer query

Fix:

- remove the raw `ORDER BY` from the virtual dataset SQL
- let the chart or table config handle ordering instead

### Fix 2: Persist `query_context` For REST-Created Charts

Problem:

- some charts existed but did not warm correctly because the saved `query_context` payload was missing

Fix:

- the helper was updated to explicitly save the correct `query_context` for the non-legacy chart types before warming them

## 11. How To Re-Run Or Edit The Dashboard Later

### Re-Run

- edit `tmp_sqlbook_survival_dashboard.py` locally if needed
- copy it into `superset_app`
- execute it again with the same three environment variables

### Safe Changes To Make Later

- add more milestone checkpoints in the milestones dataset
- add a filter or slicer row if you decide to support interactive market/channel filtering
- add a time-series chart later if the SQLBook materials include acquisition date cohorts you want to visualize over calendar time

### Avoid These Mistakes

- do not reintroduce raw trailing `ORDER BY` inside the virtual dataset SQL
- do not assume a chart is valid just because it saved; warm or render it
- do not hard-code a different Superset database ID unless you confirm `SQLBook` is still database `2`
