#include "memoria/mobile.h"
#include "bdr/c_api.h"

#include <algorithm>
#include <cmath>
#include <cctype>
#include <cstdint>
#include <cstring>
#include <exception>
#include <sstream>
#include <string>
#include <unordered_map>
#include <unordered_set>
#include <utility>
#include <vector>

namespace {
using Profile = std::unordered_map<std::string, int>;

struct Turn {
    std::uint64_t id = 0;
    std::string user;
    std::string assistant;
    Profile profile;
};

thread_local std::string g_last_error;

const std::unordered_set<std::string> kStopwords = {
    "a", "o", "as", "os", "um", "uma", "de", "da", "do", "das", "dos",
    "e", "em", "no", "na", "nos", "nas", "por", "para", "com", "sem",
    "que", "foi", "esta", "este", "esse", "essa", "ao", "aos", "se",
    "mas", "porque", "como", "ainda", "depois", "antes", "muito", "mais",
    "menos", "ja", "nao"
};

void set_error(const std::string& message) { g_last_error = message; }

bool is_token_byte(unsigned char c) {
    return std::isalnum(c) || c == '_' || c >= 0x80;
}

std::vector<std::string> tokenize(const std::string& text) {
    std::vector<std::string> tokens;
    std::string current;
    for (unsigned char c : text) {
        if (is_token_byte(c)) {
            if (c < 0x80) current.push_back(static_cast<char>(std::tolower(c)));
            else current.push_back(static_cast<char>(c));
        } else if (!current.empty()) {
            tokens.push_back(std::move(current));
            current.clear();
        }
    }
    if (!current.empty()) tokens.push_back(std::move(current));
    return tokens;
}

Profile content_profile(const std::string& text) {
    Profile profile;
    for (const auto& token : tokenize(text)) {
        if (kStopwords.find(token) == kStopwords.end()) ++profile[token];
    }
    return profile;
}

std::string turn_key(std::uint64_t id) {
    return "turn:" + std::to_string(id);
}

std::string serialize_turn(const Turn& turn) {
    std::ostringstream out;
    out << turn.user.size() << '\n' << turn.assistant.size() << '\n';
    std::string result = out.str();
    result.append(turn.user);
    result.append(turn.assistant);
    return result;
}

bool parse_size_line(const std::string& data, std::size_t& pos, std::size_t& value) {
    const auto end = data.find('\n', pos);
    if (end == std::string::npos) return false;
    try {
        value = static_cast<std::size_t>(std::stoull(data.substr(pos, end - pos)));
    } catch (...) {
        return false;
    }
    pos = end + 1;
    return true;
}

bool deserialize_turn(std::uint64_t id, const std::string& data, Turn& out) {
    std::size_t pos = 0, user_size = 0, assistant_size = 0;
    if (!parse_size_line(data, pos, user_size) || !parse_size_line(data, pos, assistant_size)) return false;
    if (user_size > data.size() - pos) return false;
    if (assistant_size > data.size() - pos - user_size) return false;
    out.id = id;
    out.user = data.substr(pos, user_size);
    pos += user_size;
    out.assistant = data.substr(pos, assistant_size);
    out.profile = content_profile(out.user + " " + out.assistant);
    return true;
}

bdr_c_status bdr_get_string(bdr_c_database* db, const std::string& key, std::string& out) {
    std::size_t needed = 0;
    auto status = bdr_c_get(db, key.data(), key.size(), nullptr, 0, &needed);
    if (status == BDR_C_NOT_FOUND) return status;
    if (status != BDR_C_BUFFER_TOO_SMALL && !(status == BDR_C_OK && needed == 0)) return status;
    out.assign(needed, '\0');
    std::size_t actual = 0;
    status = bdr_c_get(db, key.data(), key.size(), out.empty() ? nullptr : out.data(), out.size(), &actual);
    if (status == BDR_C_OK) out.resize(actual);
    return status;
}

std::vector<std::uint64_t> parse_catalog(const std::string& catalog) {
    std::vector<std::uint64_t> ids;
    std::istringstream in(catalog);
    std::string line;
    while (std::getline(in, line)) {
        if (line.empty()) continue;
        try { ids.push_back(std::stoull(line)); } catch (...) {}
    }
    return ids;
}

std::string append_catalog(const std::vector<Turn>& turns, std::uint64_t new_id) {
    std::string result;
    for (const auto& turn : turns) result += std::to_string(turn.id) + "\n";
    result += std::to_string(new_id) + "\n";
    return result;
}

} // namespace

struct memoria_mobile_runtime {
    bdr_c_database* db = nullptr;
    std::vector<Turn> turns;
    std::unordered_map<std::string, int> df;
    double threshold = 0.14;
    double min_margin = 0.02;
};

namespace {
void rebuild_df(memoria_mobile_runtime* runtime) {
    runtime->df.clear();
    for (const auto& turn : runtime->turns) {
        for (const auto& item : turn.profile) ++runtime->df[item.first];
    }
}

double weight(const memoria_mobile_runtime* runtime, const std::string& token) {
    const double n = static_cast<double>(std::max<std::size_t>(1, runtime->turns.size()));
    const auto it = runtime->df.find(token);
    const double df = it == runtime->df.end() ? 0.0 : static_cast<double>(it->second);
    return std::log((n + 1.0) / (df + 1.0)) + 1.0;
}

double score(const memoria_mobile_runtime* runtime, const Profile& query, const Profile& concept) {
    if (query.empty() || concept.empty()) return 0.0;
    double dot = 0.0, nq = 0.0, nc = 0.0;
    for (const auto& [token, count] : query) {
        const double w = weight(runtime, token);
        const double qv = static_cast<double>(count) * w;
        nq += qv * qv;
        const auto it = concept.find(token);
        if (it != concept.end()) dot += qv * (static_cast<double>(it->second) * w);
    }
    for (const auto& [token, count] : concept) {
        const double v = static_cast<double>(count) * weight(runtime, token);
        nc += v * v;
    }
    if (nq == 0.0 || nc == 0.0) return 0.0;
    return dot / (std::sqrt(nq) * std::sqrt(nc));
}

memoria_mobile_status storage_error(const char* operation) {
    set_error(std::string(operation) + ": " + bdr_c_last_error());
    return MEMORIA_MOBILE_STORAGE_ERROR;
}
}

extern "C" {

uint32_t memoria_mobile_abi_version(void) { return MEMORIA_MOBILE_ABI_VERSION; }
const char* memoria_mobile_last_error(void) { return g_last_error.c_str(); }

memoria_mobile_status memoria_mobile_open(const char* storage_directory, memoria_mobile_runtime** out_runtime) {
    if (!storage_directory || !out_runtime) {
        set_error("storage_directory and out_runtime are required");
        return MEMORIA_MOBILE_INVALID_ARGUMENT;
    }
    *out_runtime = nullptr;
    try {
        auto* runtime = new memoria_mobile_runtime();
        if (bdr_c_open(storage_directory, nullptr, &runtime->db) != BDR_C_OK) {
            delete runtime;
            return storage_error("bdr open failed");
        }
        std::string catalog;
        const auto catalog_status = bdr_get_string(runtime->db, "meta:turn_ids", catalog);
        if (catalog_status != BDR_C_OK && catalog_status != BDR_C_NOT_FOUND) {
            bdr_c_close(runtime->db);
            delete runtime;
            return storage_error("catalog read failed");
        }
        for (auto id : parse_catalog(catalog)) {
            std::string raw;
            if (bdr_get_string(runtime->db, turn_key(id), raw) != BDR_C_OK) continue;
            Turn turn;
            if (deserialize_turn(id, raw, turn)) runtime->turns.push_back(std::move(turn));
        }
        rebuild_df(runtime);
        *out_runtime = runtime;
        g_last_error.clear();
        return MEMORIA_MOBILE_OK;
    } catch (const std::exception& e) {
        set_error(e.what());
        return MEMORIA_MOBILE_INTERNAL_ERROR;
    } catch (...) {
        set_error("unknown error while opening Memoria mobile runtime");
        return MEMORIA_MOBILE_INTERNAL_ERROR;
    }
}

void memoria_mobile_close(memoria_mobile_runtime* runtime) {
    if (!runtime) return;
    if (runtime->db) bdr_c_close(runtime->db);
    delete runtime;
}

memoria_mobile_status memoria_mobile_resolve(
    memoria_mobile_runtime* runtime,
    const char* query,
    size_t query_size,
    memoria_mobile_resolution* out_resolution,
    char* out_context,
    size_t out_capacity,
    size_t* out_context_size) {
    if (!runtime || (!query && query_size > 0) || !out_resolution || !out_context_size) {
        set_error("invalid resolve arguments");
        return MEMORIA_MOBILE_INVALID_ARGUMENT;
    }
    out_resolution->status = MEMORIA_MOBILE_MISS;
    out_resolution->memory_id = 0;
    out_resolution->score = 0.0;
    out_resolution->margin = 0.0;
    *out_context_size = 0;
    if (runtime->turns.empty()) return MEMORIA_MOBILE_OK;

    const Profile q = content_profile(std::string(query ? query : "", query_size));
    if (q.empty()) {
        out_resolution->status = MEMORIA_MOBILE_UNRESOLVED;
        return MEMORIA_MOBILE_OK;
    }

    std::vector<std::pair<std::size_t, double>> ranked;
    ranked.reserve(runtime->turns.size());
    for (std::size_t i = 0; i < runtime->turns.size(); ++i) {
        ranked.emplace_back(i, score(runtime, q, runtime->turns[i].profile));
    }
    std::sort(ranked.begin(), ranked.end(), [&](const auto& a, const auto& b) {
        if (a.second != b.second) return a.second > b.second;
        return runtime->turns[a.first].id < runtime->turns[b.first].id;
    });

    const auto best_index = ranked.front().first;
    const double best = ranked.front().second;
    const double second = ranked.size() > 1 ? ranked[1].second : 0.0;
    const double margin = best - second;
    out_resolution->score = best;
    out_resolution->margin = margin;

    if (best < runtime->threshold || margin < runtime->min_margin) {
        out_resolution->status = MEMORIA_MOBILE_UNRESOLVED;
        return MEMORIA_MOBILE_OK;
    }

    const auto& turn = runtime->turns[best_index];
    out_resolution->status = MEMORIA_MOBILE_HIT;
    out_resolution->memory_id = turn.id;
    const std::string context = "USER:\n" + turn.user + "\nASSISTANT:\n" + turn.assistant;
    *out_context_size = context.size();
    if (context.size() > out_capacity || (!context.empty() && out_context == nullptr)) {
        set_error("context output buffer too small");
        return MEMORIA_MOBILE_BUFFER_TOO_SMALL;
    }
    if (!context.empty()) std::memcpy(out_context, context.data(), context.size());
    g_last_error.clear();
    return MEMORIA_MOBILE_OK;
}

memoria_mobile_status memoria_mobile_learn_turn(
    memoria_mobile_runtime* runtime,
    const char* user_text,
    size_t user_size,
    const char* assistant_text,
    size_t assistant_size,
    uint64_t* out_memory_id) {
    if (!runtime || (!user_text && user_size > 0) || (!assistant_text && assistant_size > 0) || !out_memory_id) {
        set_error("invalid learn_turn arguments");
        return MEMORIA_MOBILE_INVALID_ARGUMENT;
    }
    try {
        Turn turn;
        turn.id = runtime->turns.empty() ? 1 : runtime->turns.back().id + 1;
        turn.user.assign(user_text ? user_text : "", user_size);
        turn.assistant.assign(assistant_text ? assistant_text : "", assistant_size);
        turn.profile = content_profile(turn.user + " " + turn.assistant);

        const std::string key = turn_key(turn.id);
        const std::string raw = serialize_turn(turn);
        const std::string catalog_key = "meta:turn_ids";
        const std::string catalog = append_catalog(runtime->turns, turn.id);
        const bdr_c_pair entries[] = {
            {key.data(), key.size(), raw.data(), raw.size()},
            {catalog_key.data(), catalog_key.size(), catalog.data(), catalog.size()},
        };
        if (bdr_c_put_many(runtime->db, entries, 2, BDR_C_BATCH_SYNC) != BDR_C_OK) {
            return storage_error("atomic turn write failed");
        }
        runtime->turns.push_back(std::move(turn));
        rebuild_df(runtime);
        *out_memory_id = runtime->turns.back().id;
        g_last_error.clear();
        return MEMORIA_MOBILE_OK;
    } catch (const std::exception& e) {
        set_error(e.what());
        return MEMORIA_MOBILE_INTERNAL_ERROR;
    } catch (...) {
        set_error("unknown error while learning turn");
        return MEMORIA_MOBILE_INTERNAL_ERROR;
    }
}

memoria_mobile_status memoria_mobile_flush(memoria_mobile_runtime* runtime) {
    if (!runtime || !runtime->db) {
        set_error("invalid runtime");
        return MEMORIA_MOBILE_INVALID_ARGUMENT;
    }
    if (bdr_c_sync(runtime->db) != BDR_C_OK) return storage_error("bdr sync failed");
    g_last_error.clear();
    return MEMORIA_MOBILE_OK;
}

size_t memoria_mobile_count(const memoria_mobile_runtime* runtime) {
    return runtime ? runtime->turns.size() : 0;
}

} // extern "C"
