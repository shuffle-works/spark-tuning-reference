# Memory Utilization

<span class="tag">MEM</span>

## What it is

An executor's memory is a fixed allocation. `spark.executor.memory` sets the amount of memory per executor process, which is its JVM heap[^2]. On YARN and Kubernetes the container or pod also carries `spark.executor.memoryOverhead` on top, plus any off-heap and PySpark memory[^2]. The executor holds the whole allocation for its entire lifetime, whether or not it has work to run[^3]. This finding checks how well that allocation is used, from three angles: how close each executor's heap came to its limit, how much allocated memory-time went unused over the run, and how many cores sat idle in held executors.

The heap check reads Spark's peak heap metric. Executor metrics are sent from each executor to the driver with its heartbeat, and the per-executor peak of `JVMHeapMemory` is the highest used heap the executor reported. "Used" there counts "the amount of memory occupied by both live objects and garbage objects that have not been collected"[^6]. The finding compares that peak with `spark.executor.memory`. The metric reaches the event log only when `spark.eventLog.logStageExecutorMetrics` is true[^6].

The core check is about concurrency. An executor's core count is its concurrency ceiling: `--executor-cores 5` caps it at five concurrent tasks[^1]. The scheduler turns cores into task slots from `spark.executor.cores` and `spark.task.cpus`, which defaults to one core per task[^2]. Cores go idle whenever there are fewer runnable tasks than slots: a stage with fewer partitions than total slots leaves slots empty, and so does the tail of a stage where a [straggler](#bottleneck-straggler) or two keep running after their peers finish. Through all of it the JVM keeps its fixed heap[^3].

## How it's detected

| Rule | Fires when | Status |
|---|---|---|
| heapNearCapacity | An executor's peak heap is above 95% of `spark.executor.memory` (memory may be too small) | Validated |
| heapOverProvisioned | An executor's peak heap is below 70% of `spark.executor.memory` (memory may be over-provisioned, a cost signal) | Validated |
| idleCores | More than 50% of the available core-time ran no task | Validated |
| wasteModel | Allocated memory-time exceeds used memory-time by more than 1.5 times | Experimental |

Both heap rules look at executors one at a time, so a run can produce one finding per executor. Driver memory is not evaluated. If the log carries no per-executor memory metrics, the heap rules cannot run, and the finding says so and points at `spark.eventLog.logStageExecutorMetrics` instead.

## Why it matters

The two heap bands are opposite problems.

A heap near its limit leaves tasks little room. When a sort or hash-aggregation operator keeps asking for execution memory it cannot get, Spark blocks the task, spills its in-memory data to disk, or in the worst case throws an `OutOfMemoryError`[^3]. A full GC invoked several times before a task completes means there isn't enough memory for executing tasks[^7].

A heap far below its limit is the opposite: allocation you pay for without using it. On YARN that is the memory YARN grants the container; on Kubernetes it is the pod memory limit[^3]. Idle cores and lingering executors cost the same way, since the fixed band is reserved whether or not tasks are running.

## How to fix it

### Heap near capacity

Check first whether the pressure is real. The peak counts uncollected garbage, so a high reading alone does not prove a shortage[^6]. Look at [spill](#bottleneck-spill) and [GC pressure](#bottleneck-gc) for the same executor and stages. Spill, or heavy GC with repeated full collections, points at a real shortage[^7].

If it is real, there are three levers:

- Raise `spark.executor.memory`. The container request is the sum of `spark.executor.memoryOverhead`, `spark.executor.memory`, `spark.memory.offHeap.size` and `spark.executor.pyspark.memory`, so the cluster must have room for the larger total[^2].
- Shrink what each task holds. When the working set of a task is too large, such as a reduce task building a hash table, the simplest fix is to raise the level of parallelism so each task's input set is smaller[^7].
- Run fewer tasks per executor. Each task may take roughly between `1/(2n)` and `1/n` of execution memory with `n` tasks running, so lowering `spark.executor.cores` raises each task's share[^3].

A heap finding does not cover memory outside the heap. A container killed for exceeding its memory limit shows up as a container-memory error rather than a Spark exception, and the fix there is overhead sizing, covered on the [memory management](#memory-model) page[^3].

### Heap over-provisioned

Lower `spark.executor.memory` toward the observed peak, in steps, and re-check spill and GC after each change. The unified execution and storage region is a fraction of the heap (`spark.memory.fraction` of the heap minus 300 MiB), so a smaller heap shrinks it in proportion[^7]. Because per-task execution memory shrinks with it, a heap cut too far trades the cost signal for spill[^3]. Cached data lives in that region too, so a job that persists large datasets needs the headroom its [cache](#caching) will use.

### Idle cores and held executors

Keep executors from being oversized in the first place. Assigning all 16 cores of a node to a single executor hurts HDFS throughput and drives excessive [garbage collection](#bottleneck-gc), so aim for a balance between tiny (one core per executor) and fat (one executor per node) sizing[^4]. On YARN, leave cores for the OS and Hadoop daemons instead of handing 100% of a node to Spark containers[^1].

For the held memory band, lean on [dynamic allocation](#cluster-config) to reclaim executors once the work drains. It requests executors when tasks back up and frees them when they go idle[^1]. Executors are added in rounds once tasks have been pending for `spark.dynamicAllocation.schedulerBacklogTimeout` (default 1s), then again every `spark.dynamicAllocation.sustainedSchedulerBacklogTimeout` while the backlog holds[^5]. On the release side, an executor is removed after it has been idle longer than `spark.dynamicAllocation.executorIdleTimeout`[^5].

Cached data is the trap here. By default an executor holding [cached blocks](#caching) is never removed, governed by `spark.dynamicAllocation.cachedExecutorIdleTimeout`, whose default is infinity[^2]. Such an executor keeps its full memory band indefinitely with no active tasks unless you set that timeout to a finite value, or turn on `spark.shuffle.service.fetch.rdd.enabled` so executors holding only disk-persisted blocks are treated as idle after `spark.dynamicAllocation.executorIdleTimeout` and released[^5]. To avoid holding barely-used executors at all, lower `spark.dynamicAllocation.executorAllocationRatio` (default 1.0, full parallelism) toward 0.5, since with small tasks full-parallelism allocation can request executors that never do any work[^2].

```properties
# Balanced executor sizing, not one fat executor per node
spark.executor.cores=5

# Reclaim idle executors; give cached holders a finite timeout
spark.dynamicAllocation.enabled=true
spark.dynamicAllocation.cachedExecutorIdleTimeout=300s
spark.dynamicAllocation.executorAllocationRatio=0.5
```

### Reading the wasted-memory estimate <span class="tag">EXPERIMENTAL</span>

The wasteModel rule compares two memory-time figures. Allocated memory-time is the executor memory multiplied by the number of executors and the run duration. Used memory-time approximates the allocation as in use for as long as tasks ran, taking executor memory multiplied by the total task run time. The rule fires when the difference exceeds 1.5 times the used figure. Treat it as a rough buffer heuristic, not a measurement. It prices time with no task running, not bytes of heap left empty, so it can disagree with the heap bands: an executor can be busy all run with a half-empty heap, or idle with a full one. Use the number as a hint that the cluster may be oversized or underused, then confirm against sizing before acting on it.

## Confidence

The idleCores rule and both heap rules are validated: they rest on documented Spark concurrency, dynamic-allocation and heap-metric behavior. The wasteModel estimate is low-confidence and experimental. It is a buffer heuristic derived from allocated-versus-run-time accounting, not an exact measure of unused memory, so it should steer investigation rather than settle it.

## Limitations / false-positive risk

The heap peak counts garbage the JVM has not collected yet[^6], so heapNearCapacity can fire on an executor that never ran short of memory. Confirm with spill and GC time before raising memory. The peak is also only as fine-grained as the metric polling. With `spark.executor.metrics.pollingInterval` at its default of 0, metrics are collected on executor heartbeats, at `spark.executor.heartbeatInterval`[^2], so a short spike between heartbeats can go unseen and heapOverProvisioned can understate real use. The heap ratio sees only the heap: overhead, off-heap and PySpark memory are outside it[^2].

Idle cores are not always waste. The tail of a stage legitimately leaves slots empty while a straggler or two finish[^2], so a snapshot of low parallelism can reflect a normal straggler tail rather than chronic under-utilization. Executor metrics are absent entirely unless `spark.eventLog.logStageExecutorMetrics` is enabled[^6].

[^1]: [How to Tune Your Apache Spark Jobs (Part 2)](https://blog.cloudera.com/how-to-tune-your-apache-spark-jobs-part-2/)
[^2]: [Configuration — Spark](https://spark.apache.org/docs/latest/configuration.html)
[^3]: [Dive into Spark memory](https://luminousmen.com/post/dive-into-spark-memory)
[^4]: [Distribution of executors, cores and memory for a Spark application](https://raw.githubusercontent.com/spoddutur/spark-notes/master/distribution_of_executors_cores_and_memory_for_spark_application.md)
[^5]: [Job Scheduling — Spark](https://spark.apache.org/docs/latest/job-scheduling.html)
[^6]: [Monitoring — Spark](https://spark.apache.org/docs/latest/monitoring.html)
[^7]: [Tuning Spark](https://spark.apache.org/docs/latest/tuning.html)
