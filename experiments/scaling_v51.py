from memoria_resolutiva.scaling_benchmark import benchmark_grid


def main():
    for r in benchmark_grid():
        print(
            f"N={r.total_nodes:>7} affected={r.affected_fraction:>6.1%} "
            f"touched={r.affected_nodes:>7} inc={r.incremental_seconds:.6f}s "
            f"full={r.full_seconds:.6f}s speedup={r.speedup:.2f}x"
        )


if __name__ == "__main__":
    main()
