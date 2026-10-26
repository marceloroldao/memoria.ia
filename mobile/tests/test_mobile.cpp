#include "memoria/mobile.h"

#include <cassert>
#include <filesystem>
#include <string>
#include <vector>

static memoria_mobile_resolution resolve(memoria_mobile_runtime* runtime, const std::string& query, std::string& context) {
    memoria_mobile_resolution result{};
    size_t needed = 0;
    auto status = memoria_mobile_resolve(runtime, query.data(), query.size(), &result, nullptr, 0, &needed);
    if (result.status == MEMORIA_MOBILE_HIT) {
        assert(status == MEMORIA_MOBILE_BUFFER_TOO_SMALL);
        std::vector<char> buffer(needed);
        size_t actual = 0;
        status = memoria_mobile_resolve(runtime, query.data(), query.size(), &result, buffer.data(), buffer.size(), &actual);
        assert(status == MEMORIA_MOBILE_OK);
        context.assign(buffer.data(), actual);
    } else {
        assert(status == MEMORIA_MOBILE_OK);
        context.clear();
    }
    return result;
}

int main() {
    namespace fs = std::filesystem;
    const auto root = fs::temp_directory_path() / "memoria_mobile_contract";
    fs::remove_all(root);
    fs::create_directories(root);

    assert(memoria_mobile_abi_version() == 1u);

    memoria_mobile_runtime* runtime = nullptr;
    assert(memoria_mobile_open(root.string().c_str(), &runtime) == MEMORIA_MOBILE_OK);
    assert(runtime != nullptr);
    assert(memoria_mobile_count(runtime) == 0u);

    std::string context;
    auto first = resolve(runtime, "Qual e a tensao da fonte principal?", context);
    assert(first.status == MEMORIA_MOBILE_MISS);

    const std::string user = "Minha fonte principal e 24 V.";
    const std::string assistant = "Entendido. A fonte principal usa 24 V.";
    uint64_t memory_id = 0;
    assert(memoria_mobile_learn_turn(runtime, user.data(), user.size(), assistant.data(), assistant.size(), &memory_id) == MEMORIA_MOBILE_OK);
    assert(memory_id == 1u);
    assert(memoria_mobile_count(runtime) == 1u);

    auto same_session = resolve(runtime, "Qual e a tensao da fonte principal?", context);
    assert(same_session.status == MEMORIA_MOBILE_HIT);
    assert(same_session.memory_id == memory_id);
    assert(context.find("24 V") != std::string::npos);

    auto unrelated = resolve(runtime, "Qual a capital da Franca?", context);
    assert(unrelated.status == MEMORIA_MOBILE_UNRESOLVED);

    assert(memoria_mobile_flush(runtime) == MEMORIA_MOBILE_OK);
    memoria_mobile_close(runtime);

    runtime = nullptr;
    assert(memoria_mobile_open(root.string().c_str(), &runtime) == MEMORIA_MOBILE_OK);
    assert(memoria_mobile_count(runtime) == 1u);

    auto restarted = resolve(runtime, "Me lembre a tensao da fonte principal", context);
    assert(restarted.status == MEMORIA_MOBILE_HIT);
    assert(restarted.memory_id == memory_id);
    assert(context.find("24 V") != std::string::npos);

    memoria_mobile_close(runtime);
    fs::remove_all(root);
    return 0;
}
