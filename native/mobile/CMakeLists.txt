cmake_minimum_required(VERSION 3.22)
project(memoria_mobile C)

enable_testing()

add_library(memoria_mobile SHARED memoria_mobile.c semantic_kernel.c)
target_include_directories(memoria_mobile PUBLIC ${CMAKE_CURRENT_LIST_DIR}/../../include ${CMAKE_CURRENT_LIST_DIR})
set_target_properties(memoria_mobile PROPERTIES C_STANDARD 11 C_STANDARD_REQUIRED YES)

if(NOT ANDROID)
  add_executable(memoria_mobile_smoke tests/smoke.c)
  target_link_libraries(memoria_mobile_smoke PRIVATE memoria_mobile)
  target_include_directories(memoria_mobile_smoke PRIVATE ${CMAKE_CURRENT_LIST_DIR}/../../include)
  add_test(NAME memoria_mobile_smoke COMMAND memoria_mobile_smoke)

  add_executable(memoria_semantic_kernel_smoke tests/semantic_kernel_smoke.c)
  target_link_libraries(memoria_semantic_kernel_smoke PRIVATE memoria_mobile)
  target_include_directories(memoria_semantic_kernel_smoke PRIVATE ${CMAKE_CURRENT_LIST_DIR})
  add_test(NAME memoria_semantic_kernel_smoke COMMAND memoria_semantic_kernel_smoke)
endif()
