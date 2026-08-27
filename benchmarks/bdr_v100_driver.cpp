#include <bdr/database.hpp>

#include <chrono>
#include <cstdint>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>

namespace fs = std::filesystem;
using Clock = std::chrono::steady_clock;

static std::uint32_t read_u32(std::ifstream& in) {
    unsigned char b[4];
    if (!in.read(reinterpret_cast<char*>(b), 4)) throw std::runtime_error("truncated workload u32");
    return (std::uint32_t(b[0]) << 24) | (std::uint32_t(b[1]) << 16) |
           (std::uint32_t(b[2]) << 8) | std::uint32_t(b[3]);
}

static std::uint64_t read_u64(std::ifstream& in) {
    unsigned char b[8];
    if (!in.read(reinterpret_cast<char*>(b), 8)) throw std::runtime_error("truncated workload u64");
    std::uint64_t v = 0;
    for (unsigned char c : b) v = (v << 8) | std::uint64_t(c);
    return v;
}

static std::vector<std::pair<std::string, std::string>> load_workload(const fs::path& path) {
    std::ifstream in(path, std::ios::binary);
    if (!in) throw std::runtime_error("cannot open workload");
    const auto count = read_u64(in);
    std::vector<std::pair<std::string, std::string>> rows;
    rows.reserve(static_cast<std::size_t>(count));
    for (std::uint64_t i = 0; i < count; ++i) {
        const auto kl = read_u32(in);
        const auto vl = read_u32(in);
        std::string key(kl, '\0');
        std::string value(vl, '\0');
        if (!in.read(key.data(), static_cast<std::streamsize>(kl))) throw std::runtime_error("truncated key");
        if (!in.read(value.data(), static_cast<std::streamsize>(vl))) throw std::runtime_error("truncated value");
        rows.emplace_back(std::move(key), std::move(value));
    }
    return rows;
}

static std::uintmax_t directory_bytes(const fs::path& root) {
    std::uintmax_t total = 0;
    if (!fs::exists(root)) return 0;
    for (const auto& entry : fs::recursive_directory_iterator(root)) {
        if (entry.is_regular_file()) total += entry.file_size();
    }
    return total;
}

template <class F>
static double milliseconds(F&& fn) {
    const auto start = Clock::now();
    fn();
    return std::chrono::duration<double, std::milli>(Clock::now() - start).count();
}

int main(int argc, char** argv) {
    if (argc != 3) {
        std::cerr << "usage: bdr_v100_driver <db-dir> <workload.bin>\n";
        return 2;
    }
    try {
        const fs::path root = argv[1];
        const fs::path workload_path = argv[2];
        fs::remove_all(root);
        const auto rows = load_workload(workload_path);

        bdr::Options options{}; // frozen v1.0.0 defaults, intentionally unchanged
        auto db = bdr::Database::open(root, options);

        const double write_ms = milliseconds([&] {
            for (const auto& [key, value] : rows) db->put(key, value);
            db->sync();
        });

        std::size_t verified = 0;
        const double read_ms = milliseconds([&] {
            for (const auto& [key, value] : rows) {
                const auto got = db->get(key);
                if (!got || *got != value) throw std::runtime_error("BDR read mismatch");
                ++verified;
            }
        });

        db->checkpoint();
        const auto durable_sequence = db->durable_sequence();
        db->close();
        db.reset();
        const auto bytes_after_close = directory_bytes(root);

        std::size_t reopen_verified = 0;
        double reopen_ms = 0.0;
        auto reopened = std::unique_ptr<bdr::Database>{};
        reopen_ms = milliseconds([&] {
            reopened = bdr::Database::open(root, options);
            for (const auto& [key, value] : rows) {
                const auto got = reopened->get(key);
                if (!got || *got != value) throw std::runtime_error("BDR reopen mismatch");
                ++reopen_verified;
            }
        });
        const auto logical_size = reopened->size();
        reopened->close();

        std::cout
            << "{\"engine\":\"bdr-v1.0.0\","
            << "\"records\":" << rows.size() << ','
            << "\"write_ms\":" << write_ms << ','
            << "\"read_ms\":" << read_ms << ','
            << "\"reopen_verify_ms\":" << reopen_ms << ','
            << "\"verified\":" << verified << ','
            << "\"reopen_verified\":" << reopen_verified << ','
            << "\"logical_size\":" << logical_size << ','
            << "\"durable_sequence\":" << durable_sequence << ','
            << "\"disk_bytes\":" << bytes_after_close
            << "}\n";
        return 0;
    } catch (const std::exception& exc) {
        std::cerr << "BDR benchmark failure: " << exc.what() << '\n';
        return 1;
    }
}
