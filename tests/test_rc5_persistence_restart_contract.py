from pathlib import Path


def test_rc5_persistence_restart_contract() -> None:
    root = Path(__file__).resolve().parents[1]
    source = (root / "native" / "mobile" / "tests" / "lineage_state.c").read_text(encoding="utf-8")
    cmake = (root / "native" / "mobile" / "CMakeLists.txt").read_text(encoding="utf-8")

    # Persist data and force a durable sync before shutdown.
    assert "memoria_persistence_sync(p) == 1" in source

    # A real close/reopen cycle must occur against the same data path/org.
    first_close = source.index("memoria_persistence_close(p);")
    reopen = source.index('memoria_persistence_open(path, "org-lineage-state", &p) == 1', first_close)
    assert reopen > first_close

    # After reopening, active/superseded lineage state must still be resolved.
    after_reopen = source[reopen:]
    assert 'resolve_expect(p, "derived", 0)' in after_reopen
    assert 'resolve_expect(p, "b-new", 1)' in after_reopen

    # The native restart test must remain part of the mobile test build.
    assert "add_executable(memoria_mobile_lineage_state tests/lineage_state.c)" in cmake
    assert "target_link_libraries(memoria_mobile_lineage_state PRIVATE memoria_mobile)" in cmake
