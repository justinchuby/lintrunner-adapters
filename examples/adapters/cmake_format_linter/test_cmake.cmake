# Sample CMake file for testing cmake-format
cmake_minimum_required(VERSION 3.10)
project(TestProject)

# Poorly formatted CMake that cmake-format should fix
set(SOURCES
main.cpp
    utils.cpp
        helper.cpp)

find_package(Threads REQUIRED)

add_executable(test_app ${SOURCES})

target_link_libraries(test_app
    PRIVATE
        Threads::Threads
)

# Function with bad formatting
function(my_function arg1 arg2)
    if(${arg1} STREQUAL "test")
        message(STATUS "Testing")
    endif()
endfunction()

my_function("test" "value")
