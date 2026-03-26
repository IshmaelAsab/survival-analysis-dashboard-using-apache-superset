import json
import os
import re
import sys
from textwrap import dedent

import requests


BASE_URL = os.environ.get("SUPERSET_BASE_URL", "http://127.0.0.1:8088").rstrip("/")
USERNAME = os.environ["SUPERSET_USERNAME"]
PASSWORD = os.environ["SUPERSET_PASSWORD"]
DATABASE_ID = 2
OWNER_ID = 2
DASHBOARD_TITLE = "How Long Will Customers Last? SQLBook Survival Analysis"
DASHBOARD_SLUG = "sqlbook-customer-survival-analysis"


session = requests.Session()
session.headers.update({"Referer": BASE_URL})


def fail(message: str) -> None:
    print(message, file=sys.stderr)
    sys.exit(1)


def extract_id(payload: dict) -> int:
    if "id" in payload:
        return payload["id"]
    if isinstance(payload.get("result"), dict) and "id" in payload["result"]:
        return payload["result"]["id"]
    fail(f"Unable to extract id from response: {json.dumps(payload, indent=2)}")


def api(method: str, path: str, expected=(200,), **kwargs) -> dict:
    url = f"{BASE_URL}{path}"
    response = session.request(method, url, timeout=120, **kwargs)
    if response.status_code not in expected:
        fail(
            f"{method} {path} failed with {response.status_code}: {response.text}"
        )
    if not response.text:
        return {}
    try:
        return response.json()
    except ValueError:
        return {"raw": response.text}


def sanitize_column(column: dict) -> dict:
    allowed_keys = {
        "advanced_data_type",
        "column_name",
        "description",
        "expression",
        "filterable",
        "groupby",
        "id",
        "is_dttm",
        "optionName",
        "python_date_format",
        "type",
        "type_generic",
        "verbose_name",
        "warning_markdown",
    }
    payload = {key: column.get(key) for key in allowed_keys if key in column}
    payload.setdefault("optionName", f"_col_{column['column_name']}")
    return payload


def slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")


def simple_metric(column: dict, aggregate: str, label: str) -> dict:
    return {
        "expressionType": "SIMPLE",
        "column": sanitize_column(column),
        "aggregate": aggregate,
        "sqlExpression": None,
        "datasourceWarning": False,
        "hasCustomLabel": True,
        "label": label,
        "optionName": f"metric_{slugify(label)}",
    }


def login() -> None:
    login_payload = {
        "username": USERNAME,
        "password": PASSWORD,
        "provider": "db",
        "refresh": True,
    }
    auth = api(
        "POST",
        "/api/v1/security/login",
        expected=(200,),
        json=login_payload,
        headers={"Content-Type": "application/json"},
    )
    access_token = auth["access_token"]
    session.headers.update({"Authorization": f"Bearer {access_token}"})
    csrf = api("GET", "/api/v1/security/csrf_token/")["result"]
    session.headers.update({"X-CSRFToken": csrf})


def list_items(path: str) -> list[dict]:
    payload = api("GET", f"{path}?q=(page:0,page_size:500)")
    return payload.get("result", [])


def ensure_dataset(table_name: str, sql: str | None, schema: str = "dbo") -> dict:
    datasets = list_items("/api/v1/dataset/")
    existing = next(
        (
            item
            for item in datasets
            if item["table_name"] == table_name and item["database"]["id"] == DATABASE_ID
        ),
        None,
    )
    if existing:
        payload = {
            "table_name": table_name,
            "database_id": DATABASE_ID,
            "schema": schema,
            "sql": sql,
            "owners": [OWNER_ID],
        }
        api(
            "PUT",
            f"/api/v1/dataset/{existing['id']}",
            expected=(200,),
            json=payload,
        )
        dataset_id = existing["id"]
        action = "Updated"
    else:
        payload = {
            "database": DATABASE_ID,
            "schema": schema,
            "table_name": table_name,
            "sql": sql,
            "owners": [OWNER_ID],
        }
        created = api("POST", "/api/v1/dataset/", expected=(201,), json=payload)
        dataset_id = extract_id(created)
        action = "Created"
    api("PUT", f"/api/v1/dataset/{dataset_id}/refresh", expected=(200,))
    dataset = api("GET", f"/api/v1/dataset/{dataset_id}")["result"]
    print(f"{action} dataset {table_name} -> {dataset_id}")
    return dataset


def ensure_dashboard() -> dict:
    dashboards = list_items("/api/v1/dashboard/")
    existing = next(
        (
            item
            for item in dashboards
            if item.get("slug") == DASHBOARD_SLUG
            or item.get("dashboard_title") == DASHBOARD_TITLE
        ),
        None,
    )
    payload = {
        "dashboard_title": DASHBOARD_TITLE,
        "slug": DASHBOARD_SLUG,
        "owners": [OWNER_ID],
        "published": True,
        "css": "",
        "json_metadata": json.dumps(
            {
                "refresh_frequency": 0,
                "timed_refresh_immune_slices": [],
                "expanded_slices": {},
                "color_scheme": "",
                "label_colors": {},
                "shared_label_colors": [],
                "map_label_colors": {},
                "color_scheme_domain": [],
                "cross_filters_enabled": False,
            }
        ),
        "position_json": json.dumps(
            {
                "DASHBOARD_VERSION_KEY": "v2",
                "ROOT_ID": {"children": ["GRID_ID"], "id": "ROOT_ID", "type": "ROOT"},
                "GRID_ID": {
                    "children": [],
                    "id": "GRID_ID",
                    "parents": ["ROOT_ID"],
                    "type": "GRID",
                },
                "HEADER_ID": {
                    "id": "HEADER_ID",
                    "meta": {"text": DASHBOARD_TITLE},
                    "type": "HEADER",
                },
            }
        ),
    }
    if existing:
        api(
            "PUT",
            f"/api/v1/dashboard/{existing['id']}",
            expected=(200,),
            json=payload,
        )
        dashboard_id = existing["id"]
        action = "Updated"
    else:
        created = api("POST", "/api/v1/dashboard/", expected=(201,), json=payload)
        dashboard_id = extract_id(created)
        action = "Created"
    dashboard = api("GET", f"/api/v1/dashboard/{dashboard_id}")["result"]
    print(f"{action} dashboard {DASHBOARD_TITLE} -> {dashboard_id}")
    return dashboard


def ensure_chart(
    name: str,
    dataset: dict,
    viz_type: str,
    form_data: dict,
    dashboard_id: int,
) -> dict:
    charts = list_items("/api/v1/chart/")
    existing = next((item for item in charts if item["slice_name"] == name), None)
    payload = {
        "slice_name": name,
        "viz_type": viz_type,
        "owners": [OWNER_ID],
        "params": json.dumps(form_data),
        "query_context_generation": True,
        "datasource_id": dataset["id"],
        "datasource_type": "table",
        "dashboards": [dashboard_id],
    }
    if existing:
        api("PUT", f"/api/v1/chart/{existing['id']}", expected=(200,), json=payload)
        chart_id = existing["id"]
        action = "Updated"
    else:
        created = api("POST", "/api/v1/chart/", expected=(201,), json=payload)
        chart_id = extract_id(created)
        action = "Created"
    chart = api("GET", f"/api/v1/chart/{chart_id}")["result"]
    print(f"{action} chart {name} -> {chart_id}")
    return chart


def update_dashboard_layout(dashboard_id: int, charts: list[dict]) -> dict:
    row_defs = [
        (
            "ROW-KPI",
            [
                ("CHART-ACTIVE-RATE", charts[0], 3, 18),
                ("CHART-SURVIVAL-365", charts[1], 3, 18),
                ("CHART-HALF-LIFE", charts[2], 3, 18),
                ("CHART-Y1-DAYS", charts[3], 3, 18),
            ],
        ),
        (
            "ROW-DISTRIBUTION",
            [
                ("CHART-TENURE-HIST", charts[4], 8, 42),
                ("CHART-STOP-MIX", charts[5], 4, 42),
            ],
        ),
        (
            "ROW-DETAILS",
            [
                ("CHART-TENURE-BOX", charts[6], 6, 42),
                ("CHART-MILESTONES", charts[7], 6, 42),
            ],
        ),
        (
            "ROW-TABLES",
            [
                ("CHART-MARKET-SUMMARY", charts[8], 6, 42),
                ("CHART-REVENUE", charts[9], 6, 42),
            ],
        ),
    ]

    position = {
        "DASHBOARD_VERSION_KEY": "v2",
        "ROOT_ID": {"children": ["GRID_ID"], "id": "ROOT_ID", "type": "ROOT"},
        "GRID_ID": {
            "children": [row_id for row_id, _ in row_defs],
            "id": "GRID_ID",
            "parents": ["ROOT_ID"],
            "type": "GRID",
        },
        "HEADER_ID": {
            "id": "HEADER_ID",
            "meta": {"text": DASHBOARD_TITLE},
            "type": "HEADER",
        },
    }

    for row_id, row_charts in row_defs:
        position[row_id] = {
            "children": [chart_node_id for chart_node_id, *_ in row_charts],
            "id": row_id,
            "meta": {"background": "BACKGROUND_TRANSPARENT"},
            "parents": ["ROOT_ID", "GRID_ID"],
            "type": "ROW",
        }
        for chart_node_id, chart, width, height in row_charts:
            position[chart_node_id] = {
                "children": [],
                "id": chart_node_id,
                "meta": {
                    "chartId": chart["id"],
                    "height": height,
                    "sliceName": chart["slice_name"],
                    "uuid": chart["uuid"],
                    "width": width,
                },
                "parents": ["ROOT_ID", "GRID_ID", row_id],
                "type": "CHART",
            }

    payload = {
        "dashboard_title": DASHBOARD_TITLE,
        "slug": DASHBOARD_SLUG,
        "owners": [OWNER_ID],
        "published": True,
        "css": "",
        "json_metadata": json.dumps(
            {
                "refresh_frequency": 0,
                "timed_refresh_immune_slices": [],
                "expanded_slices": {},
                "color_scheme": "",
                "label_colors": {},
                "shared_label_colors": [],
                "map_label_colors": {},
                "color_scheme_domain": [],
                "cross_filters_enabled": False,
            }
        ),
        "position_json": json.dumps(position),
    }
    api("PUT", f"/api/v1/dashboard/{dashboard_id}", expected=(200,), json=payload)
    return api("GET", f"/api/v1/dashboard/{dashboard_id}")["result"]


def warm_up_chart(chart_id: int, dashboard_id: int) -> dict:
    result = api(
        "PUT",
        "/api/v1/chart/warm_up_cache",
        expected=(200,),
        json={"chart_id": chart_id, "dashboard_id": dashboard_id},
    )["result"]
    if isinstance(result, list):
        result = result[0]
    if result.get("viz_error"):
        fail(
            f"Chart warm up failed for {chart_id}: "
            f"{result.get('viz_error')} (status={result.get('viz_status')})"
        )
    print(f"Warmed up chart {chart_id}")
    return result


def save_query_context(chart_id: int, query_context: dict) -> None:
    api(
        "PUT",
        f"/api/v1/chart/{chart_id}",
        expected=(200,),
        json={
            "query_context": json.dumps(query_context),
            "query_context_generation": True,
        },
    )
    print(f"Saved query context for chart {chart_id}")


def column_by_name(dataset: dict, name: str) -> dict:
    for column in dataset["columns"]:
        if column["column_name"] == name:
            return column
    fail(f"Column {name} not found in dataset {dataset['table_name']}")


def kpi_form_data(dataset: dict, column_name: str, label: str, fmt: str) -> dict:
    metric = simple_metric(column_by_name(dataset, column_name), "MAX", label)
    return {
        "adhoc_filters": [],
        "annotation_layers": [],
        "datasource": f"{dataset['id']}__table",
        "header_font_size": 0.4,
        "metric": metric,
        "queryFields": {"metric": "metrics"},
        "subheader_font_size": 0.15,
        "time_range": "No filter",
        "url_params": {},
        "viz_type": "big_number_total",
        "y_axis_format": fmt,
    }


def build_big_number_query_context(dataset: dict, form_data: dict, chart_id: int) -> dict:
    final_form_data = {**form_data, "slice_id": chart_id}
    return {
        "datasource": {"id": dataset["id"], "type": "table"},
        "force": False,
        "queries": [
            {
                "time_range": "No filter",
                "filters": [],
                "extras": {"having": "", "where": ""},
                "applied_time_extras": {},
                "columns": [],
                "metrics": [form_data["metric"]],
                "annotation_layers": [],
                "series_limit": 0,
                "group_others_when_limit_reached": False,
                "order_desc": True,
                "url_params": {},
                "custom_params": {},
                "custom_form_data": {},
            }
        ],
        "form_data": final_form_data,
        "result_format": "json",
        "result_type": "full",
    }


def build_pie_query_context(dataset: dict, form_data: dict, chart_id: int) -> dict:
    final_form_data = {**form_data, "slice_id": chart_id}
    return {
        "datasource": {"id": dataset["id"], "type": "table"},
        "force": False,
        "queries": [
            {
                "filters": [],
                "extras": {"having": "", "where": ""},
                "applied_time_extras": {},
                "columns": form_data["groupby"],
                "metrics": [form_data["metric"]],
                "annotation_layers": [],
                "series_limit": 0,
                "group_others_when_limit_reached": False,
                "order_desc": True,
                "url_params": {},
                "custom_params": {},
                "custom_form_data": {},
                "post_processing": [
                    {
                        "operation": "contribution",
                        "options": {
                            "columns": [form_data["metric"]["label"]],
                            "rename_columns": [
                                f"{form_data['metric']['label']}__contribution"
                            ],
                        },
                    }
                ],
            }
        ],
        "form_data": final_form_data,
        "result_format": "json",
        "result_type": "full",
    }


def build_histogram_query_context(dataset: dict, form_data: dict, chart_id: int) -> dict:
    final_form_data = {**form_data, "slice_id": chart_id}
    groupby = form_data.get("groupby", [])
    column = form_data["column"]
    return {
        "datasource": {"id": dataset["id"], "type": "table"},
        "force": False,
        "queries": [
            {
                "filters": [],
                "extras": {"having": "", "where": ""},
                "applied_time_extras": {},
                "columns": [*groupby, column],
                "metrics": None,
                "annotation_layers": [],
                "row_limit": form_data.get("row_limit"),
                "series_limit": 0,
                "group_others_when_limit_reached": False,
                "order_desc": True,
                "url_params": {},
                "custom_params": {},
                "custom_form_data": {},
                "post_processing": [
                    {
                        "operation": "histogram",
                        "options": {
                            "column": column,
                            "groupby": groupby,
                            "bins": int(form_data.get("bins", 5)),
                            "cumulative": bool(form_data.get("cumulative", False)),
                            "normalize": bool(form_data.get("normalize", False)),
                        },
                    }
                ],
            }
        ],
        "form_data": final_form_data,
        "result_format": "json",
        "result_type": "full",
    }


def build_boxplot_query_context(dataset: dict, form_data: dict, chart_id: int) -> dict:
    final_form_data = {**form_data, "slice_id": chart_id}
    groupby = form_data.get("groupby", [])
    columns = form_data.get("columns", [])
    metrics = form_data.get("metrics", [])
    return {
        "datasource": {"id": dataset["id"], "type": "table"},
        "force": False,
        "queries": [
            {
                "filters": [],
                "extras": {"having": "", "where": ""},
                "applied_time_extras": {},
                "columns": [*columns, *groupby],
                "metrics": metrics,
                "series_columns": groupby,
                "annotation_layers": [],
                "series_limit": 0,
                "group_others_when_limit_reached": False,
                "order_desc": True,
                "url_params": {},
                "custom_params": {},
                "custom_form_data": {},
                "post_processing": [
                    {
                        "operation": "boxplot",
                        "options": {
                            "whisker_type": "tukey",
                            "percentiles": None,
                            "groupby": groupby,
                            "metrics": metrics,
                        },
                    }
                ],
            }
        ],
        "form_data": final_form_data,
        "result_format": "json",
        "result_type": "full",
    }


def build_pivot_query_context(dataset: dict, form_data: dict, chart_id: int) -> dict:
    final_form_data = {**form_data, "slice_id": chart_id}
    groupby_columns = form_data.get("groupbyColumns", [])
    groupby_rows = form_data.get("groupbyRows", [])
    metrics = form_data.get("metrics", [])
    orderby = [[metrics[0], False]] if metrics else None
    return {
        "datasource": {"id": dataset["id"], "type": "table"},
        "force": False,
        "queries": [
            {
                "filters": [],
                "extras": {"having": "", "where": ""},
                "applied_time_extras": {},
                "columns": [*groupby_columns, *groupby_rows],
                "metrics": metrics,
                "orderby": orderby,
                "annotation_layers": [],
                "row_limit": form_data.get("row_limit"),
                "series_limit": 0,
                "group_others_when_limit_reached": False,
                "order_desc": True,
                "url_params": {},
                "custom_params": {},
                "custom_form_data": {},
            }
        ],
        "form_data": final_form_data,
        "result_format": "json",
        "result_type": "full",
    }


def build_table_query_context(dataset: dict, form_data: dict, chart_id: int) -> dict:
    final_form_data = {**form_data, "slice_id": chart_id}
    return {
        "datasource": {"id": dataset["id"], "type": "table"},
        "force": False,
        "queries": [
            {
                "filters": [],
                "extras": {"having": "", "where": ""},
                "applied_time_extras": {},
                "columns": form_data.get("all_columns", []),
                "metrics": None,
                "annotation_layers": [],
                "row_limit": form_data.get("row_limit"),
                "row_offset": 0,
                "series_limit": 0,
                "group_others_when_limit_reached": False,
                "order_desc": bool(form_data.get("order_desc", False)),
                "url_params": {},
                "custom_params": {},
                "custom_form_data": {},
                "post_processing": [],
            }
        ],
        "form_data": final_form_data,
        "result_format": "json",
        "result_type": "full",
    }


def main() -> None:
    login()

    cohort_dataset = ensure_dataset(
        "sqlbook_customer_survival_cohort",
        dedent(
            """
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
            """
        ).strip(),
    )

    kpi_dataset = ensure_dataset(
        "sqlbook_customer_survival_kpis",
        dedent(
            """
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
            """
        ).strip(),
    )

    milestones_dataset = ensure_dataset(
        "sqlbook_customer_survival_milestones",
        dedent(
            """
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
            """
        ).strip(),
    )

    market_summary_dataset = ensure_dataset(
        "sqlbook_customer_survival_market_summary",
        dedent(
            """
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
            """
        ).strip(),
    )

    revenue_dataset = ensure_dataset(
        "sqlbook_customer_survival_revenue_mc",
        dedent(
            """
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
            """
        ).strip(),
    )

    dashboard = ensure_dashboard()
    dashboard_id = dashboard["id"]

    active_rate_form = kpi_form_data(
        kpi_dataset, "active_rate", "Active Rate", ".1%"
    )
    survival_365_form = kpi_form_data(
        kpi_dataset, "survival_365", "365-Day Survival", ".1%"
    )
    half_life_form = kpi_form_data(
        kpi_dataset,
        "half_life_days",
        "Customer Half-Life (Days)",
        "SMART_NUMBER",
    )
    avg_days_form = kpi_form_data(
        kpi_dataset,
        "avg_days_first_year",
        "Avg Active Days in Year 1",
        "SMART_NUMBER",
    )
    tenure_hist_form = {
        "datasource": f"{cohort_dataset['id']}__table",
        "viz_type": "histogram_v2",
        "column": "Tenure",
        "groupby": ["Market"],
        "adhoc_filters": [],
        "row_limit": 10000,
        "bins": 30,
        "normalize": False,
        "color_scheme": "supersetAndPresetColors",
        "show_value": False,
        "show_legend": True,
        "annotation_layers": [],
        "dashboards": [dashboard_id],
    }
    stop_type_mix_form = {
        "adhoc_filters": [],
        "annotation_layers": [],
        "color_scheme": "supersetColors",
        "datasource": f"{cohort_dataset['id']}__table",
        "donut": True,
        "groupby": ["StopTypeLabel"],
        "innerRadius": 45,
        "label_line": True,
        "labels_outside": True,
        "label_type": "key",
        "metric": simple_metric(
            column_by_name(cohort_dataset, "SubscriberId"),
            "COUNT",
            "Subscribers",
        ),
        "number_format": "SMART_NUMBER",
        "outerRadius": 67,
        "queryFields": {"groupby": "groupby", "metric": "metrics"},
        "row_limit": None,
        "show_labels": True,
        "show_legend": True,
        "url_params": {},
        "viz_type": "pie",
        "dashboards": [dashboard_id],
    }
    tenure_box_form = {
        "datasource": f"{cohort_dataset['id']}__table",
        "viz_type": "box_plot",
        "columns": ["Tenure"],
        "groupby": ["Market"],
        "metrics": ["count"],
        "adhoc_filters": [],
        "whiskerOptions": "Tukey",
        "x_axis_title_margin": 15,
        "y_axis_title_margin": 15,
        "y_axis_title_position": "Left",
        "color_scheme": "supersetColors",
        "x_ticks_layout": "auto",
        "number_format": "SMART_NUMBER",
        "annotation_layers": [],
        "dashboards": [dashboard_id],
    }
    milestones_form = {
        "datasource": f"{milestones_dataset['id']}__table",
        "viz_type": "table",
        "query_mode": "raw",
        "groupby": [],
        "all_columns": [
            "Tenure",
            "PopulationAtRisk",
            "NumStops",
            "HazardPct",
            "SurvivalPct",
        ],
        "percent_metrics": [],
        "adhoc_filters": [],
        "order_by_cols": [],
        "row_limit": 1000,
        "server_page_length": 10,
        "order_desc": False,
        "show_cell_bars": True,
        "color_pn": True,
        "allow_render_html": True,
        "annotation_layers": [],
        "dashboards": [dashboard_id],
    }
    market_summary_form = {
        "datasource": f"{market_summary_dataset['id']}__table",
        "viz_type": "table",
        "query_mode": "raw",
        "groupby": [],
        "all_columns": [
            "Market",
            "Customers",
            "ActiveRatePct",
            "AvgTenureDays",
            "Survival365Pct",
            "HalfLifeDays",
        ],
        "percent_metrics": [],
        "adhoc_filters": [],
        "order_by_cols": [],
        "row_limit": 1000,
        "server_page_length": 10,
        "order_desc": False,
        "show_cell_bars": True,
        "color_pn": True,
        "allow_render_html": True,
        "annotation_layers": [],
        "dashboards": [dashboard_id],
    }
    revenue_form = {
        "datasource": f"{revenue_dataset['id']}__table",
        "viz_type": "pivot_table_v2",
        "groupbyColumns": ["Channel"],
        "groupbyRows": ["Market"],
        "metrics": [
            simple_metric(
                column_by_name(revenue_dataset, "EstimatedRevenueYear1"),
                "SUM",
                "Estimated Revenue Year 1",
            )
        ],
        "metricsLayout": "COLUMNS",
        "adhoc_filters": [],
        "row_limit": 10000,
        "order_desc": True,
        "aggregateFunction": "Sum",
        "valueFormat": "$,.2f",
        "rowOrder": "key_a_to_z",
        "colOrder": "key_a_to_z",
        "annotation_layers": [],
        "dashboards": [dashboard_id],
    }

    charts = []
    charts.append(
        ensure_chart(
            "SQLBook Active Rate",
            kpi_dataset,
            "big_number_total",
            active_rate_form,
            dashboard_id,
        )
    )
    charts.append(
        ensure_chart(
            "SQLBook 365-Day Survival",
            kpi_dataset,
            "big_number_total",
            survival_365_form,
            dashboard_id,
        )
    )
    charts.append(
        ensure_chart(
            "SQLBook Customer Half-Life (Days)",
            kpi_dataset,
            "big_number_total",
            half_life_form,
            dashboard_id,
        )
    )
    charts.append(
        ensure_chart(
            "SQLBook Avg Active Days in Year 1",
            kpi_dataset,
            "big_number_total",
            avg_days_form,
            dashboard_id,
        )
    )
    charts.append(
        ensure_chart(
            "SQLBook Tenure Distribution by Market",
            cohort_dataset,
            "histogram_v2",
            tenure_hist_form,
            dashboard_id,
        )
    )
    charts.append(
        ensure_chart(
            "SQLBook Stop Type Mix",
            cohort_dataset,
            "pie",
            stop_type_mix_form,
            dashboard_id,
        )
    )
    charts.append(
        ensure_chart(
            "SQLBook Tenure Spread by Market",
            cohort_dataset,
            "box_plot",
            tenure_box_form,
            dashboard_id,
        )
    )
    charts.append(
        ensure_chart(
            "SQLBook Survival Milestones",
            milestones_dataset,
            "table",
            milestones_form,
            dashboard_id,
        )
    )
    charts.append(
        ensure_chart(
            "SQLBook Market Survival Summary",
            market_summary_dataset,
            "table",
            market_summary_form,
            dashboard_id,
        )
    )
    charts.append(
        ensure_chart(
            "SQLBook First-Year Revenue by Market/Channel",
            revenue_dataset,
            "pivot_table_v2",
            revenue_form,
            dashboard_id,
        )
    )

    dashboard = update_dashboard_layout(dashboard_id, charts)
    save_query_context(
        charts[0]["id"], build_big_number_query_context(kpi_dataset, active_rate_form, charts[0]["id"])
    )
    save_query_context(
        charts[1]["id"], build_big_number_query_context(kpi_dataset, survival_365_form, charts[1]["id"])
    )
    save_query_context(
        charts[2]["id"], build_big_number_query_context(kpi_dataset, half_life_form, charts[2]["id"])
    )
    save_query_context(
        charts[3]["id"], build_big_number_query_context(kpi_dataset, avg_days_form, charts[3]["id"])
    )
    save_query_context(
        charts[5]["id"], build_pie_query_context(cohort_dataset, stop_type_mix_form, charts[5]["id"])
    )
    save_query_context(
        charts[4]["id"],
        build_histogram_query_context(cohort_dataset, tenure_hist_form, charts[4]["id"]),
    )
    save_query_context(
        charts[6]["id"],
        build_boxplot_query_context(cohort_dataset, tenure_box_form, charts[6]["id"]),
    )
    save_query_context(
        charts[9]["id"],
        build_pivot_query_context(revenue_dataset, revenue_form, charts[9]["id"]),
    )
    save_query_context(
        charts[7]["id"],
        build_table_query_context(milestones_dataset, milestones_form, charts[7]["id"]),
    )
    save_query_context(
        charts[8]["id"],
        build_table_query_context(
            market_summary_dataset, market_summary_form, charts[8]["id"]
        ),
    )
    warmup_results = [warm_up_chart(chart["id"], dashboard_id) for chart in charts]
    print(
        json.dumps(
            {
                "dashboard_id": dashboard["id"],
                "dashboard_slug": dashboard["slug"],
                "dashboard_url": f"{BASE_URL}{dashboard['url']}",
                "chart_ids": [chart["id"] for chart in charts],
                "warmup_results": warmup_results,
                "dataset_ids": {
                    "cohort": cohort_dataset["id"],
                    "kpi": kpi_dataset["id"],
                    "milestones": milestones_dataset["id"],
                    "market_summary": market_summary_dataset["id"],
                    "revenue": revenue_dataset["id"],
                },
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
