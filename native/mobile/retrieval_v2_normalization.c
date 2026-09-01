#include "retrieval_v2_normalization.h"

#include <ctype.h>
#include <string.h>

#define TOKEN_CAP 96u

struct alias_pair { const char *from; const char *to; };

static char fold_latin1(unsigned char lead, unsigned char tail) {
    if (lead != 0xC3) return 0;
    switch (tail) {
        case 0x80: case 0x81: case 0x82: case 0x83: case 0x84:
        case 0xA0: case 0xA1: case 0xA2: case 0xA3: case 0xA4: return 'a';
        case 0x88: case 0x89: case 0x8A: case 0x8B:
        case 0xA8: case 0xA9: case 0xAA: case 0xAB: return 'e';
        case 0x8C: case 0x8D: case 0x8E: case 0x8F:
        case 0xAC: case 0xAD: case 0xAE: case 0xAF: return 'i';
        case 0x92: case 0x93: case 0x94: case 0x95: case 0x96:
        case 0xB2: case 0xB3: case 0xB4: case 0xB5: case 0xB6: return 'o';
        case 0x99: case 0x9A: case 0x9B: case 0x9C:
        case 0xB9: case 0xBA: case 0xBB: case 0xBC: return 'u';
        case 0x87: case 0xA7: return 'c';
        case 0x91: case 0xB1: return 'n';
        default: return 0;
    }
}

static int ascii_fold(const char *input, char out[TOKEN_CAP]) {
    size_t r = 0u, w = 0u;
    if (!input) return 0;
    while (input[r]) {
        unsigned char ch = (unsigned char)input[r];
        char folded = 0;
        if (ch < 0x80) {
            ++r;
            if (isalnum(ch)) folded = (char)tolower(ch);
        } else if (input[r + 1]) {
            folded = fold_latin1(ch, (unsigned char)input[r + 1]);
            r += 2u;
        } else {
            ++r;
        }
        if (folded) {
            if (w + 1u >= TOKEN_CAP) return 0;
            out[w++] = folded;
        }
    }
    out[w] = 0;
    return w > 0u;
}

static int protected_trailing_s(const char *w) {
    static const char *protected_words[] = {
        "pais", "mais", "dois", "tres", "seis", "ingles", "frances", "mes", "gas"
    };
    size_t i;
    for (i = 0u; i < sizeof(protected_words)/sizeof(protected_words[0]); ++i)
        if (strcmp(w, protected_words[i]) == 0) return 1;
    return 0;
}

static void apply_alias(char *w) {
    static const struct alias_pair aliases[] = {
        {"voltagem", "tensao"}, {"voltagens", "tensao"}, {"tensoes", "tensao"},
        {"frequencias", "frequencia"}, {"capacidades", "capacidade"},
        {"codigos", "codigo"}, {"parametros", "parametro"},
        {"baterias", "bateria"}, {"modulos", "modulo"},
        {"servidores", "servidor"}, {"valores", "valor"},
        {"portas", "porta"}, {"temperaturas", "temperatura"},
        {"principais", "principal"},
        {"nacoes", "pais"}, {"nacao", "pais"}, {"paises", "pais"},
        {"idiomas", "lingua"}, {"idioma", "lingua"}, {"linguas", "lingua"},
        {"oceans", "ocean"}, {"countries", "country"}, {"languages", "language"}
    };
    size_t i;
    for (i = 0u; i < sizeof(aliases)/sizeof(aliases[0]); ++i) {
        if (strcmp(w, aliases[i].from) == 0) {
            strcpy(w, aliases[i].to);
            return;
        }
    }
}

static void conservative_plural(char *w) {
    size_t n;
    if (!w || !*w || protected_trailing_s(w)) return;
    n = strlen(w);
    if (n <= 4u || w[n - 1u] != 's') return;

    /* Regular Portuguese plurals such as bateria(s), modulo(s), porta(s),
     * cidade(s), limite(s). Irregular forms are handled by aliases above. */
    if (n >= 3u && w[n - 2u] == 'e' && (w[n - 3u] == 'r' || w[n - 3u] == 'z')) {
        w[n - 2u] = 0; /* servidores -> servidor, luzes -> luz */
        return;
    }
    w[n - 1u] = 0;
}

int memoria_retrieval_v2_normalize_token(const char *input, char *out, size_t out_size) {
    char token[TOKEN_CAP];
    size_t n;
    if (!out || out_size == 0u) return 0;
    out[0] = 0;
    if (!ascii_fold(input, token)) return 0;
    apply_alias(token);
    conservative_plural(token);
    apply_alias(token);
    n = strlen(token);
    if (!n || n + 1u > out_size) return 0;
    memcpy(out, token, n + 1u);
    return 1;
}
