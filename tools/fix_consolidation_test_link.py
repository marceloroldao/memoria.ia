from pathlib import Path
p = Path('native/mobile/CMakeLists.txt')
s = p.read_text()
s = s.replace('tests/semantic_consolidation_state.c semantic_consolidation_state.c semantic_consolidation_kernel.c lineage_state.c lineage_adapter.c lineage_kernel.c', 'tests/semantic_consolidation_state.c semantic_consolidation_state.c semantic_consolidation_kernel.c lineage_adapter.c lineage_kernel.c')
p.write_text(s)
