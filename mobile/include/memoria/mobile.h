#pragma once

#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define MEMORIA_MOBILE_ABI_VERSION 1u

typedef struct memoria_mobile_runtime memoria_mobile_runtime;

typedef enum memoria_mobile_status {
    MEMORIA_MOBILE_OK = 0,
    MEMORIA_MOBILE_INVALID_ARGUMENT = 1,
    MEMORIA_MOBILE_BUFFER_TOO_SMALL = 2,
    MEMORIA_MOBILE_STORAGE_ERROR = 3,
    MEMORIA_MOBILE_INTERNAL_ERROR = 4
} memoria_mobile_status;

typedef enum memoria_mobile_resolution_status {
    MEMORIA_MOBILE_MISS = 0,
    MEMORIA_MOBILE_HIT = 1,
    MEMORIA_MOBILE_UNRESOLVED = 2
} memoria_mobile_resolution_status;

typedef struct memoria_mobile_resolution {
    memoria_mobile_resolution_status status;
    uint64_t memory_id;
    double score;
    double margin;
} memoria_mobile_resolution;

uint32_t memoria_mobile_abi_version(void);
const char* memoria_mobile_last_error(void);

memoria_mobile_status memoria_mobile_open(
    const char* storage_directory,
    memoria_mobile_runtime** out_runtime);

void memoria_mobile_close(memoria_mobile_runtime* runtime);

memoria_mobile_status memoria_mobile_resolve(
    memoria_mobile_runtime* runtime,
    const char* query,
    size_t query_size,
    memoria_mobile_resolution* out_resolution,
    char* out_context,
    size_t out_capacity,
    size_t* out_context_size);

memoria_mobile_status memoria_mobile_learn_turn(
    memoria_mobile_runtime* runtime,
    const char* user_text,
    size_t user_size,
    const char* assistant_text,
    size_t assistant_size,
    uint64_t* out_memory_id);

memoria_mobile_status memoria_mobile_flush(memoria_mobile_runtime* runtime);
size_t memoria_mobile_count(const memoria_mobile_runtime* runtime);

#ifdef __cplusplus
}
#endif
