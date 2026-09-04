from pathlib import Path
p = Path('native/mobile/CMakeLists.txt')
s = p.read_text()
anchor = '  semantic_consolidation_kernel.c\n'
if '  semantic_consolidation_state.c\n' not in s:
    s = s.replace(anchor, anchor + '  semantic_consolidation_state.c\n', 1)

test_anchor = '''  add_executable(memoria_semantic_consolidation_kernel_test tests/semantic_consolidation_kernel.c semantic_consolidation_kernel.c)\n  target_include_directories(memoria_semantic_consolidation_kernel_test PRIVATE ${CMAKE_CURRENT_LIST_DIR})\n  set_target_properties(memoria_semantic_consolidation_kernel_test PROPERTIES C_STANDARD 11 C_STANDARD_REQUIRED YES)\n  add_test(NAME memoria_semantic_consolidation_kernel_test COMMAND memoria_semantic_consolidation_kernel_test)\n'''
addition = test_anchor + '''\n  add_executable(memoria_semantic_consolidation_state_test tests/semantic_consolidation_state.c semantic_consolidation_state.c semantic_consolidation_kernel.c lineage_state.c lineage_adapter.c lineage_kernel.c)\n  target_include_directories(memoria_semantic_consolidation_state_test PRIVATE ${CMAKE_CURRENT_LIST_DIR})\n  set_target_properties(memoria_semantic_consolidation_state_test PROPERTIES C_STANDARD 11 C_STANDARD_REQUIRED YES)\n  add_test(NAME memoria_semantic_consolidation_state_test COMMAND memoria_semantic_consolidation_state_test)\n'''
if 'memoria_semantic_consolidation_state_test' not in s:
    if test_anchor not in s:
        raise SystemExit('test anchor not found')
    s = s.replace(test_anchor, addition, 1)
p.write_text(s)
