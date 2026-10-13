CXX ?= g++
CXXFLAGS ?= -std=c++17 -O2
# Ensure local headers are found by adding the repository root to the include
# search path.
CXXFLAGS += -MMD -MP -I.

# Include shared utilities for energy lookup
SRC = BCHvsHamming.cpp Hamming32bit1Gb.cpp Hamming64bit128Gb.cpp SAT.cpp PracticalSRAMSimulator.cpp \
      src/energy_loader.cpp src/bch63.cpp
OBJ = $(SRC:.cpp=.o)
DEP = $(OBJ:.o=.d)

BINARIES = BCHvsHamming Hamming32bit1Gb Hamming64bit128Gb SATDemo PracticalSRAMSimulator

all: $(BINARIES)

%.o: %.cpp
	$(CXX) $(CXXFLAGS) -c $< -o $@

BCHvsHamming: BCHvsHamming.o src/bch63.o
	$(CXX) $(CXXFLAGS) $^ -o $@

Hamming32bit1Gb: Hamming32bit1Gb.o
	$(CXX) $(CXXFLAGS) $< -o $@

Hamming64bit128Gb: Hamming64bit128Gb.o src/energy_loader.o
	$(CXX) $(CXXFLAGS) $^ -o $@

SATDemo: SAT.o
	$(CXX) $(CXXFLAGS) $< -o $@

PracticalSRAMSimulator: PracticalSRAMSimulator.o
	$(CXX) $(CXXFLAGS) $< -o $@

ifeq ($(OS),Windows_NT)
clean:
	powershell.exe -NoProfile -Command "$$files = @('BCHvsHamming.exe','Hamming32bit1Gb.exe','Hamming64bit128Gb.exe','SATDemo.exe','PracticalSRAMSimulator.exe','BCHvsHamming.o','Hamming32bit1Gb.o','Hamming64bit128Gb.o','SAT.o','PracticalSRAMSimulator.o','src/energy_loader.o','src/bch63.o','BCHvsHamming.d','Hamming32bit1Gb.d','Hamming64bit128Gb.d','SAT.d','PracticalSRAMSimulator.d','src/energy_loader.d','src/bch63.d','tests/unit/SecDaec64_test.exe','tests/unit/SecDaec64_test.d'); $$files | Where-Object { Test-Path -LiteralPath $$_ -PathType Leaf } | ForEach-Object { Remove-Item -Force -LiteralPath $$_ }; if ($$files | Where-Object { Test-Path -LiteralPath $$_ -PathType Leaf }) { exit 1 }"
else
clean:
	rm -f $(BINARIES) $(OBJ) $(DEP) tests/unit/SecDaec64_test tests/unit/SecDaec64_test.d
endif

-include $(DEP)

.PHONY: all help setup test smoke reviewer-smoke artifact-check docs-check reproduce reproduce-iscas lint clean clean-build gtest safeforge-decisive verify-ecc-math validate-ecc-math

help:
	@echo "GREENS reproducibility targets"
	@echo "  make                 Build the C++17 simulators"
	@echo "  make setup           Install Python dependencies into the active environment"
	@echo "  make test            Build and run the established native/Python test contract"
	@echo "  make reviewer-smoke  Run a small deterministic ECC and artifact-integrity check"
	@echo "  make smoke           Alias for reviewer-smoke"
	@echo "  make artifact-check  Validate canonical manifests, IDs, and local links"
	@echo "  make docs-check      Validate documentation and artifact links without rebuilding"
	@echo "  make reproduce       Rebuild the established registry study and documentation"
	@echo "  make reproduce-iscas  Derive ISCAS claims from frozen scientific evidence"
	@echo "  make lint            Compile maintained Python entry points"
	@echo "  make clean           Remove only local native build products"

setup:
	python -m pip install -r requirements.txt

artifact-check:
	python scripts/check_artifact.py

docs-check:
	python scripts/check_artifact.py --links-only

reviewer-smoke: artifact-check
	python eccsim.py ecc verify --implementation hsiao-generated-combinational-72-64-v1
	python eccsim.py sram simulate --size-kb 64 --word-bits 8 --scheme sec-ded --iterations 100 --seed 17 --json
	python -m pytest -q tests/python/test_artifact_integrity.py tests/python/test_sram_cli.py

smoke: reviewer-smoke

reproduce:
	python scripts/build_documentation.py

reproduce-iscas:
	python scripts/reproduce_iscas.py

lint:
	python -m compileall -q green_ecc_phy ml validation scripts/check_artifact.py

clean-build: clean

# Build and run C++ unit tests without relying on CMake or external gtest
gtest: tests/unit/SecDaec64_test
	./tests/unit/SecDaec64_test

# Build unit test without -O2 to avoid UB-sensitive crashes on some toolchains
tests/unit/SecDaec64_test: tests/unit/SecDaec64_test.cpp SecDaec64.hpp BitVector.hpp ParityCheckMatrix.hpp telemetry.hpp
	$(CXX) -std=c++17 -O0 -I. $< -o $@

test: all gtest
ifeq ($(OS),Windows_NT)
	if not exist BCHvsHamming.exe exit /b 1
	if not exist Hamming32bit1Gb.exe exit /b 1
	if not exist Hamming64bit128Gb.exe exit /b 1
	if not exist SATDemo.exe exit /b 1
	python ecc_selector.py 1e-6 2 0.6 1e-15 1 --sustainability >NUL
	set PYTHONPATH=.&& pytest -q tests/python
else
	python tests/smoke_test.py
	PYTHONPATH=. pytest -q tests/python
endif

epc-report:
	python parse_telemetry.py --csv $(CSV) --node $(NODE) --vdd $(VDD)

safeforge-decisive:
	python scripts/run_safeforge_decisive_study.py --config configs/safeforge_decisive_72.json --outdir reports/safeforge_decisive_72

verify-ecc-math:
	python scripts/verify_ecc_mathematics.py --all --output docs/date2027/rigour_gate_02

validate-ecc-math:
	python scripts/verify_ecc_mathematics.py --validate-only --output docs/date2027/rigour_gate_02
