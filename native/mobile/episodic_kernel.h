#ifndef MEMORIA_EPISODIC_KERNEL_H
#define MEMORIA_EPISODIC_KERNEL_H

#include <stddef.h>

typedef struct memoria_episode_source {
    const char *episode_id;
    const char *role;
    const char *text;
    long order;
    const char *timestamp;
    const char *event_type;
    const char *topics_csv;
    const char *source_type;
    double source_authority;
    const char *ultimate_source_memory_id;
    int superseded;
} memoria_episode_source;

typedef struct memoria_episode_result {
    int hit; /* 1 HIT, 0 UNRESOLVED */
    const char *episode_id;
    const char *text;
    long order;
    const char *timestamp;
    const char *event_type;
    const char *topics_csv;
    const char *source_type;
    double source_authority;
    const char *ultimate_source_memory_id;
    double confidence;
} memoria_episode_result;

memoria_episode_result memoria_episode_recall_latest(
    const char *query,
    const char *role,
    const char *event_type,
    const char *topics_csv,
    const memoria_episode_source *episodes,
    size_t episode_count
);

#endif
