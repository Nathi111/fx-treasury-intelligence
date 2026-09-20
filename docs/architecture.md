# Architecture

```text
Frankfurter v2 API ----\\
                        > Python extractors -> bronze.api_payload
World Bank v2 API -----/                         |
                                                 v
                                          Python transforms
                                                 |
                                                 v
                                     silver.fx_rate
                                     silver.macro_indicator
                                                 |
                                                 v
                                         Gold SQL views
                                                 |
                                                 v
                                             Power BI
```

## Design choices

- **Bronze** retains raw API payloads for lineage and debugging.
- **Silver** stores typed, deduplicated business-grain records.
- **Gold** exposes reporting-ready views for Power BI.
- Loads use PostgreSQL `ON CONFLICT` upserts so reruns are idempotent.
- GitHub Actions runs tests before the ETL. The repository secret is named `DATABASEURL` and is exposed to Python as the `DATABASE_URL` environment variable.
- Data-quality SQL is a pipeline gate: the ETL fails if the quality view returns failures.
