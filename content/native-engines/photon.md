# Photon

## What it is

Photon is the Databricks-native vectorized query engine. It accelerates SQL workloads, DataFrame API calls, ETL pipelines and stateless streaming, and it works with existing Spark APIs without code changes[^1]. It is available only on Databricks.

## How it executes

For supported operations, Photon replaces the JVM-based Spark SQL execution engine with a native C++ runtime. The Spark query optimizer (Catalyst) still plans the query, and Photon takes over at the execution layer, processing data in columnar batches rather than row by row[^1]. Databricks describes the effect of native C++ execution as eliminating garbage collection pauses, JIT warm-up delays and memory overhead for the work Photon runs[^1]. The [GC pressure](#bottleneck-gc) measured on a stage therefore reflects only the work still running on the JVM.

When Photon meets an unsupported operation during execution, it transparently falls back to the Spark runtime for the remainder of that operation, and the query still returns correct results[^1].

## Turning it on

Photon is enabled on serverless compute, SQL warehouses and serverless Lakeflow pipelines. On classic all-purpose compute, jobs compute and classic Lakeflow pipelines Databricks enables it by default, and the **Use Photon Acceleration** checkbox under **Performance** turns it on or off. Compute created through the Clusters API or Jobs API must set `runtime_engine` to `PHOTON`, and the Pipelines API uses `photon` set to `true`[^1]. Photon instance types consume DBUs at a different rate than the same instance type running the non-Photon runtime[^1].

## What changes for tuning

- **Joins and shuffle.** Photon replaces sort-merge joins with hash joins and uses a redesigned columnar shuffle[^1]. The Spark-side strategy choices on the [Join Optimization](#joins) and [Shuffle](#shuffle) pages describe the JVM engine that Photon replaces for supported operators.
- **Scans and writes.** Its scan implements filter pushdown, dictionary pruning and row-group skipping, and its native Parquet writer accelerates Delta Lake, Apache Iceberg and Parquet writes, including `UPDATE`, `DELETE`, `MERGE INTO`, `INSERT` and `CREATE TABLE AS SELECT`[^1].
- **UDFs.** Photon doesn't support UDFs, RDD APIs or Dataset APIs[^1]. A stage built around a [Python UDF](#pyspark) runs on the Spark runtime.
- **Streaming.** Photon supports stateless streaming only. Stateful streaming is not supported[^1].
- **Short queries.** Queries that normally finish in under two seconds see no meaningful improvement, because planning and scheduling overhead dominates their execution time[^1].
- **Features that need it.** Predictive I/O for reads and writes, and dynamic file pruning in `MERGE`, `UPDATE` and `DELETE`, require Photon to be enabled[^1].

## Supported operators

Photon covers scans (Parquet, Delta, CSV, JSON), filter and project, hash aggregate, hash join and shuffle, nested-loop join, null-aware anti join, union, expand, scalar subquery, the Delta and Parquet write sink, sort, top-K, limit and window functions. Databricks marks its expression and data-type categories as representative, not exhaustive, and notes that individual functions within a category may have limitations[^1].

## Seeing where Photon ran

On classic all-purpose and jobs compute, the SQL/DataFrame tab of the Spark UI draws Photon operators in orange in the query DAG and standard Spark operators in blue. On SQL warehouses and serverless compute, the query profile's Execution Details view shows the percentage of task time spent in Photon, and the query plan marks Photon operators purple and standard operators grey. If a query isn't using Photon as expected, Databricks says to check for unsupported operations, UDFs or data formats that cause a fallback to the Spark runtime[^1].

## Confidence

The behavior described here is documented by Databricks on its Photon page[^1]. That page is the only source for this section, and it lists operators and expressions as representative rather than exhaustive, so a specific function can still fall back even when its category is supported. Treat the plan colors and the Photon share of task time as the check for any one query.

## Limitations / false-positive risk

Photon exists only on Databricks. Fallback happens per operation: one unsupported expression moves the remainder of that operation to the Spark runtime[^1], so a partly accelerated stage still shows JVM-side GC, spill and serialization costs. A short query's runtime is dominated by planning and scheduling rather than data processing[^1], which makes a missing speedup there expected, not a misconfiguration.

## Sources

[^1]: [What is Photon? (Databricks)](https://docs.databricks.com/aws/en/compute/photon)
