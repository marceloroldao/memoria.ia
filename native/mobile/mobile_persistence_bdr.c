#include "mobile_persistence.h"
#include "bdr/atomic_c_api.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define KEY_CAP 384
#define VAL_CAP 128
#define MAX_OPS 64

struct memoria_persistence {
    bdr_atomic_c_handle *db;
    char *org;
};

static char *sdup(const char *s) {
    size_t n;
    char *p;
    if (!s) s = "";
    n = strlen(s) + 1;
    p = (char *)malloc(n);
    if (p) memcpy(p, s, n);
    return p;
}

static int key_of(memoria_persistence *p, char *dst, size_t cap,
                  const char *kind, size_t slot, const char *field) {
    int n;
    if (!p || !dst || !kind || !field) return 0;
    n = slot
        ? snprintf(dst, cap, "memoria-mobile/v1/%s/%s/%06zu/%s", p->org, kind, slot, field)
        : snprintf(dst, cap, "memoria-mobile/v1/%s/%s/%s", p->org, kind, field);
    return n > 0 && (size_t)n < cap;
}

static int fetch(memoria_persistence *p, const char *kind, size_t slot,
                 const char *field, char **out) {
    char key[KEY_CAP];
    bdr_atomic_c_buffer b = {0};
    bdr_atomic_c_status st;
    char *v;
    if (!out || !key_of(p, key, sizeof(key), kind, slot, field)) return 0;
    *out = NULL;
    st = bdr_atomic_c_get(p->db, key, strlen(key), &b);
    if (st == BDR_ATOMIC_C_NOT_FOUND) return 1;
    if (st != BDR_ATOMIC_C_OK) return 0;
    v = (char *)malloc(b.size + 1);
    if (!v) { bdr_atomic_c_free_buffer(b); return 0; }
    if (b.size) memcpy(v, b.data, b.size);
    v[b.size] = 0;
    bdr_atomic_c_free_buffer(b);
    *out = v;
    return 1;
}

static int parse_ul(const char *s, unsigned long *out) {
    char *end = NULL;
    unsigned long v;
    if (!s || !out) return 0;
    v = strtoul(s, &end, 10);
    if (end == s || *end) return 0;
    *out = v;
    return 1;
}

static int parse_l(const char *s, long *out) {
    char *end = NULL;
    long v;
    if (!s || !out) return 0;
    v = strtol(s, &end, 10);
    if (end == s || *end) return 0;
    *out = v;
    return 1;
}

static int parse_d(const char *s, double *out) {
    char *end = NULL;
    double v;
    if (!s || !out) return 0;
    v = strtod(s, &end);
    if (end == s || *end) return 0;
    *out = v;
    return 1;
}

static int get_ul(memoria_persistence *p, const char *field, unsigned long *out) {
    char *v = NULL;
    int ok;
    if (!fetch(p, "meta", 0, field, &v)) return 0;
    if (!v) { *out = 0; return 1; }
    ok = parse_ul(v, out);
    free(v);
    return ok;
}

static int add_put(memoria_persistence *p, bdr_atomic_c_operation *ops,
                   char keys[][KEY_CAP], size_t *n,
                   const char *kind, size_t slot, const char *field, const char *value) {
    size_t i = *n;
    if (i >= MAX_OPS || !key_of(p, keys[i], KEY_CAP, kind, slot, field)) return 0;
    ops[i].type = BDR_ATOMIC_C_PUT;
    ops[i].key = keys[i];
    ops[i].key_size = strlen(keys[i]);
    ops[i].value = value ? value : "";
    ops[i].value_size = strlen(value ? value : "");
    *n = i + 1;
    return 1;
}

static int add_meta(memoria_persistence *p, bdr_atomic_c_operation *ops,
                    char keys[][KEY_CAP], size_t *n, const char *field, const char *value) {
    return add_put(p, ops, keys, n, "meta", 0, field, value);
}

int memoria_persistence_open(const char *data_dir, const char *organization_id, memoria_persistence **out) {
    memoria_persistence *p;
    if (!data_dir || !*data_dir || !organization_id || !*organization_id || !out) return 0;
    *out = NULL;
    p = (memoria_persistence *)calloc(1, sizeof(*p));
    if (!p) return 0;
    p->org = sdup(organization_id);
    if (!p->org || bdr_atomic_c_open(data_dir, &p->db) != BDR_ATOMIC_C_OK ||
        bdr_atomic_c_abi_version() != BDR_ATOMIC_C_ABI_VERSION ||
        bdr_atomic_c_integrity_check(p->db) != BDR_ATOMIC_C_OK) {
        memoria_persistence_close(p);
        return 0;
    }
    *out = p;
    return 1;
}

int memoria_persistence_meta(memoria_persistence *p, size_t *turn_count,
                             size_t *episode_count, unsigned long *sequence) {
    char *schema = NULL;
    unsigned long version = 0, turns = 0, episodes = 0, seq = 0;
    if (!p || !turn_count || !episode_count || !sequence ||
        !fetch(p, "meta", 0, "schema", &schema)) return 0;
    if (schema) {
        if (!parse_ul(schema, &version) || version != MEMORIA_MOBILE_STATE_SCHEMA) {
            free(schema); return 0;
        }
        free(schema);
    }
    if (!get_ul(p, "turn_count", &turns) || !get_ul(p, "episode_count", &episodes) ||
        !get_ul(p, "sequence", &seq)) return 0;
    *turn_count = (size_t)turns;
    *episode_count = (size_t)episodes;
    *sequence = seq;
    return 1;
}

static int save_turn_impl(memoria_persistence *p, size_t slot,
                          unsigned long sequence, const memoria_persist_turn *t,
                          const size_t *superseded_slots, size_t superseded_count) {
    bdr_atomic_c_operation ops[MAX_OPS];
    char keys[MAX_OPS][KEY_CAP];
    char vals[16][VAL_CAP];
    bdr_atomic_c_batch_result result = {0};
    size_t n = 0, i;
    if (!p || !slot || !t || !t->memory_id || !t->text || !t->role ||
        !t->source_type || !t->ultimate_source_memory_id ||
        t->relation_count > MEMORIA_PERSIST_MAX_RELATIONS ||
        (superseded_count && !superseded_slots)) return 0;
    snprintf(vals[0], VAL_CAP, "%u", MEMORIA_MOBILE_STATE_SCHEMA);
    snprintf(vals[1], VAL_CAP, "%zu", slot);
    snprintf(vals[2], VAL_CAP, "%lu", sequence);
    snprintf(vals[3], VAL_CAP, "%.17g", t->authority);
    snprintf(vals[4], VAL_CAP, "%ld", t->order);
    snprintf(vals[5], VAL_CAP, "%zu", t->relation_count);
    snprintf(vals[6], VAL_CAP, "%d", t->superseded ? 1 : 0);
    if (!add_meta(p,ops,keys,&n,"schema",vals[0]) ||
        !add_meta(p,ops,keys,&n,"turn_count",vals[1]) ||
        !add_meta(p,ops,keys,&n,"sequence",vals[2]) ||
        !add_put(p,ops,keys,&n,"turn",slot,"memory_id",t->memory_id) ||
        !add_put(p,ops,keys,&n,"turn",slot,"text",t->text) ||
        !add_put(p,ops,keys,&n,"turn",slot,"role",t->role) ||
        !add_put(p,ops,keys,&n,"turn",slot,"source_type",t->source_type) ||
        !add_put(p,ops,keys,&n,"turn",slot,"ultimate_source_memory_id",t->ultimate_source_memory_id) ||
        !add_put(p,ops,keys,&n,"turn",slot,"authority",vals[3]) ||
        !add_put(p,ops,keys,&n,"turn",slot,"order",vals[4]) ||
        !add_put(p,ops,keys,&n,"turn",slot,"relation_count",vals[5]) ||
        !add_put(p,ops,keys,&n,"turn",slot,"superseded",vals[6])) return 0;
    for (i = 0; i < t->relation_count; ++i) {
        char field[64];
        snprintf(field,sizeof(field),"relation/%zu/subject",i);
        if (!add_put(p,ops,keys,&n,"turn",slot,field,t->relations[i].subject)) return 0;
        snprintf(field,sizeof(field),"relation/%zu/predicate",i);
        if (!add_put(p,ops,keys,&n,"turn",slot,field,t->relations[i].predicate)) return 0;
        snprintf(field,sizeof(field),"relation/%zu/object",i);
        if (!add_put(p,ops,keys,&n,"turn",slot,field,t->relations[i].object)) return 0;
        snprintf(vals[7+i],VAL_CAP,"%.17g",t->relations[i].confidence);
        snprintf(field,sizeof(field),"relation/%zu/confidence",i);
        if (!add_put(p,ops,keys,&n,"turn",slot,field,vals[7+i])) return 0;
    }
    for (i = 0; i < superseded_count; ++i) {
        if (!superseded_slots[i] || superseded_slots[i] >= slot) return 0;
        if (!add_put(p,ops,keys,&n,"turn",superseded_slots[i],"superseded","1")) return 0;
    }
    return bdr_atomic_c_write_batch(p->db,ops,n,&result) == BDR_ATOMIC_C_OK &&
           result.durable == 1 && result.operations == n;
}

int memoria_persistence_save_turn(memoria_persistence *p, size_t slot,
                                  unsigned long sequence, const memoria_persist_turn *t) {
    return save_turn_impl(p, slot, sequence, t, NULL, 0);
}

int memoria_persistence_save_turn_with_supersessions(
    memoria_persistence *p, size_t slot, unsigned long sequence,
    const memoria_persist_turn *t, const size_t *superseded_slots, size_t superseded_count
) {
    return save_turn_impl(p, slot, sequence, t, superseded_slots, superseded_count);
}

int memoria_persistence_load_turn(memoria_persistence *p, size_t slot, memoria_persist_turn *t) {
    char *v = NULL;
    unsigned long rc = 0;
    size_t i;
    if (!p || !slot || !t) return 0;
    memset(t,0,sizeof(*t));
    if (!fetch(p,"turn",slot,"memory_id",&t->memory_id) || !t->memory_id ||
        !fetch(p,"turn",slot,"text",&t->text) || !t->text ||
        !fetch(p,"turn",slot,"role",&t->role) || !t->role ||
        !fetch(p,"turn",slot,"source_type",&t->source_type) || !t->source_type ||
        !fetch(p,"turn",slot,"ultimate_source_memory_id",&t->ultimate_source_memory_id) || !t->ultimate_source_memory_id ||
        !fetch(p,"turn",slot,"authority",&v) || !v || !parse_d(v,&t->authority)) goto fail;
    free(v); v=NULL;
    if (!fetch(p,"turn",slot,"order",&v) || !v || !parse_l(v,&t->order)) goto fail;
    free(v); v=NULL;
    if (!fetch(p,"turn",slot,"superseded",&v)) goto fail;
    if (v) {
        long sup = 0;
        if (!parse_l(v,&sup)) goto fail;
        t->superseded = sup != 0;
        free(v); v=NULL;
    } else {
        t->superseded = 0;
    }
    if (!fetch(p,"turn",slot,"relation_count",&v) || !v || !parse_ul(v,&rc) || rc > MEMORIA_PERSIST_MAX_RELATIONS) goto fail;
    free(v); v=NULL;
    t->relation_count=(size_t)rc;
    for (i=0;i<t->relation_count;++i) {
        char field[64];
        snprintf(field,sizeof(field),"relation/%zu/subject",i);
        if(!fetch(p,"turn",slot,field,&v)||!v) goto fail;
        snprintf(t->relations[i].subject,sizeof(t->relations[i].subject),"%s",v); free(v); v=NULL;
        snprintf(field,sizeof(field),"relation/%zu/predicate",i);
        if(!fetch(p,"turn",slot,field,&v)||!v) goto fail;
        snprintf(t->relations[i].predicate,sizeof(t->relations[i].predicate),"%s",v); free(v); v=NULL;
        snprintf(field,sizeof(field),"relation/%zu/object",i);
        if(!fetch(p,"turn",slot,field,&v)||!v) goto fail;
        snprintf(t->relations[i].object,sizeof(t->relations[i].object),"%s",v); free(v); v=NULL;
        snprintf(field,sizeof(field),"relation/%zu/confidence",i);
        if(!fetch(p,"turn",slot,field,&v)||!v||!parse_d(v,&t->relations[i].confidence)) goto fail;
        free(v); v=NULL;
    }
    return 1;
fail:
    free(v); memoria_persistence_free_turn(t); return 0;
}

int memoria_persistence_save_episode(memoria_persistence *p, size_t slot,
                                     unsigned long sequence, const memoria_persist_episode *e) {
    bdr_atomic_c_operation ops[MAX_OPS];
    char keys[MAX_OPS][KEY_CAP];
    char vals[8][VAL_CAP];
    bdr_atomic_c_batch_result result = {0};
    size_t n = 0;
    if (!p || !slot || !e || !e->episode_id || !e->role || !e->text || !e->timestamp ||
        !e->event_type || !e->topics_csv || !e->source_type || !e->ultimate_source_memory_id) return 0;
    snprintf(vals[0],VAL_CAP,"%u",MEMORIA_MOBILE_STATE_SCHEMA);
    snprintf(vals[1],VAL_CAP,"%zu",slot);
    snprintf(vals[2],VAL_CAP,"%lu",sequence);
    snprintf(vals[3],VAL_CAP,"%.17g",e->authority);
    snprintf(vals[4],VAL_CAP,"%ld",e->order);
    snprintf(vals[5],VAL_CAP,"%d",e->superseded);
    if (!add_meta(p,ops,keys,&n,"schema",vals[0]) ||
        !add_meta(p,ops,keys,&n,"episode_count",vals[1]) ||
        !add_meta(p,ops,keys,&n,"sequence",vals[2]) ||
        !add_put(p,ops,keys,&n,"episode",slot,"episode_id",e->episode_id) ||
        !add_put(p,ops,keys,&n,"episode",slot,"role",e->role) ||
        !add_put(p,ops,keys,&n,"episode",slot,"text",e->text) ||
        !add_put(p,ops,keys,&n,"episode",slot,"timestamp",e->timestamp) ||
        !add_put(p,ops,keys,&n,"episode",slot,"event_type",e->event_type) ||
        !add_put(p,ops,keys,&n,"episode",slot,"topics_csv",e->topics_csv) ||
        !add_put(p,ops,keys,&n,"episode",slot,"source_type",e->source_type) ||
        !add_put(p,ops,keys,&n,"episode",slot,"ultimate_source_memory_id",e->ultimate_source_memory_id) ||
        !add_put(p,ops,keys,&n,"episode",slot,"authority",vals[3]) ||
        !add_put(p,ops,keys,&n,"episode",slot,"order",vals[4]) ||
        !add_put(p,ops,keys,&n,"episode",slot,"superseded",vals[5])) return 0;
    return bdr_atomic_c_write_batch(p->db,ops,n,&result) == BDR_ATOMIC_C_OK &&
           result.durable == 1 && result.operations == n;
}

int memoria_persistence_load_episode(memoria_persistence *p, size_t slot, memoria_persist_episode *e) {
    char *v = NULL;
    long sup = 0;
    if (!p || !slot || !e) return 0;
    memset(e,0,sizeof(*e));
    if (!fetch(p,"episode",slot,"episode_id",&e->episode_id) || !e->episode_id ||
        !fetch(p,"episode",slot,"role",&e->role) || !e->role ||
        !fetch(p,"episode",slot,"text",&e->text) || !e->text ||
        !fetch(p,"episode",slot,"timestamp",&e->timestamp) || !e->timestamp ||
        !fetch(p,"episode",slot,"event_type",&e->event_type) || !e->event_type ||
        !fetch(p,"episode",slot,"topics_csv",&e->topics_csv) || !e->topics_csv ||
        !fetch(p,"episode",slot,"source_type",&e->source_type) || !e->source_type ||
        !fetch(p,"episode",slot,"ultimate_source_memory_id",&e->ultimate_source_memory_id) || !e->ultimate_source_memory_id ||
        !fetch(p,"episode",slot,"authority",&v) || !v || !parse_d(v,&e->authority)) goto fail;
    free(v); v=NULL;
    if (!fetch(p,"episode",slot,"order",&v) || !v || !parse_l(v,&e->order)) goto fail;
    free(v); v=NULL;
    if (!fetch(p,"episode",slot,"superseded",&v) || !v || !parse_l(v,&sup)) goto fail;
    free(v); e->superseded=(int)sup; return 1;
fail:
    free(v); memoria_persistence_free_episode(e); return 0;
}

int memoria_persistence_sync(memoria_persistence *p) {
    return p && bdr_atomic_c_sync(p->db) == BDR_ATOMIC_C_OK;
}

void memoria_persistence_free_turn(memoria_persist_turn *t) {
    if (!t) return;
    free(t->memory_id); free(t->text); free(t->role); free(t->source_type); free(t->ultimate_source_memory_id);
    memset(t,0,sizeof(*t));
}

void memoria_persistence_free_episode(memoria_persist_episode *e) {
    if (!e) return;
    free(e->episode_id); free(e->role); free(e->text); free(e->timestamp); free(e->event_type); free(e->topics_csv);
    free(e->source_type); free(e->ultimate_source_memory_id);
    memset(e,0,sizeof(*e));
}

void memoria_persistence_close(memoria_persistence *p) {
    if (!p) return;
    if (p->db) bdr_atomic_c_close(p->db);
    free(p->org);
    free(p);
}
