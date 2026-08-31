cmake_minimum_required(VERSION 3.22)
project(memoria_mobile LANGUAGES C CXX)

set(CMAKE_POSITION_INDEPENDENT_CODE ON)
enable_testing()

set(MEMORIA_BDR_ROOT "" CACHE PATH "Path to the pinned Resolutive-DB checkout")
if(NOT MEMORIA_BDR_ROOT)
  message(FATAL_ERROR "MEMORIA_BDR_ROOT is required for durable mobile state")
endif()

add_subdirectory(
  "${MEMORIA_BDR_ROOT}/experimental/api_v86"
  "${CMAKE_BINARY_DIR}/bdr-v1"
  EXCLUDE_FROM_ALL
)

add_library(memoria_mobile SHARED
  memoria_mobile_post_v1.c
  semantic_kernel.c
  subconscious_kernel.c
  subconscious_mobile.c
  trajectory_kernel.c
  trajectory_json_adapter.c
  episodic_kernel.c
  temporal_state_kernel.c
  temporal_state_adapter.c
  relation_extractor.c
  relation_adapter.c
  diagnostic_export.c
)
target_include_directories(memoria_mobile PUBLIC ${CMAKE_CURRENT_LIST_DIR}/../../include ${CMAKE_CURRENT_LIST_DIR})
target_link_libraries(memoria_mobile PRIVATE bdr_atomic_c_api)
set_target_properties(memoria_mobile PROPERTIES C_STANDARD 11 C_STANDARD_REQUIRED YES LINKER_LANGUAGE CXX)

if(NOT ANDROID)
  add_executable(memoria_mobile_smoke tests/smoke.c)
  target_link_libraries(memoria_mobile_smoke PRIVATE memoria_mobile)
  target_include_directories(memoria_mobile_smoke PRIVATE ${CMAKE_CURRENT_LIST_DIR}/../../include)
  add_test(NAME memoria_mobile_smoke COMMAND memoria_mobile_smoke)

  add_executable(memoria_mobile_restart tests/restart.c)
  target_link_libraries(memoria_mobile_restart PRIVATE memoria_mobile)
  target_include_directories(memoria_mobile_restart PRIVATE ${CMAKE_CURRENT_LIST_DIR}/../../include)
  add_test(NAME memoria_mobile_restart COMMAND memoria_mobile_restart)

  add_executable(memoria_mobile_dynamic_turn_capacity tests/dynamic_turn_capacity.c)
  target_link_libraries(memoria_mobile_dynamic_turn_capacity PRIVATE memoria_mobile)
  target_include_directories(memoria_mobile_dynamic_turn_capacity PRIVATE ${CMAKE_CURRENT_LIST_DIR}/../../include)
  add_test(NAME memoria_mobile_dynamic_turn_capacity COMMAND memoria_mobile_dynamic_turn_capacity)

  add_executable(memoria_mobile_trajectory tests/trajectory_mobile.c)
  target_link_libraries(memoria_mobile_trajectory PRIVATE memoria_mobile)
  target_include_directories(memoria_mobile_trajectory PRIVATE ${CMAKE_CURRENT_LIST_DIR}/../../include)
  add_test(NAME memoria_mobile_trajectory COMMAND memoria_mobile_trajectory)

  add_executable(memoria_mobile_trajectory_multisource tests/trajectory_multisource_mobile.c)
  target_link_libraries(memoria_mobile_trajectory_multisource PRIVATE memoria_mobile)
  target_include_directories(memoria_mobile_trajectory_multisource PRIVATE ${CMAKE_CURRENT_LIST_DIR}/../../include)
  add_test(NAME memoria_mobile_trajectory_multisource COMMAND memoria_mobile_trajectory_multisource)

  add_executable(memoria_mobile_temporal_state tests/temporal_state_mobile.c)
  target_link_libraries(memoria_mobile_temporal_state PRIVATE memoria_mobile)
  target_include_directories(memoria_mobile_temporal_state PRIVATE ${CMAKE_CURRENT_LIST_DIR}/../../include)
  add_test(NAME memoria_mobile_temporal_state COMMAND memoria_mobile_temporal_state)

  add_executable(memoria_mobile_diagnostic_export tests/diagnostic_export_mobile.c)
  target_link_libraries(memoria_mobile_diagnostic_export PRIVATE memoria_mobile)
  target_include_directories(memoria_mobile_diagnostic_export PRIVATE ${CMAKE_CURRENT_LIST_DIR}/../../include)
  add_test(NAME memoria_mobile_diagnostic_export COMMAND memoria_mobile_diagnostic_export)

  add_executable(memoria_mobile_correction tests/correction_mobile.c)
  target_link_libraries(memoria_mobile_correction PRIVATE memoria_mobile)
  target_include_directories(memoria_mobile_correction PRIVATE ${CMAKE_CURRENT_LIST_DIR}/../../include)
  add_test(NAME memoria_mobile_correction COMMAND memoria_mobile_correction)

  add_executable(memoria_mobile_episodic_session tests/episodic_session_mobile.c)
  target_link_libraries(memoria_mobile_episodic_session PRIVATE memoria_mobile)
  target_include_directories(memoria_mobile_episodic_session PRIVATE ${CMAKE_CURRENT_LIST_DIR}/../../include)
  add_test(NAME memoria_mobile_episodic_session COMMAND memoria_mobile_episodic_session)

  add_executable(memoria_mobile_relation_identity tests/relation_identity_mobile.c)
  target_link_libraries(memoria_mobile_relation_identity PRIVATE memoria_mobile)
  target_include_directories(memoria_mobile_relation_identity PRIVATE ${CMAKE_CURRENT_LIST_DIR}/../../include)
  add_test(NAME memoria_mobile_relation_identity COMMAND memoria_mobile_relation_identity)

  add_executable(memoria_mobile_namespace tests/namespace_mobile.c)
  target_link_libraries(memoria_mobile_namespace PRIVATE memoria_mobile)
  target_include_directories(memoria_mobile_namespace PRIVATE ${CMAKE_CURRENT_LIST_DIR}/../../include)
  add_test(NAME memoria_mobile_namespace COMMAND memoria_mobile_namespace)

  add_executable(memoria_mobile_provenance_lineage tests/provenance_lineage_mobile.c)
  target_link_libraries(memoria_mobile_provenance_lineage PRIVATE memoria_mobile)
  target_include_directories(memoria_mobile_provenance_lineage PRIVATE ${CMAKE_CURRENT_LIST_DIR}/../../include)
  add_test(NAME memoria_mobile_provenance_lineage COMMAND memoria_mobile_provenance_lineage)

  add_executable(memoria_mobile_external_public_knowledge tests/external_public_knowledge_mobile.c)
  target_link_libraries(memoria_mobile_external_public_knowledge PRIVATE memoria_mobile)
  target_include_directories(memoria_mobile_external_public_knowledge PRIVATE ${CMAKE_CURRENT_LIST_DIR}/../../include)
  add_test(NAME memoria_mobile_external_public_knowledge COMMAND memoria_mobile_external_public_knowledge)

  add_executable(memoria_semantic_kernel_test tests/semantic_kernel.c semantic_kernel.c)
  target_include_directories(memoria_semantic_kernel_test PRIVATE ${CMAKE_CURRENT_LIST_DIR})
  set_target_properties(memoria_semantic_kernel_test PROPERTIES C_STANDARD 11 C_STANDARD_REQUIRED YES)
  add_test(NAME memoria_semantic_kernel_test COMMAND memoria_semantic_kernel_test)

  add_executable(memoria_subconscious_kernel_test tests/subconscious_kernel.c subconscious_kernel.c)
  target_include_directories(memoria_subconscious_kernel_test PRIVATE ${CMAKE_CURRENT_LIST_DIR})
  set_target_properties(memoria_subconscious_kernel_test PROPERTIES C_STANDARD 11 C_STANDARD_REQUIRED YES)
  add_test(NAME memoria_subconscious_kernel_test COMMAND memoria_subconscious_kernel_test)

  add_executable(memoria_subconscious_mobile_test tests/subconscious_mobile.c subconscious_mobile.c subconscious_kernel.c)
  target_include_directories(memoria_subconscious_mobile_test PRIVATE ${CMAKE_CURRENT_LIST_DIR} ${CMAKE_CURRENT_LIST_DIR}/../../include)
  target_link_libraries(memoria_subconscious_mobile_test PRIVATE memoria_mobile)
  set_target_properties(memoria_subconscious_mobile_test PROPERTIES C_STANDARD 11 C_STANDARD_REQUIRED YES)
  add_test(NAME memoria_subconscious_mobile_test COMMAND memoria_subconscious_mobile_test)

  add_executable(memoria_trajectory_kernel_test tests/trajectory_kernel.c trajectory_kernel.c)
  target_include_directories(memoria_trajectory_kernel_test PRIVATE ${CMAKE_CURRENT_LIST_DIR})
  set_target_properties(memoria_trajectory_kernel_test PROPERTIES C_STANDARD 11 C_STANDARD_REQUIRED YES)
  add_test(NAME memoria_trajectory_kernel_test COMMAND memoria_trajectory_kernel_test)

  add_executable(memoria_trajectory_json_adapter_test tests/trajectory_json_adapter.c trajectory_json_adapter.c trajectory_kernel.c)
  target_include_directories(memoria_trajectory_json_adapter_test PRIVATE ${CMAKE_CURRENT_LIST_DIR})
  set_target_properties(memoria_trajectory_json_adapter_test PROPERTIES C_STANDARD 11 C_STANDARD_REQUIRED YES)
  add_test(NAME memoria_trajectory_json_adapter_test COMMAND memoria_trajectory_json_adapter_test)

  add_executable(memoria_episodic_kernel_test tests/episodic_kernel.c episodic_kernel.c)
  target_include_directories(memoria_episodic_kernel_test PRIVATE ${CMAKE_CURRENT_LIST_DIR})
  set_target_properties(memoria_episodic_kernel_test PROPERTIES C_STANDARD 11 C_STANDARD_REQUIRED YES)
  add_test(NAME memoria_episodic_kernel_test COMMAND memoria_episodic_kernel_test)

  add_executable(memoria_temporal_state_kernel_test tests/temporal_state_kernel.c temporal_state_kernel.c)
  target_include_directories(memoria_temporal_state_kernel_test PRIVATE ${CMAKE_CURRENT_LIST_DIR})
  set_target_properties(memoria_temporal_state_kernel_test PROPERTIES C_STANDARD 11 C_STANDARD_REQUIRED YES)
  add_test(NAME memoria_temporal_state_kernel_test COMMAND memoria_temporal_state_kernel_test)

  add_executable(memoria_temporal_state_adapter_test tests/temporal_state_adapter.c temporal_state_adapter.c temporal_state_kernel.c)
  target_include_directories(memoria_temporal_state_adapter_test PRIVATE ${CMAKE_CURRENT_LIST_DIR})
  set_target_properties(memoria_temporal_state_adapter_test PROPERTIES C_STANDARD 11 C_STANDARD_REQUIRED YES)
  add_test(NAME memoria_temporal_state_adapter_test COMMAND memoria_temporal_state_adapter_test)

  add_executable(memoria_relation_extractor_test tests/relation_extractor.c relation_extractor.c)
  target_include_directories(memoria_relation_extractor_test PRIVATE ${CMAKE_CURRENT_LIST_DIR})
  set_target_properties(memoria_relation_extractor_test PROPERTIES C_STANDARD 11 C_STANDARD_REQUIRED YES)
  add_test(NAME memoria_relation_extractor_test COMMAND memoria_relation_extractor_test)

  add_executable(memoria_relation_adapter_test tests/relation_adapter.c relation_adapter.c relation_extractor.c)
  target_include_directories(memoria_relation_adapter_test PRIVATE ${CMAKE_CURRENT_LIST_DIR})
  set_target_properties(memoria_relation_adapter_test PROPERTIES C_STANDARD 11 C_STANDARD_REQUIRED YES)
  add_test(NAME memoria_relation_adapter_test COMMAND memoria_relation_adapter_test)
endif()
