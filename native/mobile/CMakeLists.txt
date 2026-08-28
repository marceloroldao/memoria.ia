cmake_minimum_required(VERSION 3.22)
project(memoria_mobile C)

enable_testing()

add_library(memoria_mobile SHARED memoria_mobile.c semantic_kernel.c episodic_kernel.c relation_extractor.c)
target_include_directories(memoria_mobile PUBLIC ${CMAKE_CURRENT_LIST_DIR}/../../include ${CMAKE_CURRENT_LIST_DIR})
set_target_properties(memoria_mobile PROPERTIES C_STANDARD 11 C_STANDARD_REQUIRED YES)

if(NOT ANDROID)
  add_executable(memoria_mobile_smoke tests/smoke.c)
  target_link_libraries(memoria_mobile_smoke PRIVATE memoria_mobile)
  target_include_directories(memoria_mobile_smoke PRIVATE ${CMAKE_CURRENT_LIST_DIR}/../../include)
  add_test(NAME memoria_mobile_smoke COMMAND memoria_mobile_smoke)

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
endif()
