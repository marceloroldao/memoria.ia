#include "mobile_persistence.h"
#include "bdr/atomic_c_api.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define KEY_CAP 384
#define VALUE_CAP 128
#define MAX_BATCH_OPS 32

struct memoria_persistence {
    bdr_atomic_c_handle *db;
    char *organization_id;
};

static char *dup_string(const char *s) {
    size_t n;
    char *out;
    if (!s) s = "";
    n = strlen(s) + 1;
    out = (char *)malloc(n);
    if (out) memcpy(out, s, n);
    return out;
}

static int make_key(memoria_persistence *p, char *out, size_t cap, const char *kind, size_t slot, const char *field) {
    int n;
    if (!p || !out || !kind || !field) return 0;
    if (slot) n = snprintf(out, cap, "memoria-mobile/v1/%s/%s/%06zu/%s", p->organization_id, kind, slot, field);
    else n = snprintf(out, cap, "memoria-mobile/v1/%s/%s/%s", p->organization_id, kind, field);
    return n > 0 && (size_t)n < cap;
}

static int get_alloc(memoria_persistence *p, const char *key, char **out) {
    bdr_atomic_c_buffer b = {0};
    bdr_atomic_c_status s;
    char *copy;
    if (!p || !key || !out) return 0;
    *out = NULL;
    s = bdr_atomic_c_get(p->db, key, strlen(key), &b);
    if (s == BDR_ATOMIC_C_NOT_FOUND) return 1;
    if (s != BDR_ATOMIC_C_OK) return 0;
    copy = (char *)malloc(b.size + 1);
    if (!copy) { bdr_atomic_c_free_buffer(b); return 0; }
    if (b.size) memcpy(copy, b.data, b.size);
    copy[b.size] = 0;
    bdr_atomic_c_free_buffer(b);
    *out = copy;
    return 1;
}

static int get_ulong(memoria_persistence *p, const char *kind, const char *field, unsigned long *out) {
    char key[KEY_CAP], *value = NULL, *end = NULL;
    unsigned long v;
    if (!make_key(p, key, sizeof(key), kind, 0, field) || !get_alloc(p, key, &value)) return 0;
    if (!value) { *out = 0; return 1; }
    v = strtoul(value, &end, 10);
    if (end == value || *end) { free(value); return 0; }
    free(value); *out = v; return 1;
}

static void op_put(bdr_atomic_c_operation *op, const char *key, const char *value) {
    op->type = BDR_ATOMIC_C_PUT;
    op->key = key; op->key_size = strlen(key);
    op->value = value; op->value_size = strlen(value);
}

static int put_field(memoria_persistence *p, const char *kind, size_t slot, const char *field,
                     const char *value, bdr_atomic_c_operation *ops, char keys[][KEY_CAP], size_t *count) {
    size_t i = *count;
    if (i >= MAX_BATCH_OPS || !make_key(p, keys[i], KEY_CAP, kind, slot, field)) return 0;
    op_put(&ops[i], keys[i], value ? value : "");
    *count = i + 1;
    return 1;
}

static int put_meta(memoria_persistence *p, const char *field, const char *value,
                    bdr_atomic_c_operation *ops, char keys[][KEY_CAP], size_t *count) {
    return put_field(p, "meta", 0, field, value, ops, keys, count);
}

static int read_field(memoria_persistence *p, const char *kind, size_t slot, const char *field, char **out) {
    char key[KEY_CAP];
    if (!make_key(p, key, sizeof(key), kind, slot, field)) return 0;
    return get_alloc(p, key, out);
}

static int parse_long_field(memoria_persistence *p, const char *kind, size_t slot, const char *field, long *out) {
    char *v = NULL, *end = NULL;
    long x;
    if (!read_field(p, kind, slot, field, &v) || !v) return 0;
    x = strtol(v, &end, 10);
    if (end == v || *end) { free(v); return 0; }
    free(v); *out = x; return 1;
}

static int parse_double_field(memoria_persistence *p, const char *kind, size_t slot, const char *field, double *out) {
    char *v = NULL, *end = NULL;
    double x;
    if (!read_field(p, kind, slot, field, &v) || !v) return 0;
    x = strtod(v, &end);
    if (end == v || *end) { free(v); return 0; }
    free(v); *out = x; return 1;
}

int memoria_persistence_open(const char *data_dir, const char *organization_id, memoria_persistence **out) {
    memoria_persistence *p;
    if (!data_dir || !*data_dir || !organization_id || !*organization_id || !out) return 0;
    p = (memoria_persistence *)calloc(1, sizeof(*p));
    if (!p) return 0;
    p->organization_id = dup_string(organization_id);
    if (!p->organization_id || bdr_atomic_c_open(data_dir, &p->db) != BDR_ATOMIC_C_OK) {
        memoria_persistence_close(p); return 0;
    }
    if (bdr_atomic_c_abi_version() != BDR_ATOMIC_C_ABI_VERSION ||
        bdr_atomic_c_integrity_check(p->db) != BDR_ATOMIC_C_OK) {
        memoria_persistence_close(p); return 0;
    }
    *out = p;
    return 1;
}

int memoria_persistence_meta(memoria_persistence *p, size_t *turn_count, size_t *episode_count, unsigned long *sequence) {
    unsigned long schema = 0, turns = 0, episodes = 0, seq = 0;
    char key[KEY_CAP], *schema_value = NULL;
    if (!p || !turn_count || !episode_count || !sequence) return 0;
    if (!make_key(p, key, sizeof(key), "meta", 0, "schema") || !get_alloc(p, key, &schema_value)) return 0;
    if (schema_value) {
        char *end = NULL;
        schema = strtoul(schema_value, &end, 10);
        free(schema_value);
        if (!end || schema != MEMORIA_MOBILE_STATE_SCHEMA) return 0;
    }
    if (!get_ulong(p, "meta", "turn_count", &turns) ||
        !get_ulong(p, "meta", "episode_count", &episodes) ||
        !get_ulong(p, "meta", "sequence", &seq)) return 0;
    *turn_count = (size_t)turns;
    *episode_count = (size_t)episodes;
    *sequence = seq;
    return 1;
}

int memoria_persistence_save_turn(memoria_persistence *p, size_t slot, unsigned long sequence, const memoria_persist_turn *t) {
    bdr_atomic_c_operation ops[MAX_BATCH_OPS];
    char keys[MAX_BATCH_OPS][KEY_CAP];
    char values[16][VALUE_CAP];
    size_t n = 0, i;
    bdr_atomic_c_batch_result result = {0};
    if (!p || !slot || !t || !t->memory_id || !t->text || !t->role || t->relation_count > MEMORIA_PERSIST_MAX_RELATIONS) return 0;
    snprintf(values[0], VALUE_CAP, "%u", MEMORIA_MOBILE_STATE_SCHEMA);
    snprintf(values[1], VALUE_CAP, "%zu", slot);
    snprintf(values[2], VALUE_CAP, "%lu", sequence);
    snprintf(values[3], VALUE_CAP, "%.17g", t->authority);
    snprintf(values[4], VALUE_CAP, "%ld", t->order);
    snprintf(values[5], VALUE_CAP, "%zu", t->relation_count);
    if (!put_meta(p,"schema",values[0],ops,keys,&n) || !put_meta(p,"turn_count",values[1],ops,keys,&n) ||
        !put_meta(p,"sequence",values[2],ops,keys,&n) ||
        !put_field(p,"turn",slot,"memory_id",t->memory_id,ops,keys,&n) ||
        !put_field(p,"turn",slot,"text",t->text,ops,keys,&n) ||
        !put_field(p,"turn",slot,"role",t->role,ops,keys,&n) ||
        !put_field(p,"turn",slot,"source_type",t->source_type,ops,keys,&n) ||
        !put_field(p,"turn",slot,"ultimate_source_memory_id",t->ultimate_source_memory_id,ops,keys,&n) ||
        !put_field(p,"turn",slot,"authority",values[3],ops,keys,&n) ||
        !put_field(p,"turn",slot,"order",values[4],ops,keys,&n) ||
        !put_field(p,"turn",slot,"relation_count",values[5],ops,keys,&n)) return 0;
    for (i=0;i<t->relation_count;++i) {
        char field[64];
        snprintf(field,sizeof(field),"relation/%zu/subject",i);
        if(!put_field(p,"turn",slot,field,t->relations[i].subject,ops,keys,&n)) return 0;
        snprintf(field,sizeof(field),"relation/%zu/predicate",i);
        if(!put_field(p,"turn",slot,field,t->relations[i].predicate,ops,keys,&n)) return 0;
        snprintf(field,sizeof(field),"relation/%zu/object",i);
        if(!put_field(p,"turn",slot,field,t->relations[i].object,ops,keys,&n)) return 0;
        snprintf(values[6+i],VALUE_CAP,"%.17g",t->relations[i].confidence);
        snprintf(field,sizeof(field),"relation/%zu/confidence",i);
        if(!put_field(p,"turn",slot,field,values[6+i],ops,keys,&n)) return 0;
    }
    return bdr_atomic_c_write_batch(p->db,ops,n,&result)==BDR_ATOMIC_C_OK && result.durable && result.operations==n;
}

int memoria_persistence_load_turn(memoria_persistence *p, size_t slot, memoria_persist_turn *t) {
    char *count = NULL, *end = NULL;
    unsigned long relation_count;
    size_t i;
    if (!p || !slot || !t) return 0;
    memset(t,0,sizeof(*t));
    if (!read_field(p,"turn",slot,"memory_id",&t->memory_id) || !t->memory_id ||
        !read_field(p,"turn",slot,"text",&t->text) || !t->text ||
        !read_field(p,"turn",slot,"role",&t->role) || !t->role ||
        !read_field(p,"turn",slot,"source_type",&t->source_type) || !t->source_type ||
        !read_field(p,"turn",slot,"ultimate_source_memory_id",&t->ultimate_source_memory_id) || !t->ultimate_source_memory_id ||
        !parse_double_field(p,"turn",slot,"authority",&t->authority) ||
        !parse_long_field(p,"turn",slot,"order",&t->order) ||
        !read_field(p,"turn",slot,"relation_count",&count) || !count) goto fail;
    relation_count = strtoul(count,&end,10); free(count); count=NULL;
    if (end==count || relation_count>MEMORIA_PERSIST_MAX_RELATIONS) goto fail;
    t->relation_count=(size_t)relation_count;
    for(i=0;i<t->relation_count;++i){
        char field[64], *v=NULL;
        snprintf(field,sizeof(field),"relation/%zu/subject",i); if(!read_field(p,"turn",slot,field,&v)||!v) goto fail; snprintf(t->relations[i].subject,sizeof(t->relations[i].subject),"%s",v); free(v);
        snprintf(field,sizeof(field),"relation/%zu/predicate",i); v=NULL; if(!read_field(p,"turn",slot,field,&v)||!v) goto fail; snprintf(t->relations[i].predicate,sizeof(t->relations[i].predicate),"%s",v); free(v);
        snprintf(field,sizeof(field),"relation/%zu/object",i); v=NULL; if(!read_field(p,"turn",slot,field,&v)||!v) goto fail; snprintf(t->relations[i].object,sizeof(t->relations[i].object),"%s",v); free(v);
        snprintf(field,sizeof(field),"relation/%zu/confidence",i); if(!parse_double_field(p,"turn",slot,field,&t->relations[i].confidence)) goto fail;
    }
    return 1;
fail:
    free(count); memoria_persistence_free_turn(t); return 0;
}

int memoria_persistence_save_episode(memoria_persistence *p, size_t slot, unsigned long sequence, const memoria_persist_episode *e) {
    bdr_atomic_c_operation ops[MAX_BATCH_OPS]; char keys[MAX_BATCH_OPS][KEY_CAP]; char values[8][VALUE_CAP]; size_t n=0; bdr_atomic_c_batch_result result={0};
    if(!p||!slot||!e||!e->episode_id||!e->role||!e->text) return 0;
    snprintf(values[0],VALUE_CAP,"%u",MEMORIA_MOBILE_STATE_SCHEMA); snprintf(values[1],VALUE_CAP,"%zu",slot); snprintf(values[2],VALUE_CAP,"%lu",sequence);
    snprintf(values[3],VALUE_CAP,"%.17g",e->authority); snprintf(values[4],VALUE_CAP,"%ld",e->order); snprintf(values[5],VALUE_CAP,"%d",e->superseded);
    if(!put_meta(p,"schema",values[0],ops,keys,&n)||!put_meta(p,"episode_count",values[1],ops,keys,&n)||!put_meta(p,"sequence",values[2],ops,keys,&n)||
       !put_field(p,"episode",slot,"episode_id",e->episode_id,ops,keys,&n)||!put_field(p,"episode",slot,"role",e->role,ops,keys,&n)||
       !put_field(p,"episode",slot,"text",e->text,ops,keys,&n)||!put_field(p,"episode",slot,"timestamp",e->timestamp,ops,keys,&n)||
       !put_field(p,"episode",slot,"event_type",e->event_type,ops,keys,&n)||!put_field(p,"episode",slot,"topics_csv",e->topics_csv,ops,keys,&n)||
       !put_field(p,"episode",slot,"source_type",e->source_type,ops,keys,&n)||!put_field(p,"episode",slot,"ultimate_source_memory_id",e->ultimate_source_memory_id,ops,keys,&n)||
       !put_field(p,"episode",slot,"authority",values[3],ops,keys,&n)||!put_field(p,"episode",slot,"order",values[4],ops,keys,&n)||
       !put_field(p,"episode",slot,"superseded",values[5],ops,keys,&n)) return 0;
    return bdr_atomic_c_write_batch(p->db,ops,n,&result)==BDR_ATOMIC_C_OK && result.durable && result.operations==n;
}

int memoria_persistence_load_episode(memoria_persistence *p, size_t slot, memoria_persist_episode *e) {
    long superseded=0;
    if(!p||!slot||!e) return 0; memset(e,0,sizeof(*e));
    if(!read_field(p,"episode",slot,"episode_id",&e->episode_id)||!e->episode_id||!read_field(p,"episode",slot,"role",&e->role)||!e->role||
       !read_field(p,"episode",slot,"text",&e->text)||!e->text||!read_field(p,"episode",slot,"timestamp",&e->timestamp)||!e->timestamp||
       !read_field(p,"episode",slot,"event_type",&e->event_type)||!e->event_type||!read_field(p,"episode",slot,"topics_csv",&e->topics_csv)||!e->topics_csv||
       !read_field(p,"episode",slot,"source_type",&e->source_type)||!e->source_type||!read_field(p,"episode",slot,"ultimate_source_memory_id",&e->ultimate_source_memory_id)||!e->ultimate_source_memory_id||
       !parse_double_field(p,"episode",slot,"authority",&e->authority)||!parse_long_field(p,"episode",slot,"order",&e->order)||
       !parse_long_field(p,"episode",slot,"superseded",&superseded)) goto fail;
    e->superseded=(int)superseded; return 1;
fail: memoria_persistence_free_episode(e); return 0;
}

int memoria_persistence_sync(memoria_persistence *p) { return p && bdr_atomic_c_sync(p->db)==BDR_ATOMIC_C_OK; }
void memoria_persistence_free_turn(memoria_persist_turn *t){ if(!t)return; free(t->memory_id);free(t->text);free(t->role);free(t->source_type);free(t->ultimate_source_memory_id);memset(t,0,sizeof(*t)); }
void memoria_persistence_free_episode(memoria_persist_episode *e){ if(!e)return;free(e->episode_id);free(e->role);free(e->text);free(e->timestamp);free(e->event_type);free(e->topics_csv);free(e->source_type);free(e->ultimate_source_memory_id);memset(e,0,sizeof(*e)); }
void memoria_persistence_close(memoria_persistence *p){ if(!p)return; if(p->db)bdr_atomic_c_close(p->db); free(p->organization_id); free(p); }
