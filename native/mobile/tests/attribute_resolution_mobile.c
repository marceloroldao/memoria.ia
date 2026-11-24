#include "memoria_mobile.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define CHECK(expr) do { if (!(expr)) { fprintf(stderr, "CHECK failed: %s (%d)\n", #expr, __LINE__); return 1; } } while (0)

static int learn(memoria_mobile_handle *handle, const char *json) {
    memoria_mobile_buffer input = {(const uint8_t *)json, strlen(json)}, output = {0};
    memoria_mobile_status status = memoria_mobile_learn_turn_json(handle, input, &output);
    memoria_mobile_free_buffer(output);
    return status == MEMORIA_MOBILE_OK;
}

static int check_queries(memoria_mobile_handle *handle) {
    static const struct {
        const char *question;
        const char *source;
        const char *property;
    } cases[] = {
        {"A QUEM PERTENCE A BIKE QUE SE DOBRA DE PASSEIO?", "fold-owner", "owner"},
        {"A quem pertence a bicicleta dobrável?", NULL, NULL},
        {"Qual o horário de saída da composição ferroviária circular?", "train-departure", "departure_time"},
        {"Quem dirige o trem circular?", "train-driver", "driver"},
        {"Quem dirige o trem noturno?", NULL, NULL},
        {"Onde guardaram a bateria sobressalente da câmera?", "battery-place", "location"},
        {"Qual é a cor da bateria reserva da câmera?", NULL, NULL},
        {"Quanto pesa a mala de Rui?", "bag-weight", "weight"},
        {"Qual é a cor da mala de Rui?", "bag-color", "color"},
        {"Quem instalou o sensor do jardim?", "sensor-installer", "installer"},
        {"Quem dirige a van serrana?", NULL, NULL},
        {"Em que dia foi entregue a encomenda com os cabos?", NULL, NULL},
        {"Em que dia chegou o pacote de cabos?", "arrival-date", "arrival_day"},
        {"Em que dia chegou o pacote de parafusos?", NULL, NULL},
        {"Em que dia entregaram a encomenda com os filtros?", "delivery-date", "delivery_day"},
        {"A quem pertence a bicicleta dobrável azul?", "exact-bike", "owner"},
        {"A quem pertence a bicicleta que se dobra azul?", NULL, NULL},
    };
    for (size_t i = 0; i < sizeof(cases) / sizeof(cases[0]); ++i) {
        char json[512], source_field[128], property_field[128];
        snprintf(json, sizeof(json), "{\"query\":\"%s\",\"namespace\":\"test\"}", cases[i].question);
        memoria_mobile_buffer input = {(const uint8_t *)json, strlen(json)}, output = {0};
        memoria_mobile_status status = memoria_mobile_resolve_context_json(handle, input, &output);
        const char *body = (const char *)output.data;
        if (cases[i].source) {
            CHECK(status == MEMORIA_MOBILE_OK && body);
            snprintf(source_field, sizeof(source_field), "\"source_memory_id\":\"%s\"", cases[i].source);
            snprintf(property_field, sizeof(property_field), "\"predicate\":\"%s\"", cases[i].property);
            CHECK(strstr(body, source_field));
            CHECK(strstr(body, property_field));
            CHECK(strstr(body, "\"provenance\""));
        } else {
            CHECK(status == MEMORIA_MOBILE_UNRESOLVED && body);
            CHECK(strstr(body, "\"attribute_resolution_used\":true"));
        }
        memoria_mobile_free_buffer(output);
    }
    return 0;
}

int main(void) {
    static const char *rows[] = {
        "{\"memory_id\":\"fold-owner\",\"text\":\"O dono da bicicleta dobrável de passeio é Caio.\"}",
        "{\"memory_id\":\"other-fold\",\"text\":\"A dona da bicicleta dobrável de trilha é Lia.\"}",
        "{\"memory_id\":\"train-departure\",\"text\":\"O trem circular parte às cinco horas.\"}",
        "{\"memory_id\":\"train-driver\",\"text\":\"A motorista do trem circular é Dalva.\"}",
        "{\"memory_id\":\"night-train\",\"text\":\"O trem noturno parte às dez horas.\"}",
        "{\"memory_id\":\"battery-place\",\"text\":\"A bateria reserva da câmera fica na caixa verde.\"}",
        "{\"memory_id\":\"bag-weight\",\"text\":\"A mala de Rui pesa 9,5 quilos.\"}",
        "{\"memory_id\":\"bag-color\",\"text\":\"A mala de Rui é amarela.\"}",
        "{\"memory_id\":\"sensor-installer\",\"text\":\"O instalador do sensor do jardim é Luan.\"}",
        "{\"memory_id\":\"arrival-date\",\"text\":\"O pacote de cabos chegou na terça-feira.\"}",
        "{\"memory_id\":\"arrival-place\",\"text\":\"O pacote de parafusos chegou na portaria.\"}",
        "{\"memory_id\":\"delivery-date\",\"text\":\"O pacote de filtros foi entregue na quarta-feira.\"}",
        "{\"memory_id\":\"exact-bike\",\"text\":\"A dona da bicicleta dobrável azul é Lia.\"}",
        "{\"memory_id\":\"other-bike\",\"text\":\"A dona da bike dobrável azul é Iara.\"}",
    };
    char path[] = "./tmp-mobile-attributes-XXXXXX";
    memoria_mobile_handle *handle = NULL;
    CHECK(mkdtemp(path));
    CHECK(memoria_mobile_open(path, "org-attributes", &handle) == MEMORIA_MOBILE_OK);
    for (size_t i = 0; i < sizeof(rows) / sizeof(rows[0]); ++i) {
        char turn[512];
        snprintf(turn, sizeof(turn), "{\"role\":\"user\",\"namespace\":\"test\",%s", rows[i] + 1);
        CHECK(learn(handle, turn));
    }
    CHECK(learn(handle, "{\"role\":\"user\",\"namespace\":\"other\",\"text\":\"O motorista da van serrana é Ivo.\"}"));
    CHECK(learn(handle, "{\"role\":\"assistant\",\"namespace\":\"test\","
        "\"text\":\"O motorista da van serrana é Davi.\",\"source_authority\":1.0}"));
    CHECK(check_queries(handle) == 0);
    CHECK(memoria_mobile_flush(handle) == MEMORIA_MOBILE_OK);
    memoria_mobile_close(handle);
    CHECK(memoria_mobile_open(path, "org-attributes", &handle) == MEMORIA_MOBILE_OK);
    CHECK(check_queries(handle) == 0);
    memoria_mobile_close(handle);

    char cleanup[96];
    snprintf(cleanup, sizeof(cleanup), "rm -rf -- %s", path);
    CHECK(system(cleanup) == 0);
    return 0;
}
