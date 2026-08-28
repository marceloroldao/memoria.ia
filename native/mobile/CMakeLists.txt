cmake_minimum_required(VERSION 3.22)
project(memoria_mobile C)

add_library(memoria_mobile SHARED memoria_mobile.c)
target_include_directories(memoria_mobile PUBLIC ${CMAKE_CURRENT_LIST_DIR}/../../include)
set_target_properties(memoria_mobile PROPERTIES C_STANDARD 11 C_STANDARD_REQUIRED YES)
