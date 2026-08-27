#include <bdr/database.hpp>
#include <pybind11/pybind11.h>
#include <pybind11/stl.h>

#include <filesystem>
#include <memory>
#include <string>
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

class NativeDatabase {
public:
    NativeDatabase(const std::string& path, std::size_t reserve_bytes, std::size_t wal_batch) {
        bdr::Options opts;
        opts.reserve_bytes = reserve_bytes;
        opts.wal_batch = wal_batch;
        db_ = bdr::Database::open(std::filesystem::path(path), opts);
    }

    ~NativeDatabase() {
        try {
            if (db_) db_->close();
        } catch (...) {
        }
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

    void sync() {
        py::gil_scoped_release release;
        db_->sync();
    }

    void checkpoint() {
        py::gil_scoped_release release;
        db_->checkpoint();
    }

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

    py::class_<NativeDatabase>(m, "Database")
        .def(py::init<const std::string&, std::size_t, std::size_t>(),
             py::arg("path"), py::arg("reserve_bytes") = 64ull * 1024ull * 1024ull,
             py::arg("wal_batch") = 512)
        .def("get", &NativeDatabase::get)
        .def("contains", &NativeDatabase::contains)
        .def("contains_many", &NativeDatabase::contains_many)
        .def("put_many", &NativeDatabase::put_many, py::arg("rows"), py::arg("durable") = true)
        .def("erase_many", &NativeDatabase::erase_many, py::arg("keys"), py::arg("durable") = true)
        .def("sync", &NativeDatabase::sync)
        .def("checkpoint", &NativeDatabase::checkpoint)
        .def("close", &NativeDatabase::close)
        .def_property_readonly("last_sequence", &NativeDatabase::last_sequence)
        .def_property_readonly("durable_sequence", &NativeDatabase::durable_sequence)
        .def_property_readonly("size", &NativeDatabase::size);
}
