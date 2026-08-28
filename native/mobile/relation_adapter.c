#include "relation_adapter.h"

#include <stdio.h>
#include <string.h>

static int append(char *out, size_t out_size, size_t *used, const char *text) {
    size_t n = strlen(text);
    if (*used + n + 1 > out_size) return 0;
    memcpy(out + *used, text, n);
    *used += n;
    out[*used] = 0;
    return 1;
}

static int append_escaped(char *out, size_t out_size, size_t *used, const char *text) {
    const unsigned char *p = (const unsigned char *)(text ? text : "");
    char esc[3] = {'\\', 0, 0};
    while (*p) {
        switch (*p) {
            case '"': esc[1] = '"'; if (!append(out,out_size,used,esc)) return 0; break;
            case '\\': esc[1] = '\\'; if (!append(out,out_size,used,esc)) return 0; break;
            case '\n': esc[1] = 'n'; if (!append(out,out_size,used,esc)) return 0; break;
            case '\r': esc[1] = 'r'; if (!append(out,out_size,used,esc)) return 0; break;
            case '\t': esc[1] = 't'; if (!append(out,out_size,used,esc)) return 0; break;
            default: {
                char one[2] = {(char)*p,0};
                if (!append(out,out_size,used,one)) return 0;
            }
        }
        ++p;
    }
    return 1;
}

int memoria_relations_to_json(const memoria_relation *relations, size_t relation_count,
                              const char *source_memory_id, char *out, size_t out_size) {
    size_t i, used = 0;
    char number[64];
    if (!out || out_size == 0 || (!relations && relation_count)) return 0;
    out[0] = 0;
    if (!append(out,out_size,&used,"[")) return 0;
    for (i = 0; i < relation_count; ++i) {
        if (i && !append(out,out_size,&used,",")) return 0;
        if (!append(out,out_size,&used,"{\"subject\":\"")) return 0;
        if (!append_escaped(out,out_size,&used,relations[i].subject)) return 0;
        if (!append(out,out_size,&used,"\",\"predicate\":\"")) return 0;
        if (!append_escaped(out,out_size,&used,relations[i].predicate)) return 0;
        if (!append(out,out_size,&used,"\",\"object\":\"")) return 0;
        if (!append_escaped(out,out_size,&used,relations[i].object)) return 0;
        if (!append(out,out_size,&used,"\",\"confidence\":")) return 0;
        snprintf(number,sizeof(number),"%.6f",relations[i].confidence);
        if (!append(out,out_size,&used,number)) return 0;
        if (!append(out,out_size,&used,",\"source_memory_id\":\"")) return 0;
        if (!append_escaped(out,out_size,&used,source_memory_id ? source_memory_id : "")) return 0;
        if (!append(out,out_size,&used,"\"}")) return 0;
    }
    return append(out,out_size,&used,"]");
}
