#include <bdr/database.hpp>
#include <pybind11/pybind11.h>
#include <pybind11/stl.h>

#include <array>
#include <cstdint>
#include <cstring>
#include <filesystem>
#include <memory>
#include <sstream>
#include <string>
#include <unordered_map>
#include <utility>
#include <vector>

namespace py = pybind11;

namespace {

std::string as_bytes(py::handle value) {
    if (!PyBytes_Check(value.ptr())) {
        throw py::type_error("value must be bytes");
    }
    char* data = nullptr;
    Py_ssize_t size = 0;
    if (PyBytes_AsStringAndSize(value.ptr(), &data, &size) != 0) {
        throw py::error_already_set();
    }
    return std::string(data, static_cast<std::size_t>(size));
}

static inline std::uint64_t rotr64(std::uint64_t x, unsigned c) {
    return (x >> c) | (x << (64 - c));
}

static inline std::uint64_t load64(const unsigned char* p) {
    std::uint64_t v;
    std::memcpy(&v, p, sizeof(v));
#if __BYTE_ORDER__ == __ORDER_BIG_ENDIAN__
    v = __builtin_bswap64(v);
#endif
    return v;
}

static inline void store64(unsigned char* p, std::uint64_t v) {
#if __BYTE_ORDER__ == __ORDER_BIG_ENDIAN__
    v = __builtin_bswap64(v);
#endif
    std::memcpy(p, &v, sizeof(v));
}

constexpr std::array<std::uint64_t, 8> B2_IV = {
    0x6a09e667f3bcc908ULL, 0xbb67ae8584caa73bULL,
    0x3c6ef372fe94f82bULL, 0xa54ff53a5f1d36f1ULL,
    0x510e527fade682d1ULL, 0x9b05688c2b3e6c1fULL,
    0x1f83d9abfb41bd6bULL, 0x5be0cd19137e2179ULL,
};

constexpr unsigned char B2_SIGMA[12][16] = {
    {0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15},
    {14,10,4,8,9,15,13,6,1,12,0,2,11,7,5,3},
    {11,8,12,0,5,2,15,13,10,14,3,6,7,1,9,4},
    {7,9,3,1,13,12,11,14,2,6,5,10,4,0,15,8},
    {9,0,5,7,2,4,10,15,14,1,11,12,6,8,3,13},
    {2,12,6,10,0,11,8,3,4,13,7,5,15,14,1,9},
    {12,5,1,15,14,13,4,10,0,7,6,3,9,2,8,11},
    {13,11,7,14,12,1,3,9,5,0,15,4,8,6,2,10},
    {6,15,14,9,11,3,0,8,12,2,13,7,1,4,10,5},
    {10,2,8,4,7,6,1,5,15,11,9,14,3,12,13,0},
    {0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15},
    {14,10,4,8,9,15,13,6,1,12,0,2,11,7,5,3},
};

struct Blake2b128 {
    std::array<std::uint64_t, 8> h = B2_IV;
    std::uint64_t t0 = 0, t1 = 0;
    std::array<unsigned char, 128> buf{};
    std::size_t buflen = 0;

    Blake2b128() { h[0] ^= 0x01010010ULL; }  // fanout=1, depth=1, digest=16

    void compress(const unsigned char block[128], bool last) {
        std::uint64_t m[16], v[16];
        for (int i = 0; i < 16; ++i) m[i] = load64(block + i * 8);
        for (int i = 0; i < 8; ++i) v[i] = h[i];
        for (int i = 0; i < 8; ++i) v[i + 8] = B2_IV[i];
        v[12] ^= t0;
        v[13] ^= t1;
        if (last) v[14] = ~v[14];

#define G(a,b,c,d,x,y) do { \
    v[a] = v[a] + v[b] + (x); v[d] = rotr64(v[d] ^ v[a], 32); \
    v[c] = v[c] + v[d];       v[b] = rotr64(v[b] ^ v[c], 24); \
    v[a] = v[a] + v[b] + (y); v[d] = rotr64(v[d] ^ v[a], 16); \
    v[c] = v[c] + v[d];       v[b] = rotr64(v[b] ^ v[c], 63); \
} while (0)
        for (int r = 0; r < 12; ++r) {
            const auto* s = B2_SIGMA[r];
            G(0,4,8,12,m[s[0]],m[s[1]]); G(1,5,9,13,m[s[2]],m[s[3]]);
            G(2,6,10,14,m[s[4]],m[s[5]]); G(3,7,11,15,m[s[6]],m[s[7]]);
            G(0,5,10,15,m[s[8]],m[s[9]]); G(1,6,11,12,m[s[10]],m[s[11]]);
            G(2,7,8,13,m[s[12]],m[s[13]]); G(3,4,9,14,m[s[14]],m[s[15]]);
        }
#undef G
        for (int i = 0; i < 8; ++i) h[i] ^= v[i] ^ v[i + 8];
    }

    void increment(std::uint64_t n) {
        t0 += n;
        if (t0 < n) ++t1;
    }

    void update(const unsigned char* in, std::size_t len) {
        while (len > 0) {
            const std::size_t space = 128 - buflen;
            const std::size_t take = len < space ? len : space;
            std::memcpy(buf.data() + buflen, in, take);
            buflen += take;
            in += take;
            len -= take;
            if (buflen == 128 && len > 0) {
                increment(128);
                compress(buf.data(), false);
                buflen = 0;
            }
        }
    }

    std::array<unsigned char, 16> final() {
        increment(static_cast<std::uint64_t>(buflen));
        std::memset(buf.data() + buflen, 0, 128 - buflen);
        compress(buf.data(), true);
        std::array<unsigned char, 16> out{};
        unsigned char full[64];
        for (int i = 0; i < 8; ++i) store64(full + i * 8, h[i]);
        std::memcpy(out.data(), full, 16);
        return out;
    }
};

std::string digest_payload_native(const char* data, std::size_t len, int layer) {
    Blake2b128 ctx;
    unsigned char prefix[2] = {
        static_cast<unsigned char>((layer >> 8) & 0xff),
        static_cast<unsigned char>(layer & 0xff),
    };
    ctx.update(prefix, 2);
    ctx.update(reinterpret_cast<const unsigned char*>(data), len);
    auto digest = ctx.final();
    static constexpr char hex[] = "0123456789abcdef";
    std::string out(32, '0');
    for (std::size_t i = 0; i < digest.size(); ++i) {
        out[i * 2] = hex[digest[i] >> 4];
        out[i * 2 + 1] = hex[digest[i] & 0x0f];
    }
    return out;
}

std::uint64_t decode_u64(const std::optional<std::string>& value) {
    if (!value) return 0;
    return static_cast<std::uint64_t>(std::stoull(*value));
}

std::string encode_u64(std::uint64_t value) { return std::to_string(value); }

class NativeDatabase {
public:
    NativeDatabase(const std::string& path, std::size_t reserve_bytes, std::size_t wal_batch) {
        bdr::Options opts;
        opts.reserve_bytes = reserve_bytes;
        opts.wal_batch = wal_batch;
        db_ = bdr::Database::open(std::filesystem::path(path), opts);
    }

    ~NativeDatabase() {
        try { if (db_) db_->close(); } catch (...) {}
    }

    py::object get(const std::string& key) const {
        auto value = db_->get(key);
        if (!value) return py::none();
        return py::bytes(value->data(), value->size());
    }

    bool contains(const std::string& key) const { return db_->contains(key); }

    std::vector<bool> contains_many(const std::vector<std::string>& keys) const {
        std::vector<bool> result;
        result.reserve(keys.size());
        py::gil_scoped_release release;
        for (const auto& key : keys) result.push_back(db_->contains(key));
        return result;
    }

    std::uint64_t put_many(py::iterable rows, bool durable) {
        std::vector<std::pair<std::string, std::string>> materialized;
        for (py::handle item : rows) {
            py::tuple row = py::cast<py::tuple>(item);
            if (row.size() != 2) throw py::value_error("put_many rows must be (key, bytes)");
            materialized.emplace_back(py::cast<std::string>(row[0]), as_bytes(row[1]));
        }
        std::uint64_t last = 0;
        {
            py::gil_scoped_release release;
            for (auto& [key, value] : materialized) {
                auto ticket = db_->put(std::move(key), std::move(value));
                last = ticket.sequence;
            }
            if (durable) db_->sync();
        }
        return last;
    }

    py::dict add_resolutive_memory(const std::string& memory_id, py::bytes payload, int max_layer, bool durable) {
        if (max_layer < 0 || max_layer > 30) throw py::value_error("max_layer must be in [0, 30]");
        const std::string data = as_bytes(payload);
        const std::string memory_key = "m:" + memory_id;

        std::uint64_t memories = 0, nodes = 0, occurrences_count = 0;
        std::vector<std::uint64_t> per_layer(static_cast<std::size_t>(max_layer + 1), 0);

        {
            py::gil_scoped_release release;
            if (db_->contains(memory_key)) throw std::runtime_error("memory already exists: " + memory_id);

            memories = decode_u64(db_->get("meta:memories"));
            nodes = decode_u64(db_->get("meta:unique_nodes"));
            occurrences_count = decode_u64(db_->get("meta:occurrences"));
            for (int layer = 0; layer <= max_layer; ++layer) {
                per_layer[static_cast<std::size_t>(layer)] = decode_u64(db_->get("meta:nodes_layer:" + std::to_string(layer)));
            }

            std::unordered_map<std::string, std::pair<int, std::string>> candidates;
            candidates.reserve(data.size() * 2 + 8);
            std::vector<std::pair<std::string, std::string>> occurrences;
            occurrences.reserve(data.size() * 2 + 8);

            for (int layer = 0; layer <= max_layer; ++layer) {
                const std::size_t width = static_cast<std::size_t>(1ULL << layer);
                std::uint64_t local_time = 0;
                for (std::size_t offset = 0; offset < data.size(); offset += width, ++local_time) {
                    const std::size_t len = std::min(width, data.size() - offset);
                    const std::string node_id = digest_payload_native(data.data() + offset, len, layer);
                    const std::string node_key = "n:" + node_id;
                    if (candidates.find(node_key) == candidates.end()) {
                        candidates.emplace(node_key, std::make_pair(layer, data.substr(offset, len)));
                    }
                    occurrences.emplace_back(
                        "o:" + memory_id + ":" + std::to_string(layer) + ":" + std::to_string(local_time),
                        node_id
                    );
                }
            }

            std::vector<std::pair<std::string, std::string>> batch;
            batch.reserve(1 + candidates.size() + occurrences.size() + 3 + per_layer.size());
            batch.emplace_back(memory_key, data);

            std::uint64_t new_nodes = 0;
            for (auto& [key, info] : candidates) {
                if (db_->contains(key)) continue;
                const int layer = info.first;
                std::string value;
                value.reserve(2 + info.second.size());
                value.push_back(static_cast<char>((layer >> 8) & 0xff));
                value.push_back(static_cast<char>(layer & 0xff));
                value += info.second;
                batch.emplace_back(key, std::move(value));
                ++new_nodes;
                ++per_layer[static_cast<std::size_t>(layer)];
            }

            for (auto& row : occurrences) batch.emplace_back(std::move(row));
            ++memories;
            nodes += new_nodes;
            occurrences_count += static_cast<std::uint64_t>(occurrences.size());
            batch.emplace_back("meta:memories", encode_u64(memories));
            batch.emplace_back("meta:unique_nodes", encode_u64(nodes));
            batch.emplace_back("meta:occurrences", encode_u64(occurrences_count));
            for (int layer = 0; layer <= max_layer; ++layer) {
                batch.emplace_back("meta:nodes_layer:" + std::to_string(layer), encode_u64(per_layer[static_cast<std::size_t>(layer)]));
            }

            for (auto& [key, value] : batch) db_->put(std::move(key), std::move(value));
            if (durable) db_->sync();
        }

        py::dict layer_counts;
        for (int layer = 0; layer <= max_layer; ++layer) {
            layer_counts[py::int_(layer)] = py::int_(per_layer[static_cast<std::size_t>(layer)]);
        }
        py::dict result;
        result["memories"] = py::int_(memories);
        result["unique_nodes"] = py::int_(nodes);
        result["occurrences"] = py::int_(occurrences_count);
        result["nodes_per_layer"] = std::move(layer_counts);
        return result;
    }

    std::uint64_t erase_many(const std::vector<std::string>& keys, bool durable) {
        std::uint64_t last = 0;
        py::gil_scoped_release release;
        for (const auto& key : keys) {
            auto ticket = db_->erase(key);
            last = ticket.sequence;
        }
        if (durable) db_->sync();
        return last;
    }

    void sync() { py::gil_scoped_release release; db_->sync(); }
    void checkpoint() { py::gil_scoped_release release; db_->checkpoint(); }
    void close() {
        if (!db_) return;
        py::gil_scoped_release release;
        db_->close();
        db_.reset();
    }

    std::uint64_t last_sequence() const { return db_->last_sequence(); }
    std::uint64_t durable_sequence() const { return db_->durable_sequence(); }
    std::size_t size() const { return db_->size(); }

private:
    std::unique_ptr<bdr::Database> db_;
};

}  // namespace

PYBIND11_MODULE(_bdr_native, m) {
    m.doc() = "Direct pybind11 binding to frozen Resolutive-DB v1.0.0";

    m.def("digest_payload_native", [](py::bytes payload, int layer) {
        const std::string data = as_bytes(payload);
        return digest_payload_native(data.data(), data.size(), layer);
    });

    py::class_<NativeDatabase>(m, "Database")
        .def(py::init<const std::string&, std::size_t, std::size_t>(),
             py::arg("path"), py::arg("reserve_bytes") = 64ull * 1024ull * 1024ull,
             py::arg("wal_batch") = 512)
        .def("get", &NativeDatabase::get)
        .def("contains", &NativeDatabase::contains)
        .def("contains_many", &NativeDatabase::contains_many)
        .def("put_many", &NativeDatabase::put_many, py::arg("rows"), py::arg("durable") = true)
        .def("add_resolutive_memory", &NativeDatabase::add_resolutive_memory,
             py::arg("memory_id"), py::arg("payload"), py::arg("max_layer"), py::arg("durable") = true)
        .def("erase_many", &NativeDatabase::erase_many, py::arg("keys"), py::arg("durable") = true)
        .def("sync", &NativeDatabase::sync)
        .def("checkpoint", &NativeDatabase::checkpoint)
        .def("close", &NativeDatabase::close)
        .def_property_readonly("last_sequence", &NativeDatabase::last_sequence)
        .def_property_readonly("durable_sequence", &NativeDatabase::durable_sequence)
        .def_property_readonly("size", &NativeDatabase::size);
}
