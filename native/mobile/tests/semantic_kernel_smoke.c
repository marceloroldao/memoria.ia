#include "semantic_kernel.h"

#include <assert.h>

int main(void) {
    {
        memoria_kernel_candidate candidates[] = {
            {"root-user", "root-user", "Minha fonte principal é 24 V.", 0.95, 1},
            {"echo-assistant", "root-user", "Minha fonte principal é 24 V.", 0.95, 2},
        };
        memoria_kernel_result result = memoria_kernel_resolve(
            "Qual é a fonte principal?", candidates, 2
        );
        assert(result.status == MEMORIA_KERNEL_HIT);
        assert(result.selected_index == 0);
    }

    {
        memoria_kernel_candidate candidates[] = {
            {"north", "north", "Atlas é norte.", 0.95, 1},
            {"south", "south", "Atlas é sul.", 0.95, 2},
        };
        memoria_kernel_result result = memoria_kernel_resolve(
            "Atlas é onde?", candidates, 2
        );
        assert(result.status == MEMORIA_KERNEL_UNRESOLVED);
    }

    {
        memoria_kernel_candidate candidates[] = {
            {"unrelated", "unrelated", "Relatório financeiro mensal.", 0.95, 1},
        };
        memoria_kernel_result result = memoria_kernel_resolve(
            "temperatura do laboratório", candidates, 1
        );
        assert(result.status == MEMORIA_KERNEL_UNRESOLVED);
    }

    return 0;
}
