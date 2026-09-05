#include <bdr/database.hpp>
#include <sqlite3.h>

#include <chrono>
#include <cstdint>
#include <cstdlib>
#include <filesystem>
#include <iomanip>
#include <iostream>
#include <optional>
#include <random>
#include <sstream>
#include <stdexcept>
#include <string>
#include <unordered_map>

namespace fs = std::filesystem;
using Clock = std::chrono::steady_clock;

static double elapsed_ms(Clock::time_point t) {
    return std::chrono::duration<double, std::milli>(Clock::now() - t).count();
}

static void sqlite_check(int rc, sqlite3* db, const char* what) {
    if (rc != SQLITE_OK && rc != SQLITE_DONE && rc != SQLITE_ROW) {
        throw std::runtime_error(std::string(what) + ": " + (db ? sqlite3_errmsg(db) : "sqlite error"));
    }
}

static std::string key_for(std::size_t i) {
    std::ostringstream os;
    os << "m:resilience-" << std::setw(10) << std::setfill('0') << i;
    return os.str();
}

static std::string value_for(std::size_t i, std::size_t bytes = 128) {
    std::string out(bytes, '\0');
    std::uint64_t x = 0x9E3779B97F4A7C15ULL ^ (i * 0xD1B54A32D192ED03ULL);
    for (std::size_t j = 0; j < bytes; ++j) {
        x ^= x >> 12; x ^= x << 25; x ^= x >> 27;
        x *= 2685821657736338717ULL;
        out[j] = static_cast<char>((x >> 56) & 0xff);
    }
    return out;
}

static bdr::Options bdr_options() {
    bdr::Options o;
    o.keep_size_preallocation = false;
    o.reserve_bytes = 0;
    o.wal_batch = 512;
    return o;
}

static int fsync_gate(const fs::path& root, std::size_t operations, std::size_t value_bytes) {
    fs::remove_all(root);
    fs::create_directories(root);

    double sqlite_ms = 0.0;
    {
        sqlite3* db = nullptr;
        auto path = root / "sqlite" / "direct.sqlite3";
        fs::create_directories(path.parent_path());
        sqlite_check(sqlite3_open(path.string().c_str(), &db), db, "sqlite open");
        sqlite_check(sqlite3_exec(db,
            "PRAGMA journal_mode=WAL; PRAGMA synchronous=FULL; CREATE TABLE kv(k TEXT PRIMARY KEY,v BLOB NOT NULL);",
            nullptr, nullptr, nullptr), db, "sqlite schema");
        sqlite3_stmt* put = nullptr;
        sqlite_check(sqlite3_prepare_v2(db, "INSERT INTO kv(k,v) VALUES(?,?)", -1, &put, nullptr), db, "sqlite prepare");
        auto t = Clock::now();
        for (std::size_t i = 0; i < operations; ++i) {
            auto k = key_for(i); auto v = value_for(i, value_bytes);
            sqlite3_bind_text(put, 1, k.data(), static_cast<int>(k.size()), SQLITE_TRANSIENT);
            sqlite3_bind_blob(put, 2, v.data(), static_cast<int>(v.size()), SQLITE_TRANSIENT);
            sqlite_check(sqlite3_step(put), db, "sqlite durable put");
            sqlite3_reset(put); sqlite3_clear_bindings(put);
        }
        sqlite_ms = elapsed_ms(t);
        sqlite3_finalize(put); sqlite3_close(db);

        sqlite_check(sqlite3_open(path.string().c_str(), &db), db, "sqlite reopen");
        sqlite3_stmt* get = nullptr;
        sqlite_check(sqlite3_prepare_v2(db, "SELECT v FROM kv WHERE k=?", -1, &get, nullptr), db, "sqlite get prepare");
        for (std::size_t i = 0; i < operations; ++i) {
            auto k = key_for(i); auto expected = value_for(i, value_bytes);
            sqlite3_bind_text(get, 1, k.data(), static_cast<int>(k.size()), SQLITE_TRANSIENT);
            if (sqlite3_step(get) != SQLITE_ROW) throw std::runtime_error("sqlite fsync reopen miss");
            auto p = static_cast<const char*>(sqlite3_column_blob(get, 0));
            int n = sqlite3_column_bytes(get, 0);
            if (std::string(p, p + n) != expected) throw std::runtime_error("sqlite fsync reopen mismatch");
            sqlite3_reset(get); sqlite3_clear_bindings(get);
        }
        sqlite3_finalize(get); sqlite3_close(db);
    }

    double bdr_ms = 0.0;
    {
        auto path = root / "bdr";
        auto db = bdr::Database::open(path, bdr_options());
        auto t = Clock::now();
        for (std::size_t i = 0; i < operations; ++i) db->put_sync(key_for(i), value_for(i, value_bytes));
        bdr_ms = elapsed_ms(t);
        if (db->durable_sequence() != operations) throw std::runtime_error("BDR durable sequence mismatch after put_sync");
        db->close(); db.reset();
        db = bdr::Database::open(path, bdr_options());
        for (std::size_t i = 0; i < operations; ++i) {
            auto got = db->get(key_for(i));
            if (!got || *got != value_for(i, value_bytes)) throw std::runtime_error("BDR fsync reopen mismatch");
        }
        if (db->durable_sequence() != operations) throw std::runtime_error("BDR durable sequence mismatch after reopen");
        db->close();
    }

    std::cout << "{\"gate\":\"per_operation_fsync\",\"operations\":" << operations
              << ",\"value_bytes\":" << value_bytes
              << ",\"sqlite_ms\":" << sqlite_ms
              << ",\"bdr_ms\":" << bdr_ms
              << ",\"sqlite_over_bdr\":" << (bdr_ms ? sqlite_ms / bdr_ms : 0.0)
              << ",\"status\":\"PASS\"}\n";
    return 0;
}

static int checkpoint_churn_gate(const fs::path& root, std::size_t cycles,
                                 std::size_t ops_per_cycle, std::size_t key_space) {
    fs::remove_all(root);
    fs::create_directories(root);
    std::mt19937_64 rng(0xBD0100C1ULL);
    std::unordered_map<std::string, std::string> oracle;
    oracle.reserve(key_space);

    auto sqlite_root = root / "sqlite";
    auto bdr_root = root / "bdr";
    fs::create_directories(sqlite_root);
    fs::create_directories(bdr_root);
    auto sqlite_path = sqlite_root / "churn.sqlite3";

    double sqlite_checkpoint_total = 0.0;
    double bdr_checkpoint_total = 0.0;
    std::uint64_t accepted = 0;

    // Initialize SQLite schema once.
    {
        sqlite3* db = nullptr;
        sqlite_check(sqlite3_open(sqlite_path.string().c_str(), &db), db, "sqlite churn open init");
        sqlite_check(sqlite3_exec(db,
            "PRAGMA journal_mode=WAL; PRAGMA synchronous=FULL; CREATE TABLE kv(k TEXT PRIMARY KEY,v BLOB NOT NULL);",
            nullptr, nullptr, nullptr), db, "sqlite churn schema");
        sqlite3_close(db);
    }

    for (std::size_t cycle = 0; cycle < cycles; ++cycle) {
        struct Op { bool erase; std::string key; std::string value; };
        std::vector<Op> ops;
        ops.reserve(ops_per_cycle);
        for (std::size_t j = 0; j < ops_per_cycle; ++j) {
            auto id = rng() % key_space;
            std::string k = "m:churn-" + std::to_string(id);
            bool erase = (rng() % 100) >= 75;
            std::string v = erase ? std::string{} : ("c" + std::to_string(cycle) + "-o" + std::to_string(j) + "-" + std::to_string(rng()));
            ops.push_back({erase, k, v});
            if (erase) oracle.erase(k); else oracle[k] = v;
            ++accepted;
        }

        // SQLite same mutation stream.
        sqlite3* sq = nullptr;
        sqlite_check(sqlite3_open(sqlite_path.string().c_str(), &sq), sq, "sqlite churn open");
        sqlite_check(sqlite3_exec(sq, "PRAGMA synchronous=FULL; BEGIN IMMEDIATE", nullptr, nullptr, nullptr), sq, "sqlite churn begin");
        sqlite3_stmt* put = nullptr; sqlite3_stmt* del = nullptr;
        sqlite_check(sqlite3_prepare_v2(sq, "INSERT INTO kv(k,v) VALUES(?,?) ON CONFLICT(k) DO UPDATE SET v=excluded.v", -1, &put, nullptr), sq, "sqlite churn put prepare");
        sqlite_check(sqlite3_prepare_v2(sq, "DELETE FROM kv WHERE k=?", -1, &del, nullptr), sq, "sqlite churn del prepare");
        for (auto const& op : ops) {
            auto* st = op.erase ? del : put;
            sqlite3_bind_text(st, 1, op.key.data(), static_cast<int>(op.key.size()), SQLITE_TRANSIENT);
            if (!op.erase) sqlite3_bind_blob(st, 2, op.value.data(), static_cast<int>(op.value.size()), SQLITE_TRANSIENT);
            sqlite_check(sqlite3_step(st), sq, "sqlite churn mutation");
            sqlite3_reset(st); sqlite3_clear_bindings(st);
        }
        sqlite_check(sqlite3_exec(sq, "COMMIT", nullptr, nullptr, nullptr), sq, "sqlite churn commit");
        auto ts = Clock::now();
        sqlite_check(sqlite3_exec(sq, "PRAGMA wal_checkpoint(TRUNCATE)", nullptr, nullptr, nullptr), sq, "sqlite churn checkpoint");
        sqlite_checkpoint_total += elapsed_ms(ts);
        sqlite3_finalize(put); sqlite3_finalize(del); sqlite3_close(sq);

        // BDR same mutation stream.
        auto bd = bdr::Database::open(bdr_root, bdr_options());
        bdr::Ticket last{};
        for (auto const& op : ops) last = op.erase ? bd->erase(op.key) : bd->put(op.key, op.value);
        if (last) bd->wait(last);
        bd->sync();
        auto tb = Clock::now(); bd->checkpoint(); bdr_checkpoint_total += elapsed_ms(tb);
        bd->close(); bd.reset();

        // Full reopen oracle validation every cycle for both engines.
        sqlite_check(sqlite3_open(sqlite_path.string().c_str(), &sq), sq, "sqlite churn reopen");
        sqlite3_stmt* get = nullptr;
        sqlite_check(sqlite3_prepare_v2(sq, "SELECT v FROM kv WHERE k=?", -1, &get, nullptr), sq, "sqlite churn get prepare");
        for (auto const& [k, v] : oracle) {
            sqlite3_bind_text(get, 1, k.data(), static_cast<int>(k.size()), SQLITE_TRANSIENT);
            if (sqlite3_step(get) != SQLITE_ROW) throw std::runtime_error("sqlite churn reopen miss");
            auto p = static_cast<const char*>(sqlite3_column_blob(get, 0)); int n = sqlite3_column_bytes(get, 0);
            if (std::string(p, p+n) != v) throw std::runtime_error("sqlite churn oracle mismatch");
            sqlite3_reset(get); sqlite3_clear_bindings(get);
        }
        sqlite3_finalize(get); sqlite3_close(sq);

        bd = bdr::Database::open(bdr_root, bdr_options());
        if (bd->size() != oracle.size()) throw std::runtime_error("BDR churn size mismatch");
        for (auto const& [k, v] : oracle) {
            auto got = bd->get(k);
            if (!got || *got != v) throw std::runtime_error("BDR churn oracle mismatch");
        }
        bd->close();
    }

    std::cout << "{\"gate\":\"checkpoint_churn\",\"cycles\":" << cycles
              << ",\"ops_per_cycle\":" << ops_per_cycle
              << ",\"accepted_mutations\":" << accepted
              << ",\"final_records\":" << oracle.size()
              << ",\"sqlite_checkpoint_total_ms\":" << sqlite_checkpoint_total
              << ",\"bdr_checkpoint_total_ms\":" << bdr_checkpoint_total
              << ",\"status\":\"PASS\"}\n";
    return 0;
}

static int crash_writer(const std::string& engine, const fs::path& root,
                        std::size_t durable_count, std::size_t volatile_count) {
    fs::remove_all(root);
    fs::create_directories(root);
    if (engine == "bdr") {
        auto db = bdr::Database::open(root / "bdr", bdr_options());
        for (std::size_t i = 0; i < durable_count; ++i) db->put(key_for(i), value_for(i));
        db->sync();
        if (db->durable_sequence() < durable_count) throw std::runtime_error("BDR durable prefix not synced");
        for (std::size_t i = durable_count; i < durable_count + volatile_count; ++i) db->put(key_for(i), value_for(i));
        std::_Exit(99); // Intentional hard process termination: no close(), no destructors.
    }
    if (engine == "sqlite") {
        auto path = root / "sqlite" / "crash.sqlite3";
        fs::create_directories(path.parent_path());
        sqlite3* db = nullptr;
        sqlite_check(sqlite3_open(path.string().c_str(), &db), db, "sqlite crash open");
        sqlite_check(sqlite3_exec(db,
            "PRAGMA journal_mode=WAL; PRAGMA synchronous=FULL; CREATE TABLE kv(k TEXT PRIMARY KEY,v BLOB NOT NULL);",
            nullptr, nullptr, nullptr), db, "sqlite crash schema");
        sqlite3_stmt* put = nullptr;
        sqlite_check(sqlite3_prepare_v2(db, "INSERT INTO kv(k,v) VALUES(?,?)", -1, &put, nullptr), db, "sqlite crash put prepare");
        sqlite_check(sqlite3_exec(db, "BEGIN IMMEDIATE", nullptr, nullptr, nullptr), db, "sqlite durable begin");
        for (std::size_t i = 0; i < durable_count; ++i) {
            auto k=key_for(i); auto v=value_for(i);
            sqlite3_bind_text(put,1,k.data(),static_cast<int>(k.size()),SQLITE_TRANSIENT);
            sqlite3_bind_blob(put,2,v.data(),static_cast<int>(v.size()),SQLITE_TRANSIENT);
            sqlite_check(sqlite3_step(put),db,"sqlite durable put"); sqlite3_reset(put); sqlite3_clear_bindings(put);
        }
        sqlite_check(sqlite3_exec(db, "COMMIT", nullptr, nullptr, nullptr), db, "sqlite durable commit");
        sqlite_check(sqlite3_exec(db, "BEGIN IMMEDIATE", nullptr, nullptr, nullptr), db, "sqlite volatile begin");
        for (std::size_t i = durable_count; i < durable_count + volatile_count; ++i) {
            auto k=key_for(i); auto v=value_for(i);
            sqlite3_bind_text(put,1,k.data(),static_cast<int>(k.size()),SQLITE_TRANSIENT);
            sqlite3_bind_blob(put,2,v.data(),static_cast<int>(v.size()),SQLITE_TRANSIENT);
            sqlite_check(sqlite3_step(put),db,"sqlite volatile put"); sqlite3_reset(put); sqlite3_clear_bindings(put);
        }
        std::_Exit(99);
    }
    throw std::runtime_error("unknown crash engine");
}

static int crash_verify(const std::string& engine, const fs::path& root,
                        std::size_t durable_count, std::size_t volatile_count) {
    std::size_t volatile_survivors = 0;
    if (engine == "bdr") {
        auto db = bdr::Database::open(root / "bdr", bdr_options());
        for (std::size_t i = 0; i < durable_count; ++i) {
            auto got=db->get(key_for(i));
            if (!got || *got!=value_for(i)) throw std::runtime_error("BDR lost/corrupted synced prefix after crash");
        }
        for (std::size_t i = durable_count; i < durable_count + volatile_count; ++i) {
            auto got=db->get(key_for(i));
            if (got) { if (*got!=value_for(i)) throw std::runtime_error("BDR corrupted volatile value after crash"); ++volatile_survivors; }
        }
        db->close();
    } else if (engine == "sqlite") {
        auto path=root/"sqlite"/"crash.sqlite3";
        sqlite3* db=nullptr;
        sqlite_check(sqlite3_open(path.string().c_str(),&db),db,"sqlite crash verify open");
        sqlite3_stmt* get=nullptr;
        sqlite_check(sqlite3_prepare_v2(db,"SELECT v FROM kv WHERE k=?",-1,&get,nullptr),db,"sqlite crash verify prepare");
        for (std::size_t i=0;i<durable_count+volatile_count;++i) {
            auto k=key_for(i);
            sqlite3_bind_text(get,1,k.data(),static_cast<int>(k.size()),SQLITE_TRANSIENT);
            int rc=sqlite3_step(get);
            if (i<durable_count) {
                if (rc!=SQLITE_ROW) throw std::runtime_error("SQLite lost durable prefix after crash");
                auto p=static_cast<const char*>(sqlite3_column_blob(get,0)); int n=sqlite3_column_bytes(get,0);
                if (std::string(p,p+n)!=value_for(i)) throw std::runtime_error("SQLite corrupted durable prefix after crash");
            } else if (rc==SQLITE_ROW) {
                ++volatile_survivors;
            }
            sqlite3_reset(get); sqlite3_clear_bindings(get);
        }
        sqlite3_finalize(get); sqlite3_close(db);
        if (volatile_survivors != 0) throw std::runtime_error("SQLite exposed uncommitted volatile suffix after crash");
    } else throw std::runtime_error("unknown crash engine");

    std::cout << "{\"gate\":\"forced_crash_recovery\",\"engine\":\"" << engine
              << "\",\"durable_count\":" << durable_count
              << ",\"volatile_count\":" << volatile_count
              << ",\"volatile_survivors\":" << volatile_survivors
              << ",\"status\":\"PASS\"}\n";
    return 0;
}

int main(int argc, char** argv) {
    try {
        if (argc < 2) throw std::runtime_error("missing mode");
        std::string mode=argv[1];
        if (mode=="fsync" && argc==5) return fsync_gate(argv[2],std::stoull(argv[3]),std::stoull(argv[4]));
        if (mode=="churn" && argc==6) return checkpoint_churn_gate(argv[2],std::stoull(argv[3]),std::stoull(argv[4]),std::stoull(argv[5]));
        if (mode=="crash-write" && argc==6) return crash_writer(argv[2],argv[3],std::stoull(argv[4]),std::stoull(argv[5]));
        if (mode=="crash-verify" && argc==6) return crash_verify(argv[2],argv[3],std::stoull(argv[4]),std::stoull(argv[5]));
        throw std::runtime_error("usage: resilience fsync ROOT OPS VALUE_BYTES | churn ROOT CYCLES OPS_PER_CYCLE KEY_SPACE | crash-write ENGINE ROOT DURABLE VOLATILE | crash-verify ENGINE ROOT DURABLE VOLATILE");
    } catch (const std::exception& e) {
        std::cerr << "RESILIENCE FAIL: " << e.what() << '\n';
        return 1;
    }
}
