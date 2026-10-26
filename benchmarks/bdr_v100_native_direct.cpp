#include <bdr/database.hpp>
#include <sqlite3.h>

#include <algorithm>
#include <chrono>
#include <cstdint>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <optional>
#include <random>
#include <sstream>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <utility>
#include <vector>

namespace fs = std::filesystem;
using Clock = std::chrono::steady_clock;

struct Record { std::string key; std::string value; };
struct Metrics {
    double write_ms = 0;
    double read_ms = 0;
    double random_read_ms = 0;
    double update_ms = 0;
    double delete_ms = 0;
    double checkpoint_ms = 0;
    double reopen_verify_ms = 0;
    std::uint64_t disk_bytes = 0;
    std::size_t verified = 0;
};

static double elapsed_ms(Clock::time_point start) {
    return std::chrono::duration<double, std::milli>(Clock::now() - start).count();
}

static std::uint64_t directory_bytes(const fs::path& root) {
    std::uint64_t total = 0;
    if (!fs::exists(root)) return 0;
    for (auto const& e : fs::recursive_directory_iterator(root)) {
        if (e.is_regular_file()) total += e.file_size();
    }
    return total;
}

static std::string hex64(std::uint64_t x) {
    std::ostringstream os;
    os << std::hex << std::setw(16) << std::setfill('0') << x;
    return os.str();
}

// Deterministic native fingerprint used only to generate stable node identifiers
// for an equal storage workload. It is intentionally outside the measured DB paths.
static std::string fingerprint(const std::string& payload, int layer) {
    std::uint64_t h = 1469598103934665603ULL ^ static_cast<std::uint64_t>(layer);
    for (unsigned char c : payload) {
        h ^= c;
        h *= 1099511628211ULL;
    }
    return hex64(h);
}

static std::string payload_for(std::size_t index, std::size_t size) {
    std::string out(size, '\0');
    std::uint64_t x = 0x9E3779B97F4A7C15ULL ^ (index * 0xD1B54A32D192ED03ULL);
    for (std::size_t i = 0; i < size; ++i) {
        x ^= x >> 12; x ^= x << 25; x ^= x >> 27;
        x *= 2685821657736338717ULL;
        out[i] = static_cast<char>((x >> 56) & 0xff);
    }
    return out;
}

static std::vector<Record> materialize(std::size_t memories, std::size_t payload_bytes, int max_layer) {
    std::vector<Record> out;
    std::unordered_map<std::string, bool> seen_nodes;
    const std::size_t per_memory_occ = payload_bytes * 2;
    out.reserve(memories * (per_memory_occ + 4));

    for (std::size_t i = 0; i < memories; ++i) {
        std::ostringstream id;
        id << "memory-" << std::setw(8) << std::setfill('0') << i;
        std::string mid = id.str();
        std::string data = payload_for(i, payload_bytes);
        out.push_back({"m:" + mid, data});
        for (int layer = 0; layer <= max_layer; ++layer) {
            std::size_t width = std::size_t{1} << layer;
            std::size_t local_time = 0;
            for (std::size_t off = 0; off < data.size(); off += width, ++local_time) {
                std::string p = data.substr(off, std::min(width, data.size() - off));
                std::string node = fingerprint(p, layer);
                std::string nkey = "n:" + node;
                if (seen_nodes.emplace(nkey, true).second) {
                    std::string nv;
                    nv.push_back(static_cast<char>((layer >> 8) & 0xff));
                    nv.push_back(static_cast<char>(layer & 0xff));
                    nv += p;
                    out.push_back({std::move(nkey), std::move(nv)});
                }
                out.push_back({"o:" + mid + ":" + std::to_string(layer) + ":" + std::to_string(local_time), node});
            }
        }
    }
    return out;
}

static void sqlite_check(int rc, sqlite3* db, const char* what) {
    if (rc != SQLITE_OK && rc != SQLITE_DONE && rc != SQLITE_ROW) {
        throw std::runtime_error(std::string(what) + ": " + (db ? sqlite3_errmsg(db) : "sqlite error"));
    }
}

static Metrics bench_sqlite(const fs::path& root, std::vector<Record>& records, std::size_t random_reads,
                            std::size_t mutate_count) {
    fs::create_directories(root);
    auto db_path = root / "direct.sqlite3";
    sqlite3* db = nullptr;
    sqlite_check(sqlite3_open(db_path.c_str(), &db), db, "open");
    sqlite_check(sqlite3_exec(db, "PRAGMA journal_mode=WAL; PRAGMA synchronous=FULL; CREATE TABLE kv(k TEXT PRIMARY KEY,v BLOB NOT NULL);", nullptr, nullptr, nullptr), db, "schema");

    sqlite3_stmt* put = nullptr;
    sqlite3_stmt* get = nullptr;
    sqlite3_stmt* del = nullptr;
    sqlite_check(sqlite3_prepare_v2(db, "INSERT INTO kv(k,v) VALUES(?,?) ON CONFLICT(k) DO UPDATE SET v=excluded.v", -1, &put, nullptr), db, "prepare put");
    sqlite_check(sqlite3_prepare_v2(db, "SELECT v FROM kv WHERE k=?", -1, &get, nullptr), db, "prepare get");
    sqlite_check(sqlite3_prepare_v2(db, "DELETE FROM kv WHERE k=?", -1, &del, nullptr), db, "prepare del");

    Metrics m;
    auto t = Clock::now();
    sqlite_check(sqlite3_exec(db, "BEGIN IMMEDIATE", nullptr, nullptr, nullptr), db, "begin");
    for (auto const& r : records) {
        sqlite3_bind_text(put, 1, r.key.data(), static_cast<int>(r.key.size()), SQLITE_TRANSIENT);
        sqlite3_bind_blob(put, 2, r.value.data(), static_cast<int>(r.value.size()), SQLITE_TRANSIENT);
        sqlite_check(sqlite3_step(put), db, "put"); sqlite3_reset(put); sqlite3_clear_bindings(put);
    }
    sqlite_check(sqlite3_exec(db, "COMMIT", nullptr, nullptr, nullptr), db, "commit");
    m.write_ms = elapsed_ms(t);

    t = Clock::now();
    for (auto const& r : records) {
        sqlite3_bind_text(get, 1, r.key.data(), static_cast<int>(r.key.size()), SQLITE_TRANSIENT);
        int rc = sqlite3_step(get);
        if (rc != SQLITE_ROW) throw std::runtime_error("sqlite sequential miss");
        auto p = static_cast<const char*>(sqlite3_column_blob(get, 0));
        int n = sqlite3_column_bytes(get, 0);
        if (std::string(p, p + n) != r.value) throw std::runtime_error("sqlite sequential mismatch");
        sqlite3_reset(get); sqlite3_clear_bindings(get); ++m.verified;
    }
    m.read_ms = elapsed_ms(t);

    std::mt19937_64 rng(0xBADC0FFEEULL);
    t = Clock::now();
    for (std::size_t i = 0; i < random_reads; ++i) {
        auto const& r = records[rng() % records.size()];
        sqlite3_bind_text(get, 1, r.key.data(), static_cast<int>(r.key.size()), SQLITE_TRANSIENT);
        if (sqlite3_step(get) != SQLITE_ROW) throw std::runtime_error("sqlite random miss");
        sqlite3_reset(get); sqlite3_clear_bindings(get);
    }
    m.random_read_ms = elapsed_ms(t);

    mutate_count = std::min(mutate_count, records.size());
    t = Clock::now();
    sqlite_check(sqlite3_exec(db, "BEGIN IMMEDIATE", nullptr, nullptr, nullptr), db, "begin update");
    for (std::size_t i = 0; i < mutate_count; ++i) {
        std::string v = records[i].value + "U";
        sqlite3_bind_text(put, 1, records[i].key.data(), static_cast<int>(records[i].key.size()), SQLITE_TRANSIENT);
        sqlite3_bind_blob(put, 2, v.data(), static_cast<int>(v.size()), SQLITE_TRANSIENT);
        sqlite_check(sqlite3_step(put), db, "update"); sqlite3_reset(put); sqlite3_clear_bindings(put);
        records[i].value = std::move(v);
    }
    sqlite_check(sqlite3_exec(db, "COMMIT", nullptr, nullptr, nullptr), db, "commit update");
    m.update_ms = elapsed_ms(t);

    t = Clock::now();
    sqlite_check(sqlite3_exec(db, "PRAGMA wal_checkpoint(TRUNCATE)", nullptr, nullptr, nullptr), db, "checkpoint");
    m.checkpoint_ms = elapsed_ms(t);

    std::vector<Record> deleted;
    deleted.reserve(mutate_count / 2);
    t = Clock::now();
    sqlite_check(sqlite3_exec(db, "BEGIN IMMEDIATE", nullptr, nullptr, nullptr), db, "begin delete");
    for (std::size_t i = 0; i < mutate_count; i += 2) {
        sqlite3_bind_text(del, 1, records[i].key.data(), static_cast<int>(records[i].key.size()), SQLITE_TRANSIENT);
        sqlite_check(sqlite3_step(del), db, "delete"); sqlite3_reset(del); sqlite3_clear_bindings(del);
        deleted.push_back(records[i]);
    }
    sqlite_check(sqlite3_exec(db, "COMMIT", nullptr, nullptr, nullptr), db, "commit delete");
    m.delete_ms = elapsed_ms(t);

    sqlite3_finalize(put); sqlite3_finalize(get); sqlite3_finalize(del); sqlite3_close(db); db = nullptr;
    t = Clock::now();
    sqlite_check(sqlite3_open(db_path.c_str(), &db), db, "reopen");
    sqlite_check(sqlite3_prepare_v2(db, "SELECT v FROM kv WHERE k=?", -1, &get, nullptr), db, "reprepare get");
    std::size_t reopen_verified = 0;
    for (std::size_t i = 0; i < records.size(); ++i) {
        bool should_exist = !(i < mutate_count && (i % 2 == 0));
        sqlite3_bind_text(get, 1, records[i].key.data(), static_cast<int>(records[i].key.size()), SQLITE_TRANSIENT);
        int rc = sqlite3_step(get);
        if (should_exist) {
            if (rc != SQLITE_ROW) throw std::runtime_error("sqlite reopen miss");
            auto p = static_cast<const char*>(sqlite3_column_blob(get, 0));
            int n = sqlite3_column_bytes(get, 0);
            if (std::string(p, p + n) != records[i].value) throw std::runtime_error("sqlite reopen mismatch");
            ++reopen_verified;
        } else if (rc == SQLITE_ROW) throw std::runtime_error("sqlite deleted key resurrected");
        sqlite3_reset(get); sqlite3_clear_bindings(get);
    }
    m.reopen_verify_ms = elapsed_ms(t);
    m.verified = reopen_verified;
    sqlite3_finalize(get); sqlite3_close(db);
    m.disk_bytes = directory_bytes(root);
    return m;
}

static Metrics bench_bdr(const fs::path& root, std::vector<Record>& records, std::size_t random_reads,
                         std::size_t mutate_count) {
    fs::create_directories(root);
    bdr::Options opts;
    opts.reserve_bytes = 64ull * 1024ull * 1024ull;
    opts.wal_batch = 512;
    auto db = bdr::Database::open(root, opts);
    Metrics m;

    auto t = Clock::now();
    for (auto const& r : records) db->put(r.key, r.value);
    db->sync();
    m.write_ms = elapsed_ms(t);

    t = Clock::now();
    for (auto const& r : records) {
        auto v = db->get(r.key);
        if (!v || *v != r.value) throw std::runtime_error("bdr sequential mismatch");
        ++m.verified;
    }
    m.read_ms = elapsed_ms(t);

    std::mt19937_64 rng(0xBADC0FFEEULL);
    t = Clock::now();
    for (std::size_t i = 0; i < random_reads; ++i) {
        auto const& r = records[rng() % records.size()];
        if (!db->get(r.key)) throw std::runtime_error("bdr random miss");
    }
    m.random_read_ms = elapsed_ms(t);

    mutate_count = std::min(mutate_count, records.size());
    t = Clock::now();
    for (std::size_t i = 0; i < mutate_count; ++i) {
        records[i].value += "U";
        db->put(records[i].key, records[i].value);
    }
    db->sync();
    m.update_ms = elapsed_ms(t);

    t = Clock::now(); db->checkpoint(); m.checkpoint_ms = elapsed_ms(t);

    t = Clock::now();
    for (std::size_t i = 0; i < mutate_count; i += 2) db->erase(records[i].key);
    db->sync();
    m.delete_ms = elapsed_ms(t);

    db->close(); db.reset();
    t = Clock::now();
    db = bdr::Database::open(root, opts);
    std::size_t reopen_verified = 0;
    for (std::size_t i = 0; i < records.size(); ++i) {
        bool should_exist = !(i < mutate_count && (i % 2 == 0));
        auto v = db->get(records[i].key);
        if (should_exist) {
            if (!v || *v != records[i].value) throw std::runtime_error("bdr reopen mismatch");
            ++reopen_verified;
        } else if (v) throw std::runtime_error("bdr deleted key resurrected");
    }
    m.reopen_verify_ms = elapsed_ms(t);
    m.verified = reopen_verified;
    db->close();
    m.disk_bytes = directory_bytes(root);
    return m;
}

static void print_metrics(const char* name, const Metrics& m) {
    std::cout << "\"" << name << "\":{";
    std::cout << "\"write_ms\":" << m.write_ms << ",";
    std::cout << "\"read_ms\":" << m.read_ms << ",";
    std::cout << "\"random_read_ms\":" << m.random_read_ms << ",";
    std::cout << "\"update_ms\":" << m.update_ms << ",";
    std::cout << "\"delete_ms\":" << m.delete_ms << ",";
    std::cout << "\"checkpoint_ms\":" << m.checkpoint_ms << ",";
    std::cout << "\"reopen_verify_ms\":" << m.reopen_verify_ms << ",";
    std::cout << "\"disk_bytes\":" << m.disk_bytes << ",";
    std::cout << "\"verified\":" << m.verified << "}";
}

int main(int argc, char** argv) {
    if (argc != 6) {
        std::cerr << "usage: native_direct ROOT MEMORIES PAYLOAD_BYTES RANDOM_READS MUTATE_COUNT\n";
        return 2;
    }
    try {
        fs::path root = argv[1];
        std::size_t memories = std::stoull(argv[2]);
        std::size_t payload_bytes = std::stoull(argv[3]);
        std::size_t random_reads = std::stoull(argv[4]);
        std::size_t mutate_count = std::stoull(argv[5]);
        fs::remove_all(root); fs::create_directories(root);

        auto mt = Clock::now();
        auto baseline = materialize(memories, payload_bytes, 3);
        double materialize_ms = elapsed_ms(mt);
        auto sqlite_records = baseline;
        auto bdr_records = baseline;

        auto sm = bench_sqlite(root / "sqlite", sqlite_records, random_reads, mutate_count);
        auto bm = bench_bdr(root / "bdr", bdr_records, random_reads, mutate_count);

        std::size_t expected_remaining = baseline.size() - (std::min(mutate_count, baseline.size()) + 1) / 2;
        if (sm.verified != expected_remaining || bm.verified != expected_remaining)
            throw std::runtime_error("reopen verification count mismatch");

        std::cout << std::fixed << std::setprecision(3);
        std::cout << "{";
        std::cout << "\"schema\":\"memoria-bdr-native-direct-v1\",";
        std::cout << "\"bdr_version\":\"v1.0.0\",";
        std::cout << "\"memories\":" << memories << ",";
        std::cout << "\"payload_bytes\":" << payload_bytes << ",";
        std::cout << "\"logical_records\":" << baseline.size() << ",";
        std::cout << "\"random_reads\":" << random_reads << ",";
        std::cout << "\"mutate_count\":" << mutate_count << ",";
        std::cout << "\"materialize_ms\":" << materialize_ms << ",";
        print_metrics("sqlite_direct", sm); std::cout << ",";
        print_metrics("bdr_direct", bm);
        std::cout << "}\n";
        return 0;
    } catch (std::exception const& e) {
        std::cerr << "ERROR: " << e.what() << "\n";
        return 1;
    }
}
