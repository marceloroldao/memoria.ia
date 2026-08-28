cmake_minimum_required(VERSION 3.22)
project(memoria_mobile LANGUAGES C CXX)

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
  memoria_mobile.c
  mobile_persistence.c
  semantic_kernel.c
  episodic_kernel.c
  relation_extractor.c
  relation_adapter.c
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

  add_executable(memoria_semantic_kernel_test tests/semantic_kernel.c semantic_kernel.c)
  target_include_directories(memoria_semantic_kernel_test PRIVATE ${CMAKE_CURRENT_LIST_DIR})
  set_target_properties(memoria_semantic_kernel_test PROPERTIES C_STANDARD 11 C_STANDARD_REQUIRED YES)
  add_test(NAME memoria_semantic_kernel_test COMMAND memoria_semantic_kernel_test)

  add_executable(memoria_episodic_kernel_test tests/episodic_kernel.c episodic_kernel.c)
  target_include_directories(memoria_episodic_kernel_test PRIVATE ${CMAKE_CURRENT_LIST_DIR})
  set_target_properties(memoria_episodic_kernel_test PROPERTIES C_STANDARD 11 C_STANDARD_REQUIRED YES)
  add_test(NAME memoria_episodic_kernel_test COMMAND memoria_episodic_kernel_test)

  add_executable(memoria_relation_extractor_test tests/relation_extractor.c relation_extractor.c)
  target_include_directories(memoria_relation_extractor_test PRIVATE ${CMAKE_CURRENT_LIST_DIR})
  set_target_properties(memoria_relation_extractor_test PROPERTIES C_STANDARD 11 C_STANDARD_REQUIRED YES)
  add_test(NAME memoria_relation_extractor_test COMMAND memoria_relation_extractor_test)

  add_executable(memoria_relation_adapter_test tests/relation_adapter.c relation_adapter.c relation_extractor.c)
  target_include_directories(memoria_relation_adapter_test PRIVATE ${CMAKE_CURRENT_LIST_DIR})
  set_target_properties(memoria_relation_adapter_test PROPERTIES C_STANDARD 11 C_STANDARD_REQUIRED YES)
  add_test(NAME memoria_relation_adapter_test COMMAND memoria_relation_adapter_test)
endif()
