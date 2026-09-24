cmake_minimum_required(VERSION 3.16)
project(memoria_mobile LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

if(NOT DEFINED BDR_SOURCE_DIR)
    message(FATAL_ERROR "BDR_SOURCE_DIR must point to resolutive-DB source")
endif()

add_subdirectory(${BDR_SOURCE_DIR} ${CMAKE_BINARY_DIR}/bdr-build EXCLUDE_FROM_ALL)

add_library(memoria_mobile SHARED src/mobile.cpp)
target_include_directories(memoria_mobile PUBLIC ${CMAKE_CURRENT_SOURCE_DIR}/include)
target_include_directories(memoria_mobile PRIVATE ${BDR_SOURCE_DIR}/experimental/api_v86/include)
target_link_libraries(memoria_mobile PRIVATE bdr_c)
set_target_properties(memoria_mobile PROPERTIES OUTPUT_NAME memoria_mobile)

if(NOT ANDROID)
    enable_testing()
    add_executable(memoria_mobile_contract tests/test_mobile.cpp)
    target_link_libraries(memoria_mobile_contract PRIVATE memoria_mobile)
    add_test(NAME memoria_mobile_contract COMMAND memoria_mobile_contract)
endif()
