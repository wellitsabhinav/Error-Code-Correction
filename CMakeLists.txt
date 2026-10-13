cmake_minimum_required(VERSION 3.14)
project(GREENS LANGUAGES CXX)

if(POLICY CMP0135)
    cmake_policy(SET CMP0135 NEW)
endif()

# Keep the declared CMake 3.14/3.15 compatibility path.
if(CMAKE_VERSION VERSION_LESS 3.16)
    set(GREENS_GOOGLETEST_URL "https://github.com/google/googletest/archive/refs/tags/v1.16.0.zip")
    set(GREENS_GOOGLETEST_SHA256 "a9607c9215866bd425a725610c5e0f739eeb50887a57903df48891446ce6fb3c")
else()
    set(GREENS_GOOGLETEST_URL "https://github.com/google/googletest/archive/refs/tags/v1.18.0.zip")
    set(GREENS_GOOGLETEST_SHA256 "63b9c77751a5b8f492486005f67533fdc58682b67476fcb91650be5958d5195a")
endif()

include(FetchContent)
FetchContent_Declare(
    googletest
    URL ${GREENS_GOOGLETEST_URL}
    URL_HASH SHA256=${GREENS_GOOGLETEST_SHA256}
)
set(gtest_force_shared_crt ON CACHE BOOL "" FORCE)
FetchContent_MakeAvailable(googletest)

add_library(ecc_core INTERFACE)
target_include_directories(ecc_core INTERFACE
    ${CMAKE_CURRENT_SOURCE_DIR})
target_compile_features(ecc_core INTERFACE cxx_std_17)

enable_testing()

add_executable(secdaec_tests tests/unit/SecDaec64_test.cpp)
target_link_libraries(secdaec_tests PRIVATE ecc_core gtest_main)
add_test(NAME secdaec_ctest COMMAND secdaec_tests)

add_executable(bch63_tests
    tests/unit/BCH63_test.cpp
    src/bch63.cpp)
target_link_libraries(bch63_tests PRIVATE ecc_core gtest_main)
add_test(NAME bch63_ctest COMMAND bch63_tests)
