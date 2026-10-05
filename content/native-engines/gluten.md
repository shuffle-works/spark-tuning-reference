# Apache Gluten

## What it is

Gluten is a middle layer that offloads the execution of JVM-based SQL engines to native engines[^1]. This page covers its Velox backend. Spark keeps the control flow: Gluten transforms Spark's whole-stage physical plan into a Substrait plan, sends it to the native engine, and reuses Spark's distributed control flow[^1]. The notes here follow Gluten's documentation on its main branch, which is not versioned, so check them against the release you run.

## Turning it on

The Velox backend needs four static settings: `spark.plugins` set to `org.apache.gluten.GlutenPlugin`, `spark.shuffle.manager` set to `org.apache.spark.shuffle.sort.ColumnarShuffleManager`, `spark.memory.offHeap.enabled` set to `true`, and a `spark.memory.offHeap.size`[^2]. Static means they are fixed when the application starts.

```properties
spark.plugins=org.apache.gluten.GlutenPlugin
spark.shuffle.manager=org.apache.spark.shuffle.sort.ColumnarShuffleManager
spark.memory.offHeap.enabled=true
spark.memory.offHeap.size=20g
```

The officially supported Spark versions are 3.4.4, 3.5.5, 4.0.2 and 4.1.1, and Spark 4.0 and 4.1 require JDK 17 or later and Scala 2.13[^3]. On an unofficially supported Spark version, `NoSuchMethodError` can be thrown at runtime[^4].

## Memory

Gluten allocates native memory from `spark.memory.offHeap.size` even when off-heap memory is otherwise disabled, and its configuration reference recommends a larger value if the plugin runs out of memory[^2]. The Velox example in its getting-started guide uses `--executor-memory 25g`, `spark.memory.offHeap.size=20g` and `spark.executor.memoryOverhead=5g`, and says to adjust executor cores, memory and off-heap size to your environment[^3]. Two further settings shape how that memory is shared:

- `spark.gluten.memory.isolation` (default `false`) caps the off-heap memory each task can use at executor memory divided by the maximum task slots. It is recommended when Gluten serves concurrent queries in one session, because not all memory Gluten allocates is guaranteed to be spillable[^2].
- `spark.gluten.memory.overAcquiredMemoryRatio` (default `0.3`) lets the Velox backend over-acquire that ratio of the allocated memory as a backup against out-of-memory errors[^2].

The Velox backend supports spill-to-disk, and `spillStrategy` set to `auto` (the default) lets the Spark memory manager manage Velox's spilling, while `none` disables it[^3]. Gluten's documentation warns that `OutOfMemoryException` can still occur with spill-to-disk when the shuffle partition count is large, and advises reducing it[^4]. See [Memory Management](#memory-model) and [spill](#bottleneck-spill) for the Spark side. The experimental `spark.gluten.velox.offHeapBroadcastBuildRelation.enabled` (default `false`) stores broadcast build relations off-heap instead of on-heap[^3].

## Joins and shuffle

The columnar shuffle is on by default (`spark.gluten.sql.columnar.shuffle`, `true`) and its codec, set with `spark.gluten.sql.columnar.shuffle.codec`, supports lz4 and zstd[^2]. For joins, `spark.gluten.sql.columnar.forceShuffledHashJoin` defaults to `true`, and separate switches control the columnar sort-merge join (`spark.gluten.sql.columnar.sortMergeJoin`, which "should be set with preferSortMergeJoin=false"), the broadcast join and the broadcast exchange[^2]. The strategy-selection rules on the [Join Optimization](#joins) page describe vanilla Spark's choices, so verify the physical plan of a Gluten job rather than assuming them.

## Fallback

Gluten falls back to vanilla Spark in several documented cases:

- ANSI mode: "If ANSI is enabled, Spark plan's execution will always fall back to vanilla Spark."[^4]
- File formats: Gluten fully supports Parquet and partially supports ORC, and the scan falls back for other formats[^4].
- Partitioned table scans need the partition information in the file path, and without it the scan falls back[^4].
- Bucket writes are not supported and fall back[^4].
- Parquet scans of the Byte type fall back[^4].

Two settings tune fallback. `spark.gluten.sql.columnar.query.fallback.threshold` (default `-1`) is the threshold for whether a query falls back, counted from the number of `ColumnarToRow` and vanilla leaf nodes. `spark.gluten.sql.columnar.fallback.expressions.threshold` (default `50`) falls back a filter or project when the number of nested expressions reaches it, because Spark codegen can be faster in that case[^2].

## Seeing where it ran

To see what can be offloaded and why a part fell back, the getting-started guide says to disable AQE (`spark.sql.adaptive.enabled=false`) so that plan validation runs in Gluten, then read the physical plan with `explain()`[^3]. In that plan, the symbol `^` marks a plan offloaded to Velox in a stage, and `VeloxColumnarToRowExec` or `GlutenRowToArrowColumnar` indicates a fallback operator before or after it[^3]. A helper, `df.fallbackSummary` from `org.apache.spark.sql.execution.GlutenImplicits`, returns the fallback summary of a Dataset[^3].

## Known incompatibilities

Gluten supports only Spark's default case-insensitive mode, and enabling case-sensitive mode can give incorrect results. Velox does not support NaN, so comparisons involving NaN can give unexpected results, and it handles only double-quoted strings in JSON data. Gluten ignores `spark.sql.parquet.datetimeRebaseModeInRead`, and "not all parquet configurations are honored"[^4].

## Engines built on Gluten

**Microsoft Fabric native execution engine.** Fabric's engine is based on two open-source components, Velox and Apache Gluten. Supported operators are offloaded from the JVM to a vectorized C++ execution path, and Fabric keeps its Spark query optimizations, including AQE[^5]. When a query can't run natively the operation falls back to the traditional Spark engine automatically, and plan nodes with a `Transformer` suffix, `*NativeFileScan` or `VeloxColumnarToRowExec` show native execution[^5]. It is enabled through the environment's acceleration setting or `spark.native.enabled`, it doesn't support structured streaming, doesn't accelerate queries against JSON and XML, and on Runtime 1.3 falls back to vanilla Spark when ANSI SQL mode is on[^5]. Fabric describes it as suited to computationally intensive queries rather than simple or I/O-bound ones[^5].

**Google Cloud native query execution.** Google's native query execution is a native engine based on Apache Gluten and Velox that runs parts of a Spark query outside the JVM. It is enabled by setting `spark.dataproc.lightningEngine.runtime` to `native`[^6][^7]. It falls back to standard Spark when ANSI mode is enabled, when case-sensitive mode is enabled, or when partitioned table scans lack partition information in the path[^6].

## Confidence

The settings, defaults and fallback cases above are taken from Gluten's own configuration reference, getting-started guide and limitations page on its main branch, and from the Fabric and Google Cloud documentation for the managed engines. Defaults in the configuration reference can change between Gluten releases, so confirm a setting against the release you run. The plan-reading guidance is documented for the Velox backend only.

## Limitations / false-positive risk

Fallback is per operator: a mostly native plan can still contain fallback operators, each marked by a transition operator in the plan[^3]. Diagnosing fallbacks means disabling AQE[^3], so the plan you inspect is a diagnostic view, not the AQE-enabled plan your production runs use (see [Adaptive Query Execution](#aqe)). Fabric and Google Cloud document their own limits separately, and those differ from Gluten's.

## Sources

[^1]: [Apache Gluten documentation](https://raw.githubusercontent.com/apache/gluten/main/docs/index.md)
[^2]: [Apache Gluten configuration](https://raw.githubusercontent.com/apache/gluten/main/docs/Configuration.md)
[^3]: [Apache Gluten: Velox backend getting started](https://raw.githubusercontent.com/apache/gluten/main/docs/get-started/Velox.md)
[^4]: [Apache Gluten: Velox backend limitations](https://raw.githubusercontent.com/apache/gluten/main/docs/velox-backend-limitations.md)
[^5]: [Native execution engine for Fabric Data Engineering](https://learn.microsoft.com/en-us/fabric/data-engineering/native-execution-engine-overview)
[^6]: [Native query execution (Google Cloud managed Spark service)](https://docs.cloud.google.com/dataproc-serverless/docs/guides/native-query-execution)
[^7]: [Spark properties (Google Cloud managed Spark service)](https://docs.cloud.google.com/dataproc-serverless/docs/concepts/properties)
