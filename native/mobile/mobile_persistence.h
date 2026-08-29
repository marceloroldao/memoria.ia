#ifndef MEMORIA_MOBILE_PERSISTENCE_H
#define MEMORIA_MOBILE_PERSISTENCE_H

#include "relation_extractor.h"

#include <stddef.h>

#define MEMORIA_MOBILE_STATE_SCHEMA 1u
#define MEMORIA_PERSIST_MAX_RELATIONS 4u
#define MEMORIA_PERSIST_MEMORY_ID_CAP 257u

typedef struct memoria_persistence memoria_persistence;

typedef struct memoria_persist_turn {
    char *memory_id;
    char *text;
    char *role;
    char *source_type;
    char *ultimate_source_memory_id;
    double authority;
    long order;
    int superseded;
    memoria_relation relations[MEMORIA_PERSIST_MAX_RELATIONS];
    char relation_memory_ids[MEMORIA_PERSIST_MAX_RELATIONS][MEMORIA_PERSIST_MEMORY_ID_CAP];
    size_t relation_count;
} memoria_persist_turn;

typedef struct memoria_persist_episode {
    char *episode_id;
    char *session_id;
    char *role;
    char *text;
    char *timestamp;
    char *event_type;
    char *topics_csv;
    char *source_type;
    char *ultimate_source_memory_id;
    double authority;
    long order;
    int superseded;
} memoria_persist_episode;

int memoria_persistence_open(const char *data_dir, const char *organization_id, memoria_persistence **out);
int memoria_persistence_meta(memoria_persistence *p, size_t *turn_count, size_t *episode_count, unsigned long *sequence);
int memoria_persistence_save_turn(memoria_persistence *p, size_t slot, unsigned long sequence, const memoria_persist_turn *turn);
int memoria_persistence_save_turn_with_supersessions(
    memoria_persistence *p, size_t slot, unsigned long sequence,
    const memoria_persist_turn *turn, const size_t *superseded_slots, size_t superseded_count
);
int memoria_persistence_load_turn(memoria_persistence *p, size_t slot, memoria_persist_turn *out);
int memoria_persistence_save_episode(memoria_persistence *p, size_t slot, unsigned long sequence, const memoria_persist_episode *episode);
int memoria_persistence_load_episode(memoria_persistence *p, size_t slot, memoria_persist_episode *out);
int memoria_persistence_sync(memoria_persistence *p);
void memoria_persistence_free_turn(memoria_persist_turn *turn);
void memoria_persistence_free_episode(memoria_persist_episode *episode);
void memoria_persistence_close(memoria_persistence *p);

#endif
