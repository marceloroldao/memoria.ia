#include "structural_text_kernel.h"

#include <math.h>
#include <stdlib.h>
#include <string.h>

typedef struct memoria_structural_edge {
    uint64_t source;
    uint64_t target;
    unsigned char channel;
    double weight;
    uint64_t observations;
    uint64_t last_tick;
} memoria_structural_edge;

typedef struct memoria_structural_recent {
    uint64_t tick;
    uint64_t *trail;
    size_t trail_count;
} memoria_structural_recent;

struct memoria_structural_text_field {
    size_t max_within_distance;
    size_t max_event_lag;
    double forgetting_rate;
    uint64_t tick;
    memoria_structural_edge *edges;
    size_t edge_count;
    size_t edge_capacity;
    memoria_structural_recent *recent;
    size_t recent_count;
    size_t recent_capacity;
};

typedef struct blake2b_ctx {
    uint64_t h[8];
    uint64_t t0;
    uint64_t t1;
    unsigned char buf[128];
    size_t buflen;
} blake2b_ctx;

static const uint64_t B2_IV[8] = {
    UINT64_C(0x6a09e667f3bcc908), UINT64_C(0xbb67ae8584caa73b),
    UINT64_C(0x3c6ef372fe94f82b), UINT64_C(0xa54ff53a5f1d36f1),
    UINT64_C(0x510e527fade682d1), UINT64_C(0x9b05688c2b3e6c1f),
    UINT64_C(0x1f83d9abfb41bd6b), UINT64_C(0x5be0cd19137e2179)
};

static const unsigned char B2_SIGMA[12][16] = {
    {0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15},
    {14,10,4,8,9,15,13,6,1,12,0,2,11,7,5,3},
    {11,8,12,0,5,2,15,13,10,14,3,6,7,1,9,4},
    {7,9,3,1,13,12,11,14,2,6,5,10,4,0,15,8},
    {9,0,5,7,2,4,10,15,14,1,11,12,6,8,3,13},
    {2,12,6,10,0,11,8,3,4,13,7,5,15,14,1,9},
    {12,5,1,15,14,13,4,10,0,7,6,3,9,2,8,11},
    {13,11,7,14,12,1,3,9,5,0,15,4,8,6,2,10},
    {6,15,14,9,11,3,0,8,12,2,13,7,1,4,10,5},
    {10,2,8,4,7,6,1,5,15,11,9,14,3,12,13,0},
    {0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15},
    {14,10,4,8,9,15,13,6,1,12,0,2,11,7,5,3}
};

static uint64_t rotr64(uint64_t x, unsigned int c) {
    return (x >> c) | (x << (64u - c));
}

static uint64_t load64_le(const unsigned char *p) {
    uint64_t v = 0;
    size_t i;
    for (i = 0; i < 8; ++i) v |= ((uint64_t)p[i]) << (8u * i);
    return v;
}

static void store64_le(unsigned char *p, uint64_t v) {
    size_t i;
    for (i = 0; i < 8; ++i) p[i] = (unsigned char)((v >> (8u * i)) & 0xffu);
}

static void blake2b_init8(blake2b_ctx *ctx) {
    size_t i;
    memset(ctx, 0, sizeof(*ctx));
    for (i = 0; i < 8; ++i) ctx->h[i] = B2_IV[i];
    /* digest_length=8, key_length=0, fanout=1, depth=1 */
    ctx->h[0] ^= UINT64_C(0x01010008);
}

static void blake2b_increment(blake2b_ctx *ctx, uint64_t n) {
    const uint64_t before = ctx->t0;
    ctx->t0 += n;
    if (ctx->t0 < before) ++ctx->t1;
}

static void blake2b_compress(blake2b_ctx *ctx, const unsigned char block[128], int last) {
    uint64_t m[16];
    uint64_t v[16];
    size_t i;
    int r;
    for (i = 0; i < 16; ++i) m[i] = load64_le(block + i * 8u);
    for (i = 0; i < 8; ++i) {
        v[i] = ctx->h[i];
        v[i + 8] = B2_IV[i];
    }
    v[12] ^= ctx->t0;
    v[13] ^= ctx->t1;
    if (last) v[14] = ~v[14];

#define G(a,b,c,d,x,y) do { \
    v[a] = v[a] + v[b] + (x); v[d] = rotr64(v[d] ^ v[a], 32); \
    v[c] = v[c] + v[d];       v[b] = rotr64(v[b] ^ v[c], 24); \
    v[a] = v[a] + v[b] + (y); v[d] = rotr64(v[d] ^ v[a], 16); \
    v[c] = v[c] + v[d];       v[b] = rotr64(v[b] ^ v[c], 63); \
} while (0)

    for (r = 0; r < 12; ++r) {
        const unsigned char *s = B2_SIGMA[r];
        G(0,4,8,12,m[s[0]],m[s[1]]);
        G(1,5,9,13,m[s[2]],m[s[3]]);
        G(2,6,10,14,m[s[4]],m[s[5]]);
        G(3,7,11,15,m[s[6]],m[s[7]]);
        G(0,5,10,15,m[s[8]],m[s[9]]);
        G(1,6,11,12,m[s[10]],m[s[11]]);
        G(2,7,8,13,m[s[12]],m[s[13]]);
        G(3,4,9,14,m[s[14]],m[s[15]]);
    }
#undef G
    for (i = 0; i < 8; ++i) ctx->h[i] ^= v[i] ^ v[i + 8];
}

static void blake2b_update(blake2b_ctx *ctx, const unsigned char *input, size_t len) {
    while (len > 0) {
        const size_t space = 128u - ctx->buflen;
        const size_t take = len < space ? len : space;
        memcpy(ctx->buf + ctx->buflen, input, take);
        ctx->buflen += take;
        input += take;
        len -= take;
        if (ctx->buflen == 128u && len > 0) {
            blake2b_increment(ctx, 128u);
            blake2b_compress(ctx, ctx->buf, 0);
            ctx->buflen = 0;
        }
    }
}

static void blake2b_final8(blake2b_ctx *ctx, unsigned char out[8]) {
    unsigned char full[64];
    size_t i;
    blake2b_increment(ctx, (uint64_t)ctx->buflen);
    memset(ctx->buf + ctx->buflen, 0, 128u - ctx->buflen);
    blake2b_compress(ctx, ctx->buf, 1);
    for (i = 0; i < 8; ++i) store64_le(full + i * 8u, ctx->h[i]);
    memcpy(out, full, 8);
}

static int reserve_edges(memoria_structural_text_field *field, size_t need) {
    memoria_structural_edge *grown;
    size_t cap;
    if (need <= field->edge_capacity) return 1;
    cap = field->edge_capacity ? field->edge_capacity * 2u : 32u;
    while (cap < need) cap *= 2u;
    grown = (memoria_structural_edge *)realloc(field->edges, cap * sizeof(*grown));
    if (!grown) return 0;
    field->edges = grown;
    field->edge_capacity = cap;
    return 1;
}

static int reserve_recent(memoria_structural_text_field *field, size_t need) {
    memoria_structural_recent *grown;
    size_t cap;
    if (need <= field->recent_capacity) return 1;
    cap = field->recent_capacity ? field->recent_capacity * 2u : 8u;
    while (cap < need) cap *= 2u;
    grown = (memoria_structural_recent *)realloc(field->recent, cap * sizeof(*grown));
    if (!grown) return 0;
    field->recent = grown;
    field->recent_capacity = cap;
    return 1;
}

static double decayed(
    const memoria_structural_text_field *field,
    const memoria_structural_edge *edge
) {
    const uint64_t age = field->tick >= edge->last_tick ? field->tick - edge->last_tick : 0u;
    if (age == 0u || field->forgetting_rate == 0.0) return edge->weight;
    return edge->weight * exp(-field->forgetting_rate * (double)age);
}

static memoria_structural_edge *find_edge(
    memoria_structural_text_field *field,
    uint64_t source,
    uint64_t target,
    unsigned char channel
) {
    size_t i;
    for (i = 0; i < field->edge_count; ++i) {
        memoria_structural_edge *edge = &field->edges[i];
        if (edge->source == source && edge->target == target && edge->channel == channel) return edge;
    }
    return NULL;
}

static const memoria_structural_edge *find_edge_const(
    const memoria_structural_text_field *field,
    uint64_t source,
    uint64_t target,
    unsigned char channel
) {
    size_t i;
    for (i = 0; i < field->edge_count; ++i) {
        const memoria_structural_edge *edge = &field->edges[i];
        if (edge->source == source && edge->target == target && edge->channel == channel) return edge;
    }
    return NULL;
}

static int reinforce(
    memoria_structural_text_field *field,
    uint64_t source,
    uint64_t target,
    unsigned char channel,
    double amount
) {
    memoria_structural_edge *edge;
    if (amount <= 0.0) return 1;
    edge = find_edge(field, source, target, channel);
    if (!edge) {
        if (!reserve_edges(field, field->edge_count + 1u)) return 0;
        edge = &field->edges[field->edge_count++];
        memset(edge, 0, sizeof(*edge));
        edge->source = source;
        edge->target = target;
        edge->channel = channel;
        edge->last_tick = field->tick;
    } else {
        edge->weight = decayed(field, edge);
        edge->last_tick = field->tick;
    }
    edge->weight += amount;
    edge->observations += 1u;
    return 1;
}

static void trim_recent(memoria_structural_text_field *field) {
    while (field->recent_count > 0u) {
        memoria_structural_recent *first = &field->recent[0];
        if (field->tick - first->tick <= field->max_event_lag) break;
        free(first->trail);
        if (field->recent_count > 1u) {
            memmove(
                field->recent,
                field->recent + 1u,
                (field->recent_count - 1u) * sizeof(*field->recent)
            );
        }
        --field->recent_count;
    }
}

static int append_recent(
    memoria_structural_text_field *field,
    const uint64_t *trail,
    size_t trail_count
) {
    memoria_structural_recent *slot;
    uint64_t *copy;
    if (!reserve_recent(field, field->recent_count + 1u)) return 0;
    copy = (uint64_t *)malloc(trail_count * sizeof(*copy));
    if (!copy) return 0;
    memcpy(copy, trail, trail_count * sizeof(*copy));
    slot = &field->recent[field->recent_count++];
    slot->tick = field->tick;
    slot->trail = copy;
    slot->trail_count = trail_count;
    return 1;
}

static size_t unique_copy(const uint64_t *values, size_t count, uint64_t **out) {
    uint64_t *items;
    size_t i;
    size_t n = 0;
    if (!values || count == 0u) {
        *out = NULL;
        return 0u;
    }
    items = (uint64_t *)malloc(count * sizeof(*items));
    if (!items) {
        *out = NULL;
        return SIZE_MAX;
    }
    for (i = 0; i < count; ++i) {
        size_t j;
        int seen = 0;
        for (j = 0; j < n; ++j) {
            if (items[j] == values[i]) {
                seen = 1;
                break;
            }
        }
        if (!seen) items[n++] = values[i];
    }
    *out = items;
    return n;
}

static int utf8_decode_one(
    const unsigned char *input,
    size_t available,
    uint32_t *out_codepoint,
    size_t *out_consumed
) {
    unsigned char a;
    if (!input || available == 0u || !out_codepoint || !out_consumed) return 0;
    a = input[0];
    if (a < 0x80u) {
        *out_codepoint = a;
        *out_consumed = 1u;
        return 1;
    }
    if ((a & 0xe0u) == 0xc0u) {
        unsigned char b;
        uint32_t cp;
        if (available < 2u) return 0;
        b = input[1];
        if ((b & 0xc0u) != 0x80u) return 0;
        cp = ((uint32_t)(a & 0x1fu) << 6u) | (uint32_t)(b & 0x3fu);
        if (cp < 0x80u) return 0;
        *out_codepoint = cp;
        *out_consumed = 2u;
        return 1;
    }
    if ((a & 0xf0u) == 0xe0u) {
        unsigned char b;
        unsigned char d;
        uint32_t cp;
        if (available < 3u) return 0;
        b = input[1];
        d = input[2];
        if ((b & 0xc0u) != 0x80u || (d & 0xc0u) != 0x80u) return 0;
        cp = ((uint32_t)(a & 0x0fu) << 12u)
            | ((uint32_t)(b & 0x3fu) << 6u)
            | (uint32_t)(d & 0x3fu);
        if (cp < 0x800u || (cp >= 0xd800u && cp <= 0xdfffu)) return 0;
        *out_codepoint = cp;
        *out_consumed = 3u;
        return 1;
    }
    if ((a & 0xf8u) == 0xf0u) {
        unsigned char b;
        unsigned char d;
        unsigned char e;
        uint32_t cp;
        if (available < 4u) return 0;
        b = input[1];
        d = input[2];
        e = input[3];
        if ((b & 0xc0u) != 0x80u || (d & 0xc0u) != 0x80u || (e & 0xc0u) != 0x80u) return 0;
        cp = ((uint32_t)(a & 0x07u) << 18u)
            | ((uint32_t)(b & 0x3fu) << 12u)
            | ((uint32_t)(d & 0x3fu) << 6u)
            | (uint32_t)(e & 0x3fu);
        if (cp < 0x10000u || cp > 0x10ffffu) return 0;
        *out_codepoint = cp;
        *out_consumed = 4u;
        return 1;
    }
    return 0;
}

static size_t utf8_encode_one(uint32_t cp, unsigned char out[4]) {
    if (cp <= 0x7fu) {
        out[0] = (unsigned char)cp;
        return 1u;
    }
    if (cp <= 0x7ffu) {
        out[0] = (unsigned char)(0xc0u | (cp >> 6u));
        out[1] = (unsigned char)(0x80u | (cp & 0x3fu));
        return 2u;
    }
    if (cp <= 0xffffu) {
        out[0] = (unsigned char)(0xe0u | (cp >> 12u));
        out[1] = (unsigned char)(0x80u | ((cp >> 6u) & 0x3fu));
        out[2] = (unsigned char)(0x80u | (cp & 0x3fu));
        return 3u;
    }
    if (cp <= 0x10ffffu) {
        out[0] = (unsigned char)(0xf0u | (cp >> 18u));
        out[1] = (unsigned char)(0x80u | ((cp >> 12u) & 0x3fu));
        out[2] = (unsigned char)(0x80u | ((cp >> 6u) & 0x3fu));
        out[3] = (unsigned char)(0x80u | (cp & 0x3fu));
        return 4u;
    }
    return 0u;
}

static int casefold_token(
    const char *token,
    size_t token_len,
    unsigned char **out_bytes,
    size_t *out_len
) {
    unsigned char *normalized;
    size_t pos = 0u;
    size_t written = 0u;
    size_t capacity;
    if (!token || token_len == 0u || !out_bytes || !out_len) return 0;
    capacity = token_len * 2u + 8u;
    normalized = (unsigned char *)malloc(capacity);
    if (!normalized) return 0;

    while (pos < token_len) {
        uint32_t cp;
        size_t consumed;
        unsigned char encoded[4];
        size_t encoded_len;
        if (!utf8_decode_one(
            (const unsigned char *)token + pos,
            token_len - pos,
            &cp,
            &consumed
        )) {
            free(normalized);
            return 0;
        }
        pos += consumed;

        if (cp >= (uint32_t)'A' && cp <= (uint32_t)'Z') {
            cp += (uint32_t)('a' - 'A');
        } else if ((cp >= 0x00c0u && cp <= 0x00d6u) ||
                   (cp >= 0x00d8u && cp <= 0x00deu)) {
            cp += 0x20u;
        } else if (cp == 0x00dfu) {
            if (written + 2u > capacity) {
                free(normalized);
                return 0;
            }
            normalized[written++] = (unsigned char)'s';
            normalized[written++] = (unsigned char)'s';
            continue;
        } else if (cp == 0x00b5u) {
            /* Python casefold: MICRO SIGN -> GREEK SMALL LETTER MU. */
            cp = 0x03bcu;
        }

        encoded_len = utf8_encode_one(cp, encoded);
        if (encoded_len == 0u || written + encoded_len > capacity) {
            free(normalized);
            return 0;
        }
        memcpy(normalized + written, encoded, encoded_len);
        written += encoded_len;
    }

    *out_bytes = normalized;
    *out_len = written;
    return 1;
}

static int token_codepoint(uint32_t cp) {
    if ((cp >= (uint32_t)'a' && cp <= (uint32_t)'z') ||
        (cp >= (uint32_t)'A' && cp <= (uint32_t)'Z') ||
        (cp >= (uint32_t)'0' && cp <= (uint32_t)'9') ||
        cp == (uint32_t)'_') return 1;
    return cp >= 0x00c0u && cp <= 0x00ffu;
}

int memoria_structural_text_symbol(
    const char *token,
    size_t token_len,
    uint64_t *out_symbol
) {
    static const unsigned char prefix[] = "memoria.ia:text-token:v1";
    blake2b_ctx ctx;
    unsigned char digest[8];
    unsigned char *normalized = NULL;
    size_t normalized_len = 0u;
    size_t i;
    uint64_t value = 0;
    if (!token || token_len == 0u || !out_symbol) return 0;
    if (!casefold_token(token, token_len, &normalized, &normalized_len)) return 0;
    blake2b_init8(&ctx);
    blake2b_update(&ctx, prefix, sizeof(prefix));
    blake2b_update(&ctx, normalized, normalized_len);
    blake2b_final8(&ctx, digest);
    free(normalized);
    for (i = 0; i < 8; ++i) value = (value << 8u) | (uint64_t)digest[i];
    *out_symbol = value;
    return 1;
}

int memoria_structural_text_tokenize(
    const char *text,
    size_t text_len,
    uint64_t *out_symbols,
    size_t out_capacity,
    size_t *out_count
) {
    size_t pos = 0u;
    size_t token_start = SIZE_MAX;
    size_t count = 0u;
    if (!text || !out_count) return 0;

    while (pos < text_len) {
        uint32_t cp;
        size_t consumed;
        const size_t cp_start = pos;
        if (!utf8_decode_one(
            (const unsigned char *)text + pos,
            text_len - pos,
            &cp,
            &consumed
        )) return 0;
        pos += consumed;

        if (token_codepoint(cp)) {
            if (token_start == SIZE_MAX) token_start = cp_start;
            continue;
        }

        if (token_start != SIZE_MAX) {
            if (out_symbols) {
                if (count >= out_capacity ||
                    !memoria_structural_text_symbol(
                        text + token_start,
                        cp_start - token_start,
                        &out_symbols[count]
                    )) return 0;
            }
            ++count;
            token_start = SIZE_MAX;
        }
    }

    if (token_start != SIZE_MAX) {
        if (out_symbols) {
            if (count >= out_capacity ||
                !memoria_structural_text_symbol(
                    text + token_start,
                    text_len - token_start,
                    &out_symbols[count]
                )) return 0;
        }
        ++count;
    }

    *out_count = count;
    return 1;
}

/* Reuse the tokenizer's Unicode boundaries and casefolding. This bridge only
 * contributes query evidence; observation addresses remain unchanged. */
static int next_surface_token(
    const char *text,
    size_t length,
    size_t *position,
    unsigned char **out,
    size_t *out_length
) {
    size_t start = SIZE_MAX;
    *out = NULL;
    *out_length = 0u;
    while (*position < length) {
        uint32_t cp;
        size_t consumed;
        size_t current = *position;
        if (!utf8_decode_one((const unsigned char *)text + current,
                length - current, &cp, &consumed)) return -1;
        *position += consumed;
        if (token_codepoint(cp)) {
            if (start == SIZE_MAX) start = current;
        } else if (start != SIZE_MAX) {
            return casefold_token(text + start, current - start, out, out_length) ? 1 : -1;
        }
    }
    if (start != SIZE_MAX)
        return casefold_token(text + start, length - start, out, out_length) ? 1 : -1;
    return 0;
}

int memoria_structural_text_surface_overlap(
    const char *query,
    const char *candidate,
    size_t *out_count
) {
    size_t query_position = 0u;
    size_t count = 0u;
    int found;
    if (!query || !candidate || !out_count) return 0;
    while (1) {
        unsigned char *q = NULL;
        size_t qlen = 0u;
        size_t candidate_position = 0u;
        found = next_surface_token(query, strlen(query), &query_position, &q, &qlen);
        if (found < 0) return 0;
        if (!found) break;
        while (1) {
            unsigned char *c = NULL;
            size_t clen = 0u;
            size_t common = 0u;
            size_t longest;
            found = next_surface_token(candidate, strlen(candidate),
                &candidate_position, &c, &clen);
            if (found < 0) { free(q); return 0; }
            if (!found) break;
            longest = qlen > clen ? qlen : clen;
            while (common < qlen && common < clen && q[common] == c[common])
                ++common;
            /* At least four shared bytes covering four fifths of the longer
             * surface. Exact equality is already counted by the symbol path. */
            if (common >= 4u && common < longest &&
                common * 5u >= longest * 4u) {
                ++count;
                free(c);
                break;
            }
            free(c);
        }
        free(q);
    }
    *out_count = count;
    return 1;
}

memoria_structural_text_field *memoria_structural_text_field_create(
    size_t max_within_distance,
    size_t max_event_lag,
    double forgetting_rate
) {
    memoria_structural_text_field *field;
    if (max_within_distance < 1u || max_event_lag < 1u || forgetting_rate < 0.0) return NULL;
    field = (memoria_structural_text_field *)calloc(1u, sizeof(*field));
    if (!field) return NULL;
    field->max_within_distance = max_within_distance;
    field->max_event_lag = max_event_lag;
    field->forgetting_rate = forgetting_rate;
    return field;
}

void memoria_structural_text_field_destroy(memoria_structural_text_field *field) {
    size_t i;
    if (!field) return;
    for (i = 0; i < field->recent_count; ++i) free(field->recent[i].trail);
    free(field->recent);
    free(field->edges);
    free(field);
}

int memoria_structural_text_field_observe(
    memoria_structural_text_field *field,
    const uint64_t *trail,
    size_t trail_count
) {
    size_t i;
    if (!field || (trail_count > 0u && !trail)) return 0;
    ++field->tick;
    trim_recent(field);

    for (i = 0; i < trail_count; ++i) {
        size_t j;
        size_t upper = i + field->max_within_distance + 1u;
        if (upper > trail_count) upper = trail_count;
        for (j = i + 1u; j < upper; ++j) {
            if (!reinforce(
                field,
                trail[i],
                trail[j],
                MEMORIA_STRUCTURAL_CHANNEL_WITHIN,
                1.0 / (double)(j - i)
            )) return 0;
        }
    }

    if (trail_count > 0u) {
        size_t r;
        for (r = 0; r < field->recent_count; ++r) {
            const memoria_structural_recent *previous = &field->recent[r];
            const uint64_t lag = field->tick - previous->tick;
            const double mass = 1.0 / (
                (double)lag * (double)previous->trail_count * (double)trail_count
            );
            size_t a;
            for (a = 0; a < previous->trail_count; ++a) {
                size_t b;
                for (b = 0; b < trail_count; ++b) {
                    if (!reinforce(
                        field,
                        previous->trail[a],
                        trail[b],
                        MEMORIA_STRUCTURAL_CHANNEL_TEMPORAL,
                        mass
                    )) return 0;
                }
            }
        }
        if (!append_recent(field, trail, trail_count)) return 0;
    }
    return 1;
}

double memoria_structural_text_field_association(
    const memoria_structural_text_field *field,
    uint64_t source,
    uint64_t target,
    int channel
) {
    double total = 0.0;
    int current;
    if (!field) return 0.0;
    if (channel != MEMORIA_STRUCTURAL_CHANNEL_ANY &&
        channel != MEMORIA_STRUCTURAL_CHANNEL_WITHIN &&
        channel != MEMORIA_STRUCTURAL_CHANNEL_TEMPORAL) return 0.0;

    for (current = MEMORIA_STRUCTURAL_CHANNEL_WITHIN;
         current <= MEMORIA_STRUCTURAL_CHANNEL_TEMPORAL;
         ++current) {
        const memoria_structural_edge *edge;
        if (channel != MEMORIA_STRUCTURAL_CHANNEL_ANY && current != channel) continue;
        edge = find_edge_const(field, source, target, (unsigned char)current);
        if (edge) total += decayed(field, edge);
    }
    return total;
}

size_t memoria_structural_text_field_edge_count(
    const memoria_structural_text_field *field
) {
    return field ? field->edge_count : 0u;
}

uint64_t memoria_structural_text_field_tick(
    const memoria_structural_text_field *field
) {
    return field ? field->tick : 0u;
}

int memoria_structural_text_score_candidate(
    const memoria_structural_text_field *field,
    const uint64_t *query,
    size_t query_count,
    const uint64_t *candidate,
    size_t candidate_count,
    memoria_structural_text_score *out_score
) {
    uint64_t *q = NULL;
    uint64_t *c = NULL;
    size_t qn;
    size_t cn;
    size_t exact = 0u;
    double mass = 0.0;
    size_t i;
    if (!field || !out_score || !query || !candidate || query_count == 0u || candidate_count == 0u) return 0;
    qn = unique_copy(query, query_count, &q);
    cn = unique_copy(candidate, candidate_count, &c);
    if (qn == SIZE_MAX || cn == SIZE_MAX || qn == 0u || cn == 0u) {
        free(q);
        free(c);
        return 0;
    }

    for (i = 0; i < qn; ++i) {
        size_t j;
        for (j = 0; j < cn; ++j) {
            if (q[i] == c[j]) {
                ++exact;
                break;
            }
        }
    }

    for (i = 0; i < qn; ++i) {
        size_t j;
        for (j = 0; j < cn; ++j) {
            double forward;
            double reverse;
            if (q[i] == c[j]) continue;
            forward = memoria_structural_text_field_association(
                field, q[i], c[j], MEMORIA_STRUCTURAL_CHANNEL_ANY
            );
            reverse = memoria_structural_text_field_association(
                field, c[j], q[i], MEMORIA_STRUCTURAL_CHANNEL_ANY
            );
            mass += forward > reverse ? forward : reverse;
        }
    }

    out_score->exact_overlap = exact;
    out_score->surface_overlap = 0u;
    out_score->association_mass = mass / ((double)qn * (double)cn);
    out_score->score = ((double)exact / (double)qn) + out_score->association_mass;
    free(q);
    free(c);
    return 1;
}
