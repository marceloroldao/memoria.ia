#pragma once

// Linux-only compatibility shim used by Memoria.ia's experimental BDR v1.1
// integration. It preserves the frozen bdr::Database surface expected by the
// existing pybind layer while routing pending logical writes through the
// additive bdr::AtomicDatabase API.
//
// The real v1.1 database.hpp is included with Database temporarily renamed so
// its public structs (Options, Ticket, Operation, OperationType, IndexStats)
// remain available without colliding with the shim class below.
#define Database LegacyDatabase
#include_next <bdr/database.hpp>
#undef Database

#include <bdr/atomic_database.hpp>

#include <filesystem>
#include <memory>
#include <mutex>
#include <optional>
#include <string>
#include <unordered_map>
#include <utility>
#include <vector>

namespace bdr {

class Database {
public:
    static std::unique_ptr<Database> open(const std::filesystem::path& directory,
                                          Options options = {}) {
        return std::unique_ptr<Database>(
            new Database(AtomicDatabase::open(directory), std::move(options)));
    }

    ~Database() {
        try {
            close();
        } catch (...) {
        }
    }

    Database(const Database&) = delete;
    Database& operator=(const Database&) = delete;

    Ticket submit(Operation operation) {
        std::lock_guard<std::mutex> guard(mu_);
        ensure_open();
        remember_base_state(operation.key);
        const auto ticket = Ticket{visible_sequence_locked()};
        if (operation.type == OperationType::Put) {
            pending_view_[operation.key] = operation.value;
        } else {
            pending_view_[operation.key] = std::nullopt;
        }
        pending_.push_back(std::move(operation));
        return ticket;
    }

    Ticket put(std::string key, std::string value) {
        Operation op;
        op.type = OperationType::Put;
        op.key = std::move(key);
        op.value = std::move(value);
        return submit(std::move(op));
    }

    Ticket erase(std::string key) {
        Operation op;
        op.type = OperationType::Delete;
        op.key = std::move(key);
        return submit(std::move(op));
    }

    void put_sync(std::string key, std::string value) {
        put(std::move(key), std::move(value));
        sync();
    }

    void erase_sync(std::string key) {
        erase(std::move(key));
        sync();
    }

    std::optional<std::string> get(const std::string& key) const {
        std::lock_guard<std::mutex> guard(mu_);
        ensure_open();
        auto it = pending_view_.find(key);
        if (it != pending_view_.end()) return it->second;
        return atomic_->get(key);
    }

    bool contains(const std::string& key) const {
        return static_cast<bool>(get(key));
    }

    void wait(Ticket) {
        // Pending writes are immediately visible through the in-process overlay.
        // Durability remains explicit through sync(), matching the Memoria.ia
        // contract used by the existing native binding.
    }

    void sync() {
        std::lock_guard<std::mutex> guard(mu_);
        ensure_open();
        flush_locked();
    }

    void checkpoint() {
        // AtomicDatabase v1.1 intentionally does not expose checkpoint. For the
        // compatibility surface, checkpoint therefore means: establish a durable
        // atomic boundary. Legacy BDR3 files remain untouched by the BDW4 path.
        sync();
    }

    void close() {
        std::lock_guard<std::mutex> guard(mu_);
        if (!atomic_) return;
        flush_locked();
        atomic_.reset();
        pending_.clear();
        pending_view_.clear();
        base_exists_.clear();
    }

    std::uint64_t last_sequence() const noexcept {
        try {
            std::lock_guard<std::mutex> guard(mu_);
            if (!atomic_) return 0;
            return visible_sequence_locked();
        } catch (...) {
            return 0;
        }
    }

    std::uint64_t durable_sequence() const noexcept {
        try {
            std::lock_guard<std::mutex> guard(mu_);
            return atomic_ ? atomic_->durable_sequence() : 0;
        } catch (...) {
            return 0;
        }
    }

    std::size_t size() const {
        std::lock_guard<std::mutex> guard(mu_);
        ensure_open();
        std::size_t total = atomic_->size();
        for (const auto& [key, current] : pending_view_) {
            const bool existed = base_exists_.at(key);
            const bool exists_now = current.has_value();
            if (!existed && exists_now) {
                ++total;
            } else if (existed && !exists_now) {
                --total;
            }
        }
        return total;
    }

    IndexStats index_stats() const {
        IndexStats stats;
        stats.records = size();
        return stats;
    }

private:
    Database(std::unique_ptr<AtomicDatabase> atomic, Options options)
        : atomic_(std::move(atomic)), options_(std::move(options)) {}

    void ensure_open() const {
        if (!atomic_) throw std::runtime_error("BDR database is closed");
    }

    void remember_base_state(const std::string& key) {
        if (base_exists_.find(key) != base_exists_.end()) return;
        base_exists_[key] = atomic_->contains(key);
    }

    std::uint64_t visible_sequence_locked() const {
        const auto base = atomic_->last_sequence();
        return pending_.empty() ? base : base + 1;
    }

    void flush_locked() {
        if (pending_.empty()) {
            atomic_->sync();
            return;
        }

        // The whole pending logical unit crosses one BDW4 commit boundary.
        // With Memoria.ia's default sync_every_memories=1 this is exactly one
        // logical memory. Explicit deferred-sync policies may group several
        // logical memories into one stronger all-or-nothing durable boundary.
        atomic_->write_batch(pending_, DurabilityMode::BatchSync);
        pending_.clear();
        pending_view_.clear();
        base_exists_.clear();
    }

    mutable std::mutex mu_;
    std::unique_ptr<AtomicDatabase> atomic_;
    Options options_;
    std::vector<Operation> pending_;
    std::unordered_map<std::string, std::optional<std::string>> pending_view_;
    std::unordered_map<std::string, bool> base_exists_;
};

}  // namespace bdr
