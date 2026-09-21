"""One-time bootstrap: build questions.yaml + per-question answer files from the
current section answer files and the SECTIONS array (transcribed below).

Runs BEFORE .codex/workflows/step4-answering.js is deleted — it is the last
consumer of the SECTIONS array.

Acceptance (see main()): projecting the migrated registry back reproduces each
section's question blocks verbatim and the union of its footnote defs; the only
intended change is the H1 line (canonicalized to `# <title>`) and Sources ordering.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

from scripts.project_section import build_projection, split_sources
from scripts.registry import Registry, Section, Question, save_registry

REPO_ROOT = Path(__file__).resolve().parent.parent
ANSWERS_DIR = REPO_ROOT / "research" / "answers"
ANSWERS_Q_DIR = ANSWERS_DIR / "q"
QUESTIONS_PATH = REPO_ROOT / "research" / "questions.yaml"

_REF_RE = re.compile(r"\[\^([^\]]+)\]")

# Transcribed verbatim from .codex/workflows/step4-answering.js SECTIONS[].
# id/num/title/default_k + source_file (per docs/anchor-map.md) + questions[].
# NOTE for implementer: copy every question string exactly, including punctuation.
SECTIONS_SEED: list[dict] = [
    {"id": "3.1-introduction", "num": "3.1", "title": "Introduction",
     "default_k": 15, "source_file": "3.1-introduction.md", "questions": [
        "What is the intended mental model a practitioner should have before reading an optimization guide?",
        "What is the canonical definition of a \"straggler task\" in Spark documentation vs in the research literature? Are they the same concept?",
        "What exactly is a \"speculative task\" — what conditions trigger speculative execution, and what config controls it (spark.speculation.*)?",
     ]},
    {"id": "3.2-execution-model", "num": "3.2", "title": "Spark Execution Model",
     "default_k": 15, "source_file": "3.2-execution-model.md", "questions": [
        "What are the precise responsibilities of the Driver process? What data structures live only on the Driver?",
        "How does a Job decompose into Stages and Tasks? What exactly is the rule for stage boundary creation?",
        "Is a shuffle the only trigger for a stage boundary, or can other operations (e.g., sortBy on an RDD, checkpointing) also split stages?",
        "What is the difference between spark.default.parallelism and spark.sql.shuffle.partitions? When does each take effect — is there a priority order?",
        "What is the DAG Scheduler exact responsibility vs the Task Scheduler? Can they be run on different threads?",
        "What does \"narrow\" vs \"wide\" transformation mean formally? Is mapPartitions always narrow? Is coalesce narrow or wide?",
        "When does Spark use pipelining within a stage? Are all narrow transformations pipelined, or are there exceptions?",
     ]},
    {"id": "3.3-memory-management", "num": "3.3", "title": "Memory Management",
     "default_k": 15, "source_file": "3.3-memory-management.md", "questions": [
        "How does the Unified Memory Manager (introduced in Spark 1.6) allocate memory between execution and storage?",
        "What is the exact eviction policy when execution needs memory that storage is using? Is it LRU per block, per partition, or per RDD?",
        "Does storage memory ever evict execution memory, or is eviction unidirectional (storage to execution)?",
        "What is the formula for reserved system memory? The docs mention 300 MB — is this hardcoded or configurable?",
        "What happens step-by-step when execution memory is exhausted during a sort or hash aggregation — what is the exact spill trigger and spill path?",
        "What is the difference between spark.executor.memoryOverhead in YARN vs Kubernetes — does the meaning or formula differ?",
        "Is spark.python.worker.memory a hard limit enforced by the JVM, or just a hint? What happens when a Python worker exceeds it?",
        "What is off-heap memory (spark.memory.offHeap) used for exactly — Tungsten, storage, both? Does it affect GC pause frequency?",
        "Is spark.memory.fraction applied to total JVM heap or to JVM heap minus the 300 MB reserved memory?",
        "What is the exact behavior when spark.memory.offHeap.enabled=true but spark.memory.offHeap.size=0?",
     ]},
    {"id": "3.4-partitioning", "num": "3.4", "title": "Partitioning",
     "default_k": 15, "source_file": "3.4-partitioning.md", "questions": [
        "What is the default number of partitions after a shuffle, and what is the guidance for tuning it?",
        "When should repartition be preferred over coalesce, and vice versa?",
        "Does repartition(n) guarantee exactly n output partitions? What algorithm does it use — does it use a hash shuffle?",
        "Does coalesce(n) ever trigger a shuffle? Under what condition does it promote to a full shuffle?",
        "What is the partition sizing rule of thumb (128-256 MB per task) — where does this number come from, and does it refer to input bytes, output bytes, or compressed bytes?",
        "In the salting technique for skew, how many salt values should be used? Is there a formula relating salt count to skew ratio or partition count?",
        "When using repartition(col) for join alignment, does Spark guarantee that both DataFrames will use the same partitioner if the same column and count are specified?",
        "What is the maximum number of partitions Spark supports? Is there a practical upper limit beyond which performance degrades due to scheduling overhead?",
     ]},
    {"id": "3.5-join-optimization", "num": "3.5", "title": "Join Optimization",
     "default_k": 15, "source_file": "3.5-join-optimization.md", "questions": [
        "What join strategies does Spark SQL support, and how does the optimizer choose between them?",
        "What is the exact default for spark.sql.autoBroadcastJoinThreshold in Spark 3.x? Is it based on compressed or uncompressed table size, and where does Spark measure it (statistics, file size, or plan estimate)?",
        "When a broadcast hint is specified but the table exceeds the threshold, does Spark obey the hint or fall back to sort-merge?",
        "What is the driver memory cost of broadcasting a table — is the full table materialized on the driver before being sent to executors?",
        "Does bucketing require both tables to have the same number of buckets? What happens if bucket counts differ — is there a partial benefit?",
        "Does bucketing eliminate the sort phase of sort-merge join, or just the shuffle, or both?",
        "Can the Catalyst optimizer reorder joins automatically (join reordering)? Is spark.sql.cbo.joinReorder.enabled needed?",
        "What is the difference between BROADCAST, MERGE, SHUFFLE_HASH, and SHUFFLE_REPLICATE_NL join hints?",
        "In a skew join with manual salting, what is the correct way to handle the NULL key case so salted and non-salted rows join correctly?",
        "What is spark.sql.join.preferSortMergeJoin and when does it override broadcast threshold logic?",
     ]},
    {"id": "3.6-shuffle", "num": "3.6", "title": "Shuffle",
     "default_k": 15, "source_file": "3.6-shuffle.md", "questions": [
        "What operations trigger a shuffle in Spark SQL / DataFrame API?",
        "What is the difference between sort-based shuffle (SortShuffleManager) and hash-based shuffle? When does Spark fall back to hash-based?",
        "What is the bypass merge threshold (spark.shuffle.sort.bypassMergeThreshold)? When does Spark use the bypass path and what are the trade-offs?",
        "What does spark.shuffle.compress compress — map output, reduce input, or both? What codec is used by default?",
        "What is spark.reducer.maxSizeInFlight and what happens when a reducer tries to fetch more than this limit?",
        "What is spark.shuffle.file.buffer — what is it buffering, and when does increasing it help?",
        "Does groupBy().agg() always produce a shuffle? Are there cases where Spark can avoid it (e.g., input is already partitioned by the group key)?",
        "What is the shuffle read overhead for distinct() vs dropDuplicates(cols) — do they differ in shuffle volume?",
        "What exactly is \"external shuffle service\" (spark.shuffle.service.enabled) and when is it required vs optional?",
        "What is push-based shuffle (SPARK-30602 / Magnet) — when available, how is it enabled, and what does it improve vs classic pull shuffle?",
     ]},
    {"id": "3.7-data-formats", "num": "3.7", "title": "Data Formats",
     "default_k": 15, "source_file": "3.7-data-formats.md", "questions": [
        "What are the main structural differences between Parquet and ORC, and when should each be preferred?",
        "Does Snappy compression support block-level splitting in Parquet? If not, how does Parquet achieve parallelism despite non-splittable Snappy?",
        "What is the difference between Parquet row group size and HDFS/S3 block size, and how do they interact for task parallelism?",
        "What statistics does Parquet collect per row group (min/max, null count, bloom filters)? Which are used for predicate pushdown in Spark?",
        "What statistics does ORC collect (min/max, bloom filters, row index stride)? How does ORC predicate pushdown differ from Parquet?",
        "At what file size does the \"too many small files\" problem become measurable? Is there a task count threshold where scheduling overhead dominates?",
        "Does mergeSchema in spark.read.parquet handle type widening (e.g., int to long)? What happens on a type conflict it cannot resolve?",
        "What is Zstd compression ratio vs speed trade-off compared to Snappy for Parquet files of typical Spark workload sizes? Are there benchmark references?",
        "Why is Gzip generally discouraged for Spark inputs? Is it solely the non-splittability, or are there other factors (CPU cost, codec availability)?",
        "Parquet v1 vs v2 (parquet.writer.version) — what is the practical difference for Spark readers, and is v2 safe to enable by default?",
     ]},
    {"id": "3.8-caching-persistence", "num": "3.8", "title": "Caching & Persistence",
     "default_k": 15, "source_file": "3.8-caching-persistence.md", "questions": [
        "Under what circumstances does caching a DataFrame improve performance vs have no effect or hurt performance?",
        "What is the exact difference between df.cache() and df.persist(StorageLevel.MEMORY_AND_DISK) in Spark 3.0+? Are they identical?",
        "What are the pros and cons of df.write.format(\"noop\").mode(\"overwrite\").save() vs df.count() for forcing materialization of a cached DataFrame?",
        "Does calling df.cache() followed by df.count() guarantee that all partitions are cached, including those on executors that are not currently active?",
        "What is the eviction policy for MEMORY_AND_DISK — when does Spark decide to spill a partition to disk rather than evict it?",
        "What is the CPU/memory trade-off of MEMORY_AND_DISK_SER vs MEMORY_AND_DISK? At what data size does serialization save enough memory to be worth the CPU cost?",
        "Does checkpointing always truncate the lineage graph? What happens if the checkpoint directory is unavailable at job runtime?",
        "Is there a limit on how many DataFrames can be cached simultaneously? What is the actual eviction trigger — absolute memory bytes or fraction?",
        "What is the overhead of calling unpersist() — is it synchronous (blocks until eviction) or asynchronous by default?",
     ]},
    {"id": "3.9-pyspark-specifics", "num": "3.9", "title": "PySpark Specifics",
     "default_k": 15, "source_file": "3.9-pyspark-specifics.md", "questions": [
        "How does PySpark execute Python UDFs — what is the serialization path between the JVM and the Python worker?",
        "What is the exact per-row overhead of Pickle serialization in a Python UDF vs Arrow batch serialization in a pandas UDF? Are there published benchmarks?",
        "What is the difference between a pandas_udf of type SCALAR (Series to Series), SCALAR_ITER (Iterator[Series] to Iterator[Series]), and MAP_ITER (mapInPandas)? When should each be used?",
        "Does enabling spark.sql.execution.arrow.pyspark.enabled affect operations other than pandas UDFs (e.g., toPandas(), createDataFrame() from a pandas DataFrame)?",
        "Is pyspark.sql.functions always faster than an equivalent Python UDF? Are there documented edge cases where a UDF is competitive?",
        "What is spark.python.worker.reuse — what does it reuse, and what are the correctness risks of enabling it?",
        "What does spark.python.worker.memory control exactly — is it a per-worker limit, and what happens at the OS level when it is exceeded?",
        "What is the correct way to handle stateful operations in PySpark without row-at-a-time Python UDFs?",
     ]},
    {"id": "3.10-adaptive-query-execution", "num": "3.10", "title": "Adaptive Query Execution",
     "default_k": 15, "source_file": "3.10-adaptive-query-execution.md", "questions": [
        "What does AQE re-optimize at runtime that the static optimizer cannot?",
        "At what point in query execution are shuffle statistics available to AQE — after all map tasks complete, or incrementally?",
        "What is the exact algorithm for AQE partition coalescing — does it use a greedy bin-packing approach, and what is the target partition size (spark.sql.adaptive.advisoryPartitionSizeInBytes)?",
        "What is the exact skew detection algorithm: what are spark.sql.adaptive.skewJoin.skewedPartitionFactor and spark.sql.adaptive.skewJoin.skewedPartitionThresholdInBytes doing, and how does the split work?",
        "When AQE promotes a sort-merge join to broadcast, does it re-materialize the build side, or does it reuse the shuffle files already written?",
        "Can AQE re-optimize the same query plan multiple times (e.g., after each shuffle stage), or only once?",
        "Does disabling AQE affect query plan caching (spark.sql.cache.serializer)?",
        "Are there known cases where AQE produces a worse plan than the static optimizer? What are the failure modes?",
        "What is spark.sql.adaptive.localShuffleReader.enabled — when does AQE use a local shuffle reader and what does it avoid?",
        "Does AQE interact with Dynamic Partition Pruning (DPP)? What is the order of application — DPP first, then AQE re-optimization?",
     ]},
    {"id": "3.11-cluster-tuning", "num": "3.11", "title": "Cluster Tuning",
     "default_k": 15, "source_file": "3.11-cluster-tuning.md", "questions": [
        "What is the recommended formula for sizing Spark executors (cores x memory)?",
        "Why is <=5 cores per executor the common recommendation — what is the connection to NUMA, OS jitter, and HDFS throughput?",
        "What is the exact container memory formula for YARN: spark.executor.memory + spark.executor.memoryOverhead + spark.memory.offHeap.size? Is there an additional overhead on top?",
        "For Kubernetes, what is the difference between spark.kubernetes.executor.request.cores and spark.executor.cores? Can they be set independently, and what happens if they differ?",
        "What does spark.locality.wait control exactly — is it a timeout per level (process-local to node-local to rack-local to any)? What are spark.locality.wait.node, spark.locality.wait.rack, spark.locality.wait.process?",
        "What is the interaction between dynamic allocation and shuffle tracking (spark.dynamicAllocation.shuffleTracking.enabled)? What can go wrong if shuffle tracking is disabled?",
        "When dynamic allocation removes an executor, are its shuffle files lost? What does the external shuffle service solve here?",
        "What is the driver memory impact of a wide physical plan (many columns, deeply nested)? What is spark.driver.maxResultSize and how is it different from driver heap?",
        "Is there a documented maximum number of executors beyond which Spark scheduling overhead degrades performance?",
        "What is spark.task.cpus and when must it be set greater than 1? What is the interaction with spark.executor.cores for resource allocation?",
     ]},
    {"id": "3.12-anti-patterns", "num": "3.12", "title": "Anti-Patterns",
     "default_k": 15, "source_file": "3.12-anti-patterns.md", "questions": [
        "What are the most commonly cited Spark anti-patterns in practitioner literature?",
        "collect() on a large DataFrame — what is the exact failure path: is it the driver OOM, the serialization buffer, or network transfer that fails first?",
        "Does df.count() after a cache() guarantee full materialization? Is there any scenario where some partitions are computed but not persisted to the cache?",
        "For Python row-at-a-time UDFs: is the overhead primarily serialization (pickle), context switching, or Python interpreter overhead? Are there benchmarks separating these?",
        "spark.sql.shuffle.partitions=200 fixed: what is the observable symptom of too few partitions (spill signatures) vs too many (scheduling overhead signature) in the Spark UI?",
        "Broadcasting a table that is too large — at what point does the broadcast fail: driver OOM during collection, executor OOM during replication, or serialization timeout?",
        "Is repartition(1) before write ever correct, or is coalesce(1) always preferable when a single output file is needed?",
        "For the \"no predicate pushdown\" anti-pattern: how can a practitioner verify pushdown is happening in the physical plan (df.explain(\"formatted\"))? What keywords indicate pushdown is active?",
     ]},
    {"id": "3.13-bottleneck-reference", "num": "3.13", "title": "Bottleneck Reference",
     "default_k": 18, "source_file": "3.13-bottleneck-reference.md", "questions": [
        "Is executorRunTime (as recorded in taskMetrics) wall-clock time or CPU time? Does it include time the task is blocked on I/O?",
        "Is jvmGCTime included in executorRunTime, or is it additive? — i.e., does executorRunTime + jvmGCTime > wall-clock task time?",
        "What is peakExecutionMemory exactly — is it measured per-task or per-executor? Does it include storage memory?",
        "Does shuffleReadMetrics.remoteBytesRead include local reads (same host shuffle), or only cross-node reads?",
        "What is the exact condition Spark uses to fire a speculative task — is it based on a fraction of median task duration, a percentile, or an absolute threshold? What config controls it?",
        "For memoryBytesSpilled vs diskBytesSpilled: what is the semantic difference? Can memoryBytesSpilled > 0 with diskBytesSpilled = 0?",
        "Where exactly is SparkListenerStageSubmitted emitted in the event log — is it fired when the stage is created or when the first task is launched?",
        "For the slow-host detector: does Spark record host per task in the event log? What field name in SparkListenerTaskEnd carries the executor host?",
        "What is fetchWaitTime in task metrics — what exactly is the executor waiting for, and does it include deserialization time?",
        "What is resultSerializationTime in taskMetrics and under what workload profile does it dominate end-to-end task time?",
     ]},
    {"id": "3.14-metrics-glossary", "num": "3.14", "title": "Metrics Glossary",
     "default_k": 18, "source_file": "3.14-metrics-glossary.md", "questions": [
        "Does taskMetrics.inputMetrics.bytesRead count bytes before or after decompression?",
        "Does taskMetrics.outputMetrics.bytesWritten count bytes before or after compression?",
        "Is taskMetrics.executorRunTime available for tasks that failed, or only for successful task ends?",
        "What is the unit of taskMetrics.jvmGCTime — milliseconds? Is it cumulative across all GC events in the task?",
        "What exactly is taskMetrics.peakExecutionMemory tracking — Tungsten off-heap, on-heap execution pool, or both?",
        "Is SparkListenerExecutorAdded fired once at executor registration or every time an executor core becomes available?",
        "What is the reason field format in SparkListenerTaskEnd for different failure types — what are the canonical reason strings?",
        "Does taskMetrics.shuffleWriteMetrics.bytesWritten count bytes before or after compression, and does it include bytes spilled to disk during the shuffle write, or only the final merged output?",
        "For stage wall-clock duration, is completionTime - submissionTime (from SparkListenerStageCompleted/SparkListenerStageSubmitted) the correct pair of fields, or does Spark record a stage duration elsewhere in the event log?",
     ]},
    {"id": "3.15-config-quick-reference", "num": "3.15", "title": "Spark Config Quick-Reference",
     "default_k": 18, "source_file": "3.15-config-quick-reference.md", "questions": [
        "What is the exact default of spark.sql.shuffle.partitions in Spark 3.0+ with AQE enabled — is the effective default different when coalescing is on?",
        "What is the valid range for spark.memory.fraction? Can it be set to 0.9 safely, or are there documented failure modes above a certain threshold?",
        "What is the interaction between spark.memory.fraction and spark.memory.storageFraction — are they independent, or does one constrain the other?",
        "Does spark.sql.execution.arrow.pyspark.enabled = true have any correctness risks (e.g., type mismatches between Arrow and Spark types)?",
        "What are the valid spark.dynamicAllocation.shuffleTracking.* configs and their defaults in Spark 3.x?",
        "What is the default and valid range for spark.sql.adaptive.advisoryPartitionSizeInBytes?",
        "What is the difference between -XX:+UseG1GC and -XX:+UseZGC in terms of throughput vs pause latency trade-offs — for what Spark workload profile does ZGC win?",
        "What is the default and behavior of spark.sql.adaptive.coalescePartitions.minPartitionSize (introduced Spark 3.2+)? How does it interact with advisoryPartitionSizeInBytes?",
     ]},
]


def parse_section_file(md: str) -> tuple[str, list[tuple[str, str]]]:
    lines = md.splitlines()
    title = ""
    for line in lines:
        if line.startswith("# "):
            title = line[2:].strip()
            break
    blocks: list[tuple[str, str]] = []
    current_heading = None
    current: list[str] = []
    for line in lines:
        if line.startswith("## "):
            heading = line[3:].strip()
            if heading == "Sources":
                break
            if current_heading is not None:
                blocks.append((current_heading, "\n".join(current).rstrip() + "\n"))
            current_heading = heading
            current = [line]
        elif current_heading is not None:
            current.append(line)
    if current_heading is not None:
        blocks.append((current_heading, "\n".join(current).rstrip() + "\n"))
    return title, blocks


def used_footnotes(block: str) -> list[str]:
    seen: list[str] = []
    for m in _REF_RE.finditer(block):
        key = m.group(1)
        if key not in seen:
            seen.append(key)
    return seen


def per_question_file(block: str, section_defs: dict[str, str]) -> str:
    keys = used_footnotes(block)
    parts = [block.rstrip(), "", "## Sources", ""]
    parts.extend(section_defs[k] for k in keys if k in section_defs)
    return "\n".join(parts) + "\n"


def migrate() -> Registry:
    ANSWERS_Q_DIR.mkdir(parents=True, exist_ok=True)
    sections: list[Section] = []
    questions: list[Question] = []
    for sec in SECTIONS_SEED:
        sections.append(Section(sec["id"], sec["num"], sec["title"], sec["default_k"]))
        src = (ANSWERS_DIR / sec["source_file"]).read_text(encoding="utf-8")
        _, def_map = split_sources(src)
        _, blocks = parse_section_file(src)
        for i, (heading, block) in enumerate(blocks, start=1):
            qid = f"{sec['num']}-q{i:02d}"
            body = block.lower()
            status = "needs-review" if ("[needs-review" in body or "[unresourced" in body) else "answered"
            (ANSWERS_Q_DIR / f"{qid}.md").write_text(
                per_question_file(block, def_map), encoding="utf-8")
            questions.append(Question(qid, sec["id"], heading, "n/a", None, status))
    return Registry(sections=sections, questions=questions)


def main() -> int:
    reg = migrate()
    save_registry(reg, QUESTIONS_PATH)
    print(f"wrote {QUESTIONS_PATH}: {len(reg.sections)} sections, {len(reg.questions)} questions")
    # Acceptance check: reprojection preserves question-block bodies + footnote union.
    failures = 0
    for sec in reg.sections:
        original = (ANSWERS_DIR / next(s["source_file"] for s in SECTIONS_SEED if s["id"] == sec.id)).read_text(encoding="utf-8")
        _, orig_blocks = parse_section_file(original)
        proj = build_projection(reg, sec.id, ANSWERS_Q_DIR)
        _, proj_blocks = parse_section_file(proj)
        if [b for _, b in orig_blocks] != [b for _, b in proj_blocks]:
            print(f"  MISMATCH in {sec.id}: question bodies differ", file=sys.stderr)
            failures += 1
    print("acceptance: OK" if not failures else f"acceptance: {failures} section(s) mismatched")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
