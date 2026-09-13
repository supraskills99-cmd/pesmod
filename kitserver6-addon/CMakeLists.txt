cmake_minimum_required(VERSION 3.20)
project(PESModKitserverCompat LANGUAGES CXX)
set(CMAKE_GENERATOR_PLATFORM Win32)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

add_library(PESModKitserverCompat SHARED KitserverCompat.cpp)
target_include_directories(PESModKitserverCompat PRIVATE
    ${CMAKE_SOURCE_DIR}/../include/MinHook/include
)
target_link_libraries(PESModKitserverCompat PRIVATE
    ${CMAKE_SOURCE_DIR}/../include/MinHook/lib/MinHook.x86.lib
)
set_target_properties(PESModKitserverCompat PROPERTIES
    PREFIX ""
    SUFFIX ".asi"
)
if(MSVC)
    target_compile_options(PESModKitserverCompat PRIVATE /W4 /EHsc)
endif()
