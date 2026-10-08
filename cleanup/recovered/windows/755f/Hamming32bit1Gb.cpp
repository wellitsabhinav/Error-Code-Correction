#include <iostream>
#include <vector>
#include <bitset>
#include <random>
#include <iomanip>
#include <cassert>
#include <cmath>
#include <chrono>
#include <map>
#include <set>
#include <unordered_map>
#include <fstream>
#include <string>
#include "ParityCheckMatrix.hpp"
#include "gate_energy.hpp"

// Print design archetype guidance that helps users interpret simulator results.
static void printArchetypeReport() {
    std::cout << R"(Archetype 1: "Fortress" (Maximum Reliability)
Characteristics:
- FIT: < 1e-15 (top 5% of solutions)
- Carbon: 0.8-1.2 kg CO₂e (acceptable trade-off)
- Latency: 3-5 ns (acceptable for server applications)
- Typical ECC: LDPC, Turbo-Product codes
- Technology: 14nm-28nm (mature, reliable processes)

Target Applications:
- Mission-critical servers (financial, aerospace)
- Automotive safety systems (ISO 26262)
- Medical devices (FDA regulated)

Design Rationale:
"Maximum protection against data corruption, cost is secondary consideration"

Representative Configuration:
- Code: LDPC-256-239
- Node: 28nm
- VDD: 0.9V (conservative for reliability)
- Temperature: 25°C (active cooling)
- Scrub: 60s (aggressive error scrubbing)

Archetype 2: "Efficiency" (Balanced Trade-offs)
Characteristics:
- FIT: 1e-13 to 1e-12 (good reliability)
- Carbon: 0.3-0.6 kg CO₂e (environmentally conscious)
- Latency: 1.5-2.5 ns (good performance)
- Typical ECC: SEC-DAEC, Advanced Hamming
- Technology: 14nm (optimal efficiency point)

Target Applications:
- Enterprise servers
- Cloud computing infrastructure
- High-performance workstations

Design Rationale:
"Optimal balance across all objectives, mainstream deployment"

Representative Configuration:
- Code: SEC-DAEC-64
- Node: 14nm
- VDD: 0.8V (standard operation)
- Temperature: 75°C (typical server environment)
- Scrub: 600s (balanced scrubbing)

Archetype 3: "Frugal" (Minimum Environmental Impact)
Characteristics:
- FIT: 1e-12 to 1e-11 (acceptable reliability)
- Carbon: < 0.3 kg CO₂e (top 10% environmental performance)
- Latency: 1-2 ns (excellent performance)
- Typical ECC: SEC-DED, simple codes
- Technology: 7nm (high efficiency when properly managed)

Target Applications:
- Mobile devices
- IoT sensors
- Edge computing
- Green data centers

Design Rationale:
"Minimize environmental impact while maintaining acceptable protection"

Representative Configuration:
- Code: SEC-DED-64
- Node: 7nm
- VDD: 0.6V (ultra-low power)
- Temperature: 45°C (passive cooling)
- Scrub: 3600s (minimal scrubbing)

Archetype 4: "Speed Demon" (Maximum Performance)
Characteristics:
- FIT: 1e-13 to 1e-11 (variable reliability)
- Carbon: 0.4-0.8 kg CO₂e (performance costs carbon)
- Latency: < 1.5 ns (top 5% performance)
- Typical ECC: Simple codes, minimal overhead
- Technology: 7nm-14nm (high-speed processes)

Target Applications:
- High-frequency trading systems
- Real-time gaming/VR
- Ultra-low latency networking
- AI inference engines

Design Rationale:
"Every nanosecond counts, optimize for minimum access time"

Representative Configuration:
- Code: SEC-DED-32 (smaller words for speed)
- Node: 7nm
- VDD: 1.0V (maximum performance)
- Temperature: 85°C (aggressive operation)
- Scrub: 7200s (minimal impact on performance)

Cross-Archetype Analysis:
Trade-off Matrix:
                 Fortress  Efficiency  Frugal  Speed Demon
Reliability      ★★★★★     ★★★★        ★★★     ★★
Carbon Impact    ★★        ★★★★        ★★★★★   ★★
Performance      ★★        ★★★         ★★★★    ★★★★★
Cost            ★         ★★★         ★★★★★   ★★
Complexity      ★         ★★★         ★★★★★   ★★★★
)" << std::endl;
}

class HammingCodeSECDED {
public:
    static const int DATA_BITS = 32;
    static const int PARITY_BITS = 6;  // 2^6 = 64 >= 32 + 6 + 1
    static const int OVERALL_PARITY_BIT = 1;  // SEC-DED enhancement
    static const int TOTAL_BITS = DATA_BITS + PARITY_BITS + OVERALL_PARITY_BIT;  // 39 bits

private:
    // Parity bit positions (powers of 2): 1, 2, 4, 8, 16, 32
    const std::vector<int> parity_positions = {1, 2, 4, 8, 16, 32};
    ParityCheckMatrix pcm_;

    // Build the parity-check matrix for the code. This is called during
    // construction and whenever the configuration changes.
    void buildParityCheckMatrix() {
        pcm_.rows.clear();
        for (int parity_bit : parity_positions) {
            std::array<uint64_t,2> row{0,0};
            for (int pos = 1; pos <= TOTAL_BITS - 1; ++pos) {
                if (pos & parity_bit) {
                    int idx = pos - 1;
                    if (idx < 64)
                        row[0] |= (1ULL << idx);
                    else
                        row[1] |= (1ULL << (idx-64));
                }
            }
            pcm_.rows.push_back(row);
        }
    }

public:
    HammingCodeSECDED() { buildParityCheckMatrix(); }

    // Rebuild the parity-check matrix. This provides a reinitialisation path
    // should configuration parameters such as the word size change in future.
    void resetPCM() { buildParityCheckMatrix(); }

    // Load a parity-check matrix from an external file. Each line of the file
    // represents one row of the matrix and should contain a sequence of `0`
    // and `1` characters. Any whitespace or additional characters are
    // ignored. The number of columns is capped at TOTAL_BITS-1 as the overall
    // parity bit is not included in the syndrome calculation.
    bool loadPCMFromFile(const std::string& filename) {
        std::ifstream file(filename);
        if (!file) {
            return false;
        }
        pcm_.rows.clear();
        std::string line;
        while (std::getline(file, line)) {
            std::array<uint64_t,2> row{0,0};
            std::size_t col = 0;
            for (char c : line) {
                if (c != '0' && c != '1')
                    continue;
                if (c == '1') {
                    if (col < 64)
                        row[0] |= (1ULL << col);
                    else
                        row[1] |= (1ULL << (col - 64));
                }
                ++col;
                if (col >= TOTAL_BITS - 1)
                    break;
            }
            if (col > 0)
                pcm_.rows.push_back(row);
        }
        return !pcm_.rows.empty();
    }

    struct CodeWord {
        uint64_t data;  // 39 bits stored in 64-bit int
        
        CodeWord() : data(0) {}
        CodeWord(uint64_t d) : data(d & ((1ULL << TOTAL_BITS) - 1)) {}
        
        bool getBit(int pos) const {
            return (data >> (pos - 1)) & 1;
        }
        
        void setBit(int pos, bool value) {
            if (value) {
                data |= (1ULL << (pos - 1));
            } else {
                data &= ~(1ULL << (pos - 1));
            }
        }
        
        void flipBit(int pos) {
            data ^= (1ULL << (pos - 1));
        }
        
        int countOnes() const {
            return __builtin_popcountll(data & ((1ULL << TOTAL_BITS) - 1));
        }
    };
    
    enum ErrorType {
        NO_ERROR,
        SINGLE_ERROR_CORRECTABLE,
        DOUBLE_ERROR_DETECTABLE,
        MULTIPLE_ERROR_UNCORRECTABLE,
        OVERALL_PARITY_ERROR
    };
    
    struct DecodingResult {
        uint32_t corrected_data;
        int syndrome;
        int error_position;
        ErrorType error_type;
        bool overall_parity;
        std::string syndrome_binary;
        std::string error_type_string;
        bool data_corrected;
    };
    
    // Check if position is a parity bit position
    bool isParityPosition(int pos) const {
        return (pos & (pos - 1)) == 0 && pos <= 32;  // Check if pos is power of 2 <= 32
    }
    
    // Check if position is overall parity position
    bool isOverallParityPosition(int pos) const {
        return pos == TOTAL_BITS;  // Position 39
    }
    
    // Get data bit positions (non-parity, non-overall-parity positions)
    std::vector<int> getDataPositions() const {
        std::vector<int> positions;
        for (int i = 1; i <= TOTAL_BITS; i++) {
            if (!isParityPosition(i) && !isOverallParityPosition(i)) {
                positions.push_back(i);
            }
        }
        return positions;
    }
    
    // Encode 32-bit data into 39-bit SEC-DED Hamming codeword
    CodeWord encode(uint32_t data) const {
        CodeWord codeword;
        
        // Place data bits in non-parity positions
        std::vector<int> data_positions = getDataPositions();
        for (int i = 0; i < DATA_BITS; i++) {
            bool bit_value = (data >> i) & 1;
            codeword.setBit(data_positions[i], bit_value);
        }
        
        // Calculate and set Hamming parity bits
        for (int parity_bit : parity_positions) {
            int parity = 0;
            
            // Check all positions that this parity bit covers
            for (int pos = 1; pos <= TOTAL_BITS - 1; pos++) {  // Exclude overall parity
                if ((pos & parity_bit) != 0) {  // If bit is set in binary representation
                    if (codeword.getBit(pos)) {
                        parity ^= 1;
                    }
                }
            }
            
            codeword.setBit(parity_bit, parity);
        }
        
        // Calculate and set overall parity bit (SEC-DED)
        int overall_parity = 0;
        for (int pos = 1; pos <= TOTAL_BITS - 1; pos++) {
            if (codeword.getBit(pos)) {
                overall_parity ^= 1;
            }
        }
        codeword.setBit(TOTAL_BITS, overall_parity);
        
        return codeword;
    }
    
    // Decode SEC-DED Hamming codeword with enhanced error detection
    DecodingResult decode(CodeWord received) const {
        DecodingResult result;
        result.syndrome = 0;
        result.error_position = 0;
        result.data_corrected = false;

        BitVector cwVec;
        for (int pos = 1; pos <= TOTAL_BITS - 1; ++pos) {
            if (received.getBit(pos))
                cwVec.set(pos-1, true);
        }

        // Use the cached parity-check matrix built during construction.
        BitVector synVec = pcm_.syndrome(cwVec);
        for (int i = 0; i < PARITY_BITS; ++i) {
            if (synVec.get(i))
                result.syndrome |= (1 << i);
        }
        
        // Calculate overall parity
        int calculated_overall_parity = 0;
        for (int pos = 1; pos <= TOTAL_BITS; pos++) {
            if (received.getBit(pos)) {
                calculated_overall_parity ^= 1;
            }
        }
        result.overall_parity = (calculated_overall_parity != 0);
        
        // Convert syndrome to binary string
        result.syndrome_binary = std::bitset<PARITY_BITS>(result.syndrome).to_string();
        
        // SEC-DED Analysis
        if (result.syndrome == 0 && !result.overall_parity) {
            // No error
            result.error_type = NO_ERROR;
            result.error_type_string = "No Error";
        } else if (result.syndrome == 0 && result.overall_parity) {
            // Error in overall parity bit only
            result.error_type = OVERALL_PARITY_ERROR;
            result.error_type_string = "Overall Parity Error";
            result.error_position = TOTAL_BITS;
            received.flipBit(TOTAL_BITS);
            result.data_corrected = true;
        } else if (result.syndrome != 0 && result.overall_parity) {
            // Single error (correctable)
            result.error_type = SINGLE_ERROR_CORRECTABLE;
            result.error_type_string = "Single Error (Correctable)";
            result.error_position = result.syndrome;
            
            if (result.error_position <= TOTAL_BITS - 1) {
                received.flipBit(result.error_position);
                result.data_corrected = true;
            }
        } else if (result.syndrome != 0 && !result.overall_parity) {
            // Double error (detectable, not correctable)
            result.error_type = DOUBLE_ERROR_DETECTABLE;
            result.error_type_string = "Double Error (Detectable, Not Correctable)";
            result.data_corrected = false;
        } else {
            // Multiple error (uncorrectable)
            result.error_type = MULTIPLE_ERROR_UNCORRECTABLE;
            result.error_type_string = "Multiple Error (Uncorrectable)";
            result.data_corrected = false;
        }
        
        // Extract data bits from (possibly corrected) codeword
        std::vector<int> data_positions = getDataPositions();
        result.corrected_data = 0;
        for (int i = 0; i < DATA_BITS; i++) {
            if (received.getBit(data_positions[i])) {
                result.corrected_data |= (1U << i);
            }
        }
        
        return result;
    }
};

class ECCStatistics {
private:
    std::map<std::string, uint64_t> counters;
    std::chrono::steady_clock::time_point start_time;
    double energy_accumulator;  // Dynamic energy in joules
    const double energy_per_xor;
    const double energy_per_and;

public:
    ECCStatistics()
        : energy_accumulator(0.0),
          energy_per_xor(gate_energy(28, 0.8, "xor")),
          energy_per_and(gate_energy(28, 0.8, "and")) {
        start_time = std::chrono::steady_clock::now();
        reset();
    }
    
    void reset() {
        counters.clear();
        counters["total_writes"] = 0;
        counters["total_reads"] = 0;
        counters["no_errors"] = 0;
        counters["single_errors_corrected"] = 0;
        counters["double_errors_detected"] = 0;
        counters["multiple_errors_uncorrectable"] = 0;
        counters["overall_parity_errors"] = 0;
        counters["data_corruption_prevented"] = 0;
        energy_accumulator = 0.0;
    }
    
    void recordWrite() {
        counters["total_writes"]++;
    }
    
    void recordRead(const HammingCodeSECDED::DecodingResult& result) {
        counters["total_reads"]++;

        // Base energy for parity checks (XORs)
        energy_accumulator +=
            (HammingCodeSECDED::PARITY_BITS + HammingCodeSECDED::OVERALL_PARITY_BIT) *
            energy_per_xor;

        switch (result.error_type) {
            case HammingCodeSECDED::NO_ERROR:
                counters["no_errors"]++;
                break;
            case HammingCodeSECDED::SINGLE_ERROR_CORRECTABLE:
                counters["single_errors_corrected"]++;
                counters["data_corruption_prevented"]++;
                energy_accumulator += energy_per_and;
                break;
            case HammingCodeSECDED::DOUBLE_ERROR_DETECTABLE:
                counters["double_errors_detected"]++;
                counters["data_corruption_prevented"]++;
                energy_accumulator += energy_per_and;
                break;
            case HammingCodeSECDED::MULTIPLE_ERROR_UNCORRECTABLE:
                counters["multiple_errors_uncorrectable"]++;
                energy_accumulator += energy_per_and;
                break;
            case HammingCodeSECDED::OVERALL_PARITY_ERROR:
                counters["overall_parity_errors"]++;
                counters["data_corruption_prevented"]++;
                energy_accumulator += energy_per_and;
                break;
        }
    }
    
    void printStatistics() {
        auto end_time = std::chrono::steady_clock::now();
        auto duration = std::chrono::duration_cast<std::chrono::milliseconds>(end_time - start_time);
        
        std::cout << "\n" << std::string(60, '=') << std::endl;
        std::cout << "ECC STATISTICS SUMMARY" << std::endl;
        std::cout << std::string(60, '=') << std::endl;
        std::cout << "Simulation Duration: " << duration.count() << " ms" << std::endl;
        std::cout << "Total Memory Operations:" << std::endl;
        std::cout << "  Writes: " << counters["total_writes"] << std::endl;
        std::cout << "  Reads:  " << counters["total_reads"] << std::endl;
        std::cout << std::endl;
        
        std::cout << "Error Detection & Correction:" << std::endl;
        std::cout << "  No Errors:                    " << counters["no_errors"] 
                  << " (" << std::fixed << std::setprecision(2) 
                  << (100.0 * counters["no_errors"] / counters["total_reads"]) << "%)" << std::endl;
        std::cout << "  Single Errors Corrected:      " << counters["single_errors_corrected"]
                  << " (" << std::fixed << std::setprecision(2) 
                  << (100.0 * counters["single_errors_corrected"] / counters["total_reads"]) << "%)" << std::endl;
        std::cout << "  Double Errors Detected:       " << counters["double_errors_detected"]
                  << " (" << std::fixed << std::setprecision(2) 
                  << (100.0 * counters["double_errors_detected"] / counters["total_reads"]) << "%)" << std::endl;
        std::cout << "  Overall Parity Errors:        " << counters["overall_parity_errors"]
                  << " (" << std::fixed << std::setprecision(2) 
                  << (100.0 * counters["overall_parity_errors"] / counters["total_reads"]) << "%)" << std::endl;
        std::cout << "  Multiple Errors (Uncorrectable): " << counters["multiple_errors_uncorrectable"]
                  << " (" << std::fixed << std::setprecision(2) 
                  << (100.0 * counters["multiple_errors_uncorrectable"] / counters["total_reads"]) << "%)" << std::endl;
        
        std::cout << std::endl;
        std::cout << "Data Integrity Metrics:" << std::endl;
        std::cout << "  Data Corruption Prevented:    " << counters["data_corruption_prevented"]
                  << " (" << std::fixed << std::setprecision(2) 
                  << (100.0 * counters["data_corruption_prevented"] / counters["total_reads"]) << "%)" << std::endl;
        
        uint64_t total_errors = counters["single_errors_corrected"] +
                               counters["double_errors_detected"] +
                               counters["multiple_errors_uncorrectable"] +
                               counters["overall_parity_errors"];

        if (total_errors > 0) {
            std::cout << "  Error Recovery Rate:           "
                      << std::fixed << std::setprecision(2)
                      << (100.0 * counters["data_corruption_prevented"] / total_errors) << "%" << std::endl;
        }
        std::cout << std::string(60, '-') << std::endl;
        std::cout << "Estimated energy consumed: " << std::scientific
                  << energy_accumulator << " J" << std::endl;

        std::cout << std::string(60, '=') << std::endl;

        // Structured logging of statistics
        std::ofstream json_out("ecc_stats.json");
        if (json_out) {
            double ber = 0.0;
            if (counters["total_reads"] > 0) {
                ber = static_cast<double>(total_errors) /
                      (counters["total_reads"] * HammingCodeSECDED::DATA_BITS);
            }
            json_out << "{\n";
            json_out << "  \"total_reads\": " << counters["total_reads"] << ",\n";
            json_out << "  \"total_writes\": " << counters["total_writes"] << ",\n";
            json_out << "  \"single_errors_corrected\": " << counters["single_errors_corrected"] << ",\n";
            json_out << "  \"double_errors_detected\": " << counters["double_errors_detected"] << ",\n";
            json_out << "  \"multiple_errors_uncorrectable\": " << counters["multiple_errors_uncorrectable"] << ",\n";
            json_out << "  \"overall_parity_errors\": " << counters["overall_parity_errors"] << ",\n";
            json_out << "  \"dynamic_J\": " << energy_accumulator << ",\n";
            json_out << "  \"leakage_J\": 0.0,\n";
            json_out << "  \"total_J\": " << energy_accumulator << ",\n";
            json_out << "  \"ber\": " << ber << "\n";
            json_out << "}\n";
        }

        std::ofstream csv_out("ecc_stats.csv");
        if (csv_out) {
            csv_out << "metric,value\n";
            for (const auto& p : counters) {
                csv_out << p.first << ',' << p.second << "\n";
            }
            double ber = 0.0;
            if (counters["total_reads"] > 0) {
                ber = static_cast<double>(total_errors) /
                      (counters["total_reads"] * HammingCodeSECDED::DATA_BITS);
            }
            csv_out << "dynamic_J," << energy_accumulator << "\n";
            csv_out << "leakage_J,0\n";
            csv_out << "total_J," << energy_accumulator << "\n";
            csv_out << "ber," << ber << "\n";
        }
    }
};

class AdvancedMemorySimulator {
private:
    static const size_t MEMORY_SIZE_WORDS = 1024 * 1024 * 256;  // 1GB / 4 bytes = 256M words
    std::unordered_map<uint32_t, HammingCodeSECDED::CodeWord> memory;  // sparse memory map
    HammingCodeSECDED hamming;
    ECCStatistics stats;
    std::mt19937 rng;
    
public:
    AdvancedMemorySimulator() : rng(std::random_device{}()) {
        std::cout << "Initialized SEC-DED 1GB memory simulator with "
                  << MEMORY_SIZE_WORDS << " 32-bit words" << std::endl;
        std::cout << "Total bits per codeword: " << HammingCodeSECDED::TOTAL_BITS
                  << " (32 data + 6 parity + 1 overall parity)" << std::endl;
    }

    // Reinitialise the ECC logic. This allows the simulator to rebuild the
    // cached parity-check matrix if any configuration parameter changes.
    void reinitializeECC() { hamming.resetPCM(); }
    
    // Write data to memory with SEC-DED encoding
    void write(uint32_t address, uint32_t data) {
        if (address >= MEMORY_SIZE_WORDS) {
            throw std::out_of_range("Address out of range");
        }
        
        memory[address] = hamming.encode(data);
        stats.recordWrite();
    }

    // Read data from memory with error detection/correction
    HammingCodeSECDED::DecodingResult read(uint32_t address) {
        auto it = memory.find(address);
        if (it == memory.end()) {
            throw std::out_of_range("Address not written or out of range");
        }

        auto result = hamming.decode(it->second);

        // Refresh memory with corrected data if SEC-DED fixed a bit flip
        if (result.data_corrected) {
            it->second = hamming.encode(result.corrected_data);
        }

        stats.recordRead(result);
        return result;
    }
    
    // Inject single-bit error at specific position
    void injectError(uint32_t address, int bit_position) {
        auto it = memory.find(address);
        if (it == memory.end()) {
            throw std::out_of_range("Address not written");
        }
        
        if (bit_position < 1 || bit_position > HammingCodeSECDED::TOTAL_BITS) {
            throw std::out_of_range("Invalid bit position");
        }
        
        it->second.flipBit(bit_position);
        std::cout << "Injected error at address " << address 
                  << ", bit position " << bit_position << std::endl;
    }
    
    // Inject burst error (adjacent bits)
    void injectBurstError(uint32_t address, int start_position, int burst_length) {
        auto it = memory.find(address);
        if (it == memory.end()) {
            throw std::out_of_range("Address not written");
        }
        
        if (start_position < 1 || start_position + burst_length - 1 > HammingCodeSECDED::TOTAL_BITS) {
            throw std::out_of_range("Invalid burst error parameters");
        }
        
        std::cout << "Injecting burst error at address " << address 
                  << ", positions " << start_position << "-" << (start_position + burst_length - 1) << ": ";
        
        for (int i = 0; i < burst_length; i++) {
            int pos = start_position + i;
            it->second.flipBit(pos);
            std::cout << pos << " ";
        }
        std::cout << std::endl;
    }
    
    // Inject random errors
    void injectRandomErrors(uint32_t address, int num_errors) {
        auto it = memory.find(address);
        if (it == memory.end()) {
            throw std::out_of_range("Address not written");
        }

        std::uniform_int_distribution<int> bit_dist(1, HammingCodeSECDED::TOTAL_BITS);
        std::cout << "Injecting " << num_errors << " random errors at address " << address << ": ";

        std::set<int> used_positions;
        for (int i = 0; i < num_errors; i++) {
            int bit_pos;
            do {
                bit_pos = bit_dist(rng);
            } while (used_positions.count(bit_pos));

            used_positions.insert(bit_pos);
            it->second.flipBit(bit_pos);
            std::cout << bit_pos << " ";
        }
        std::cout << std::endl;
    }
    
    size_t getMemorySize() const {
        return memory.size();
    }

    size_t getMemoryCapacity() const {
        return MEMORY_SIZE_WORDS;
    }

    // Load an external parity-check matrix. This allows experiments with
    // arbitrary ECC constructions while reusing the simulator infrastructure.
    bool loadParityCheckMatrix(const std::string& path) {
        return hamming.loadPCMFromFile(path);
    }

    void printStatistics() {
        stats.printStatistics();
    }
    
    void resetStatistics() {
        stats.reset();
    }
};

class AdvancedTestSuite {
private:
    AdvancedMemorySimulator& memory;
    HammingCodeSECDED hamming;
    
    void printTestHeader(const std::string& test_name) {
        std::cout << "\n" << std::string(60, '=') << std::endl;
        std::cout << "TEST: " << test_name << std::endl;
        std::cout << std::string(60, '=') << std::endl;
    }
    
    void printDecodingResult(uint32_t address, uint32_t original_data,
                           const HammingCodeSECDED::DecodingResult& result) {
        std::cout << "Address: 0x" << std::hex << address << std::dec << std::endl;
        std::cout << "Original Data: 0x" << std::hex << original_data 
                  << " (" << std::bitset<32>(original_data) << ")" << std::endl;
        std::cout << "Syndrome: " << result.syndrome 
                  << " (" << result.syndrome_binary << ")" << std::endl;
        std::cout << "Overall Parity: " << (result.overall_parity ? "ODD" : "EVEN") << std::endl;
        std::cout << "Error Type: " << result.error_type_string << std::endl;
        std::cout << "Error Position: " << result.error_position << std::endl;
        std::cout << "Data Corrected: " << (result.data_corrected ? "YES" : "NO") << std::endl;
        std::cout << "Corrected Data: 0x" << std::hex << result.corrected_data 
                  << " (" << std::bitset<32>(result.corrected_data) << ")" << std::endl;
        std::cout << "Data Integrity: " << ((original_data == result.corrected_data ||
                                             result.error_type == HammingCodeSECDED::DOUBLE_ERROR_DETECTABLE) ? "MAINTAINED" : "COMPROMISED") << std::endl;
        std::cout << std::string(40, '-') << std::endl;

        // Append structured log for this read
        std::ofstream csv_log("decoding_results.csv", std::ios::app);
        if (csv_log) {
            csv_log << address << ',' << original_data << ','
                    << result.error_type_string << ',' << result.data_corrected << '\n';
        }
        std::ofstream json_log("decoding_results.json", std::ios::app);
        if (json_log) {
            json_log << "{\"address\": " << address
                     << ", \"error_type\": \"" << result.error_type_string << "\",";
            json_log << " \"data_corrected\": " << (result.data_corrected ? "true" : "false") << "}" << std::endl;
        }
    }
    
public:
    AdvancedTestSuite(AdvancedMemorySimulator& mem) : memory(mem) {}

    void testKnownVectors() {
        printTestHeader("Known Test Vectors");

        struct Vector { uint32_t data; uint64_t encoded; };
        std::vector<Vector> vectors = {
            {0x00000000u, 0x0ULL},
            {0xFFFFFFFFu, 0x3F7FFFFFF4ULL},
            {0x12345678u, 0x44C68A67C9ULL}
        };

        for (const auto& v : vectors) {
            auto cw = hamming.encode(v.data);
            assert(cw.data == v.encoded && "Encoding mismatch");
            auto result = hamming.decode(cw);
            assert(result.corrected_data == v.data && "Mismatch in decoding!");
            printDecodingResult(0, v.data, result);
        }
    }

    void batchFaultInjection(int trials = 1000) {
        printTestHeader("Batch Fault Injection");
        std::mt19937 rng(42);
        std::uniform_int_distribution<uint32_t> data_dist(0, UINT32_MAX);
        std::uniform_int_distribution<int> error_count_dist(1, 3);
        std::uniform_int_distribution<int> pos_dist(1, HammingCodeSECDED::TOTAL_BITS);

        int detections = 0, corrections = 0;
        std::ofstream log("batch_results.csv");
        if (log) log << "trial,errors,detected,corrected\n";

        for (int t = 0; t < trials; ++t) {
            uint32_t data = data_dist(rng);
            auto cw = hamming.encode(data);
            int num_errors = error_count_dist(rng);
            std::set<int> used;
            for (int i = 0; i < num_errors; ++i) {
                int pos;
                do {
                    pos = pos_dist(rng);
                } while (!used.insert(pos).second);
                cw.flipBit(pos);
            }
            auto result = hamming.decode(cw);
            bool detected = result.error_type != HammingCodeSECDED::NO_ERROR;
            bool corrected = result.corrected_data == data;
            if (detected) detections++; if (corrected) corrections++;
            if (log) log << t << ',' << num_errors << ',' << detected << ',' << corrected << '\n';
        }

        std::cout << "Detection rate: " << (100.0 * detections / trials) << "%" << std::endl;
        std::cout << "Correction rate: " << (100.0 * corrections / trials) << "%" << std::endl;
    }

    void runAllTests() {
        // Execute the full suite including known vectors and large batch fault
        // injection trials to ensure regression coverage.
        testKnownVectors();
        testNoError();
        testSingleBitErrors();
        testDoubleBitErrors();
        testOverallParityErrors();
        testBurstErrors();
        testRandomMultipleErrors();
        testMixedWorkload();
        batchFaultInjection();
    }
    
    void testNoError() {
        printTestHeader("No Error Test (SEC-DED)");
        
        std::vector<uint32_t> test_data = {
            0x00000000, 0xFFFFFFFF, 0x12345678, 0xA5A5A5A5, 0x5A5A5A5A
        };
        
        for (size_t i = 0; i < test_data.size(); i++) {
            uint32_t address = i;
            uint32_t data = test_data[i];
            
            memory.write(address, data);
            auto result = memory.read(address);
            
            std::cout << "Test " << (i + 1) << ":" << std::endl;
            printDecodingResult(address, data, result);
        }
    }
    
    void testSingleBitErrors() {
        printTestHeader("Single Bit Error Test (SEC-DED)");
        
        uint32_t test_data = 0x12345678;
        uint32_t base_address = 1000;
        
        // Test a sampling of positions including data, parity, and overall parity
        std::vector<int> test_positions = {1, 2, 3, 4, 5, 8, 15, 16, 20, 32, 35, 39};
        
        for (int pos : test_positions) {
            uint32_t address = base_address + pos;
            
            memory.write(address, test_data);
            memory.injectError(address, pos);
            auto result = memory.read(address);
            
            std::cout << "Single error at position " << pos << ":" << std::endl;
            printDecodingResult(address, test_data, result);
        }
    }
    
    void testDoubleBitErrors() {
        printTestHeader("Double Bit Error Test (SEC-DED Detection)");
        
        uint32_t test_data = 0xAAAAAAAA;
        uint32_t base_address = 2000;
        
        std::vector<std::pair<int, int>> double_error_pairs = {
            {1, 3}, {2, 5}, {10, 15}, {20, 25}, {30, 35}
        };
        
        for (size_t i = 0; i < double_error_pairs.size(); i++) {
            uint32_t address = base_address + i;
            auto& pair = double_error_pairs[i];
            
            memory.write(address, test_data);
            memory.injectError(address, pair.first);
            memory.injectError(address, pair.second);
            auto result = memory.read(address);
            
            std::cout << "Double error at positions " << pair.first << ", " << pair.second << ":" << std::endl;
            printDecodingResult(address, test_data, result);
        }
    }
    
    void testOverallParityErrors() {
        printTestHeader("Overall Parity Bit Error Test");
        
        uint32_t test_data = 0x55555555;
        uint32_t address = 3000;
        
        memory.write(address, test_data);
        memory.injectError(address, HammingCodeSECDED::TOTAL_BITS);  // Position 39
        auto result = memory.read(address);
        
        std::cout << "Overall parity bit error:" << std::endl;
        printDecodingResult(address, test_data, result);
    }
    
    void testBurstErrors() {
        printTestHeader("Burst Error Test");
        
        uint32_t test_data = 0x87654321;
        uint32_t base_address = 4000;
        
        std::vector<std::pair<int, int>> burst_configs = {
            {1, 2},   // 2-bit burst
            {5, 3},   // 3-bit burst
            {10, 4},  // 4-bit burst
            {20, 5},  // 5-bit burst
            {30, 6}   // 6-bit burst
        };
        
        for (size_t i = 0; i < burst_configs.size(); i++) {
            uint32_t address = base_address + i;
            auto& config = burst_configs[i];
            
            memory.write(address, test_data);
            memory.injectBurstError(address, config.first, config.second);
            auto result = memory.read(address);
            
            std::cout << "Burst error (" << config.second << " bits):" << std::endl;
            printDecodingResult(address, test_data, result);
        }
    }
    
    void testRandomMultipleErrors() {
        printTestHeader("Random Multiple Error Test");
        
        uint32_t test_data = 0xDEADBEEF;
        uint32_t base_address = 5000;
        
        std::vector<int> error_counts = {3, 4, 5, 6, 7, 8};
        
        for (size_t i = 0; i < error_counts.size(); i++) {
            uint32_t address = base_address + i;
            
            memory.write(address, test_data);
            memory.injectRandomErrors(address, error_counts[i]);
            auto result = memory.read(address);
            
            std::cout << "Random multiple errors (" << error_counts[i] << " bits):" << std::endl;
            printDecodingResult(address, test_data, result);
        }
    }
    
    void testMixedWorkload() {
        printTestHeader("Mixed Workload Simulation");
        
        std::mt19937 rng(12345);
        std::uniform_int_distribution<uint32_t> data_dist(0, UINT32_MAX);
        std::uniform_int_distribution<int> error_type_dist(0, 100);
        
        for (int i = 0; i < 20; i++) {
            uint32_t address = 6000 + i;
            uint32_t data = data_dist(rng);
            
            memory.write(address, data);
            
            int error_chance = error_type_dist(rng);
            std::string scenario;
            
            if (error_chance < 70) {
                // 70% - No error
                scenario = "No Error";
            } else if (error_chance < 85) {
                // 15% - Single error
                std::uniform_int_distribution<int> bit_dist(1, HammingCodeSECDED::TOTAL_BITS);
                memory.injectError(address, bit_dist(rng));
                scenario = "Single Error";
            } else if (error_chance < 95) {
                // 10% - Double error
                memory.injectRandomErrors(address, 2);
                scenario = "Double Error";
            } else {
                // 5% - Multiple errors
                std::uniform_int_distribution<int> count_dist(3, 6);
                memory.injectRandomErrors(address, count_dist(rng));
                scenario = "Multiple Errors";
            }
            
            auto result = memory.read(address);
            
            std::cout << "Mixed workload " << (i + 1) << " (" << scenario << "):" << std::endl;
            printDecodingResult(address, data, result);
        }
    }
};

// Compare SEC-DED and TAEC coverage using a simple Monte Carlo model.
static void runEccSchemeDemo(int trials = 1000, unsigned seed = 1) {
    using Pattern = std::pair<int, std::string>;
    const std::vector<Pattern> patterns = {
        {1, ""},
        {2, "adj"},
        {2, "nonadj"},
        {3, "adj"},
        {3, "nonadj"},
    };
    const std::set<Pattern> correctable_hamming = {{1, ""}};
    const std::set<Pattern> detectable_hamming = {{2, "adj"}, {2, "nonadj"}};
    const std::set<Pattern> correctable_taec = {{1, ""}, {2, "adj"}, {3, "adj"}};
    const std::set<Pattern> detectable_taec = {{2, "nonadj"}, {3, "nonadj"}};

    std::map<Pattern, int> pattern_counts;
    struct Stats { int corrected = 0, detected = 0, undetected = 0; };
    std::map<std::string, Stats> stats = {{"SEC-DED", {}}, {"TAEC", {}}};

    std::mt19937 rng(seed);
    std::uniform_int_distribution<size_t> dist(0, patterns.size() - 1);
    for (int i = 0; i < trials; ++i) {
        const Pattern& p = patterns[dist(rng)];
        pattern_counts[p]++;
        auto update = [&](const std::string& code,
                          const std::set<Pattern>& correctable,
                          const std::set<Pattern>& detectable) {
            if (correctable.count(p))
                stats[code].corrected++;
            else if (detectable.count(p))
                stats[code].detected++;
            else
                stats[code].undetected++;
        };
        update("SEC-DED", correctable_hamming, detectable_hamming);
        update("TAEC", correctable_taec, detectable_taec);
    }

    auto label = [](const Pattern& p) {
        if (p.first == 1)
            return std::string("1-bit single");
        std::string type = (p.second == "adj") ? "adjacent" : "nonadjacent";
        return std::to_string(p.first) + "-bit " + type;
    };

    std::cout << "\nPattern distribution:" << std::endl;
    for (const auto& p : patterns) {
        std::cout << "  " << label(p) << ": " << pattern_counts[p] << std::endl;
    }

    std::cout << "\nECC results:" << std::endl;
    for (const auto& kv : stats) {
        const auto& code = kv.first;
        const auto& s = kv.second;
        std::cout << "  " << std::setw(7) << code
                  << " -> corrected: " << s.corrected
                  << " (" << std::fixed << std::setprecision(2)
                  << (100.0 * s.corrected / trials) << "%), "
                  << "detected-only: " << s.detected
                  << " (" << (100.0 * s.detected / trials) << "%), "
                  << "undetected: " << s.undetected
                  << " (" << (100.0 * s.undetected / trials) << "%)" << std::endl;
    }
}

int main(int argc, char* argv[]) {
    try {
        bool smoke = false;
        std::string pcm_path;
        for (int i = 1; i < argc; ++i) {
            std::string arg = argv[i];
            if (arg == "--smoke") {
                smoke = true;
            } else if (arg == "--pcm" && i + 1 < argc) {
                pcm_path = argv[++i];
            }
        }

        if (smoke) {
            HammingCodeSECDED hamming;
            auto cw = hamming.encode(0x12345678u);
            auto result = hamming.decode(cw);
            return (result.corrected_data == 0x12345678u) ? 0 : 1;
        }

        std::cout << "Advanced Hamming SEC-DED Memory Simulator" << std::endl;
        std::cout << "Data bits: 32, Parity bits: 6, Overall parity: 1, Total bits: 39" << std::endl;
        std::cout << "Memory size: 1GB (256M 32-bit words)" << std::endl;
        std::cout << "Features: Single Error Correction, Double Error Detection" << std::endl;

        AdvancedMemorySimulator memory;
        if (!pcm_path.empty() && !memory.loadParityCheckMatrix(pcm_path)) {
            std::cerr << "Warning: failed to load parity-check matrix from '"
                      << pcm_path << "'. Using default." << std::endl;
        }
        AdvancedTestSuite tests(memory);

        tests.runAllTests();

        memory.printStatistics();

        std::cout << "\n" << std::string(60, '=') << std::endl;
        std::cout << "ADVANCED SIMULATION COMPLETE" << std::endl;
        std::cout << "Total memory words used: " << memory.getMemorySize() << std::endl;
        std::cout << "Memory utilization: " << std::fixed << std::setprecision(6)
                  << (100.0 * memory.getMemorySize()) / memory.getMemoryCapacity()
                  << "% of 1GB capacity" << std::endl;
        std::cout << "Actual memory consumed: ~"
                  << (memory.getMemorySize() * sizeof(HammingCodeSECDED::CodeWord)) / (1024*1024)
                  << " MB" << std::endl;
        std::cout << std::string(60, '=') << std::endl;


        // Provide high level design guidance for users exploring ECC choices.
        printArchetypeReport();

        // Illustrate ECC scheme coverage for both SEC-DED and TAEC.
        runEccSchemeDemo();


    } catch (const std::exception& e) {
        std::cerr << "Error: " << e.what() << std::endl;
        return 1;
    }

    return 0;
}
