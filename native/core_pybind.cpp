#include <pybind11/pybind11.h>
#include <pybind11/stl.h>

#include <algorithm>
#include <cmath>
#include <cstdint>
#include <string>
#include <unordered_map>
#include <utility>
#include <vector>

namespace py = pybind11;

namespace {

struct Feature {
    int offset;
    std::string token;

    bool operator==(const Feature& other) const noexcept {
        return offset == other.offset && token == other.token;
    }
};

struct FeatureHash {
    std::size_t operator()(const Feature& f) const noexcept {
        std::size_t h1 = std::hash<int>{}(f.offset);
        std::size_t h2 = std::hash<std::string>{}(f.token);
        return h1 ^ (h2 + 0x9e3779b97f4a7c15ULL + (h1 << 6) + (h1 >> 2));
    }
};

using Profile = std::unordered_map<Feature, std::uint64_t, FeatureHash>;
using TokenCounts = std::unordered_map<std::string, std::uint64_t>;

class ContextScorer {
public:
    explicit ContextScorer(int radius = 2) : radius_(radius) {
        if (radius_ < 1) throw py::value_error("radius must be >= 1");
    }

    void observe(const std::vector<std::string>& trajectory) {
        py::gil_scoped_release release;
        for (std::size_t i = 0; i < trajectory.size(); ++i) {
            const auto& node = trajectory[i];
            auto& profile = profiles_[node];
            auto& unordered = unordered_[node];
            ++observations_[node];
            const std::size_t lo = i > static_cast<std::size_t>(radius_) ? i - radius_ : 0;
            const std::size_t hi = std::min(trajectory.size(), i + static_cast<std::size_t>(radius_) + 1);
            for (std::size_t j = lo; j < hi; ++j) {
                if (j == i) continue;
                Feature f{static_cast<int>(j) - static_cast<int>(i), trajectory[j]};
                auto it = profile.find(f);
                if (it == profile.end()) {
                    feature_df_[f] += 1;
                    profile.emplace(std::move(f), 1);
                } else {
                    ++it->second;
                }
                ++unordered[trajectory[j]];
            }
        }
    }

    double similarity(const std::string& a, const std::string& b) const {
        py::gil_scoped_release release;
        return similarity_nogil(a, b);
    }

    double unordered_similarity(const std::string& a, const std::string& b) const {
        py::gil_scoped_release release;
        return unordered_similarity_nogil(a, b);
    }

    std::vector<std::pair<std::string, double>> nearest(const std::string& node, std::size_t top_k = 5) const {
        std::vector<std::pair<std::string, double>> scores;
        {
            py::gil_scoped_release release;
            if (profiles_.find(node) == profiles_.end()) return scores;
            scores.reserve(profiles_.size() > 0 ? profiles_.size() - 1 : 0);
            for (const auto& [other, _] : profiles_) {
                if (other == node) continue;
                scores.emplace_back(other, similarity_nogil(node, other));
            }
            std::sort(scores.begin(), scores.end(), [](const auto& x, const auto& y) {
                if (x.second != y.second) return x.second > y.second;
                return x.first < y.first;
            });
            if (scores.size() > top_k) scores.resize(top_k);
        }
        return scores;
    }

    std::size_t nodes() const noexcept { return profiles_.size(); }

private:
    double weight(const Feature& f) const {
        const double total_nodes = static_cast<double>(std::max<std::size_t>(1, profiles_.size()));
        auto it = feature_df_.find(f);
        const double df = it == feature_df_.end() ? 0.0 : static_cast<double>(it->second);
        return std::log((total_nodes + 1.0) / (df + 1.0)) + 1.0;
    }

    double similarity_nogil(const std::string& a, const std::string& b) const {
        auto ia = profiles_.find(a);
        auto ib = profiles_.find(b);
        if (ia == profiles_.end() || ib == profiles_.end() || ia->second.empty() || ib->second.empty()) return 0.0;
        const Profile* small = &ia->second;
        const Profile* large = &ib->second;
        if (small->size() > large->size()) std::swap(small, large);

        double dot = 0.0;
        for (const auto& [f, av] : *small) {
            auto it = large->find(f);
            if (it == large->end()) continue;
            const double w = weight(f);
            dot += static_cast<double>(av) * static_cast<double>(it->second) * w * w;
        }
        double na2 = 0.0, nb2 = 0.0;
        for (const auto& [f, v] : ia->second) {
            const double x = static_cast<double>(v) * weight(f);
            na2 += x * x;
        }
        for (const auto& [f, v] : ib->second) {
            const double x = static_cast<double>(v) * weight(f);
            nb2 += x * x;
        }
        if (na2 == 0.0 || nb2 == 0.0) return 0.0;
        return dot / (std::sqrt(na2) * std::sqrt(nb2));
    }

    double unordered_similarity_nogil(const std::string& a, const std::string& b) const {
        auto ia = unordered_.find(a);
        auto ib = unordered_.find(b);
        if (ia == unordered_.end() || ib == unordered_.end() || ia->second.empty() || ib->second.empty()) return 0.0;
        const TokenCounts* small = &ia->second;
        const TokenCounts* large = &ib->second;
        if (small->size() > large->size()) std::swap(small, large);
        double dot = 0.0;
        for (const auto& [token, av] : *small) {
            auto it = large->find(token);
            if (it != large->end()) dot += static_cast<double>(av) * static_cast<double>(it->second);
        }
        double na2 = 0.0, nb2 = 0.0;
        for (const auto& [_, v] : ia->second) na2 += static_cast<double>(v) * static_cast<double>(v);
        for (const auto& [_, v] : ib->second) nb2 += static_cast<double>(v) * static_cast<double>(v);
        if (na2 == 0.0 || nb2 == 0.0) return 0.0;
        return dot / (std::sqrt(na2) * std::sqrt(nb2));
    }

    int radius_;
    std::unordered_map<std::string, Profile> profiles_;
    std::unordered_map<std::string, TokenCounts> unordered_;
    std::unordered_map<Feature, std::uint64_t, FeatureHash> feature_df_;
    std::unordered_map<std::string, std::uint64_t> observations_;
};

}  // namespace

PYBIND11_MODULE(_core_native, m) {
    m.doc() = "Native CPU hot paths for Memoria.ia resolutive core";
    py::class_<ContextScorer>(m, "ContextScorer")
        .def(py::init<int>(), py::arg("radius") = 2)
        .def("observe", &ContextScorer::observe)
        .def("similarity", &ContextScorer::similarity)
        .def("unordered_similarity", &ContextScorer::unordered_similarity)
        .def("nearest", &ContextScorer::nearest, py::arg("node"), py::arg("top_k") = 5)
        .def_property_readonly("nodes", &ContextScorer::nodes);
}
