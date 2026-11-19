from mcp_task_runner.benchmarks import BenchmarkObservation, summarize_observations


def test_benchmark_summary_scores_completion_structure_tools_and_verification():
    summary = summarize_observations(
        [
            BenchmarkObservation("task", "model@gateway-a", True, True, True, True, 100, 0.01),
            BenchmarkObservation("task", "model@gateway-a", False, False, False, False, 200, 0.02, error="bad"),
        ]
    )
    assert summary.task_count == 2
    assert summary.completion_rate == 0.5
    assert summary.structured_rate == 0.5
    assert "completion_below_baseline" in summary.signals
    assert summary.score < 80
