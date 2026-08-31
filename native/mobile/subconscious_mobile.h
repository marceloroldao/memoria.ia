#ifndef MEMORIA_SUBCONSCIOUS_MOBILE_H
#define MEMORIA_SUBCONSCIOUS_MOBILE_H

#include "memoria_mobile.h"

void memoria_subconscious_mobile_observe_resolution(
    memoria_mobile_handle *handle,
    memoria_mobile_buffer request_json,
    memoria_mobile_status status,
    memoria_mobile_buffer response_json
);

void memoria_subconscious_mobile_forget_handle(memoria_mobile_handle *handle);

#endif
