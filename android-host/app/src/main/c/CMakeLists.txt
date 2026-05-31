cmake_minimum_required(VERSION 3.22.1)
project(tempest_host C)

# Passed from app/build.gradle.kts:
#   PYTHON_VERSION    e.g. 3.14
#   PYTHON_PREFIX_DIR absolute path to the CPython prefix (lib/, include/)
if(NOT DEFINED PYTHON_VERSION)
    set(PYTHON_VERSION "3.14")
endif()

add_library(tempest_host SHARED tempest_host.c)

target_include_directories(tempest_host PRIVATE
    "${PYTHON_PREFIX_DIR}/include/python${PYTHON_VERSION}")

# The shim links libpython directly; loading tempest_host pulls libpython in.
target_link_directories(tempest_host PRIVATE "${PYTHON_PREFIX_DIR}/lib")
target_link_libraries(tempest_host
    log
    "python${PYTHON_VERSION}")
