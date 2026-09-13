cmake_minimum_required(VERSION 3.20)
project(PESModKits LANGUAGES CXX)
set(CMAKE_GENERATOR_PLATFORM Win32)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
add_library(PESModKits SHARED NativeKitPng.cpp)
target_include_directories(PESModKits PRIVATE ${CMAKE_SOURCE_DIR}/../include)
target_link_libraries(PESModKits PRIVATE
    ${CMAKE_SOURCE_DIR}/../include/MinHook/lib/MinHook.x86.lib
    windowscodecs
    ole32
)
set_target_properties(PESModKits PROPERTIES PREFIX "" SUFFIX ".asi")
