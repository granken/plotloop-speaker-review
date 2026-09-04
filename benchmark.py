import timeit
from pathlib import Path

def run_baseline(outputs, confirmed_by_target, batch_id):
    batch = {"batch_id": batch_id}
    # Mocking these to do nothing for the benchmark of the loop itself
    def write_review_artifact(t, b, r): return f"artifact_{t}"
    def write_completion_signal(t, b, to, a): return f"signal_{t}"

    for target_value, reviews in confirmed_by_target.items():
        target = Path(target_value)
        target_outputs = [output for output in outputs if str(Path(output["transcript"]).parent) == target_value]
        artifact = write_review_artifact(target, batch["batch_id"], reviews)
        signal = write_completion_signal(target, batch["batch_id"], target_outputs, artifact)
        batch.setdefault("review_artifacts", []).append(str(artifact))
        batch.setdefault("completion_signals", []).append(str(signal))
    return batch

def run_optimized(outputs, confirmed_by_target, batch_id):
    batch = {"batch_id": batch_id}
    def write_review_artifact(t, b, r): return f"artifact_{t}"
    def write_completion_signal(t, b, to, a): return f"signal_{t}"

    outputs_by_target = {}
    for output in outputs:
        parent_dir = str(Path(output["transcript"]).parent)
        outputs_by_target.setdefault(parent_dir, []).append(output)

    for target_value, reviews in confirmed_by_target.items():
        target = Path(target_value)
        target_outputs = outputs_by_target.get(target_value, [])
        artifact = write_review_artifact(target, batch["batch_id"], reviews)
        signal = write_completion_signal(target, batch["batch_id"], target_outputs, artifact)
        batch.setdefault("review_artifacts", []).append(str(artifact))
        batch.setdefault("completion_signals", []).append(str(signal))
    return batch

if __name__ == "__main__":
    num_targets = 100
    num_outputs = 1000

    targets = [f"/path/to/target_{i}" for i in range(num_targets)]
    confirmed_by_target = {t: ["review1", "review2"] for t in targets}

    outputs = []
    for i in range(num_outputs):
        outputs.append({"transcript": f"{targets[i % num_targets]}/transcript_{i}.txt"})

    batch_id = "BATCH_1"

    print("Benchmarking Baseline...")
    baseline_time = timeit.timeit(lambda: run_baseline(outputs, confirmed_by_target, batch_id), number=10)
    print(f"Baseline Time: {baseline_time:.4f} seconds")

    print("Benchmarking Optimized...")
    optimized_time = timeit.timeit(lambda: run_optimized(outputs, confirmed_by_target, batch_id), number=10)
    print(f"Optimized Time: {optimized_time:.4f} seconds")
    print(f"Improvement: {(baseline_time / optimized_time):.2f}x")
