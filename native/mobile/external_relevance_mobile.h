#ifndef MEMORIA_EXTERNAL_RELEVANCE_MOBILE_H
#define MEMORIA_EXTERNAL_RELEVANCE_MOBILE_H

#include "memoria_mobile.h"

memoria_mobile_status memoria_mobile_learn_external_knowledge_guarded_json(
    memoria_mobile_handle *handle,
    memoria_mobile_buffer request_json,
    memoria_mobile_buffer *response_json
);

#endif
