#include "episodic_kernel.h"
#include <assert.h>
#include <string.h>

int main(void) {
    memoria_episode_source episodes[] = {
        {"e1","assistant","first creation about transport",1,"2026-08-28T10:00:00Z","creation","transport","assistant_generated",0.35,"e1",0},
        {"e2","user","unrelated note",2,0,0,"misc","user_assertion",1.0,"e2",0},
        {"e3","assistant","second creation about transport",3,"2026-08-28T10:05:00Z","creation","transport","assistant_generated",0.35,"e3",0}
    };
    memoria_episode_result r = memoria_episode_recall_latest("last creation about transport","assistant","creation","transport",episodes,3);
    assert(r.hit == 1);
    assert(strcmp(r.episode_id,"e3") == 0);
    assert(r.order == 3);
    assert(strcmp(r.source_type,"assistant_generated") == 0);

    episodes[2].superseded = 1;
    r = memoria_episode_recall_latest("last creation about transport","assistant","creation","transport",episodes,3);
    assert(r.hit == 1 && strcmp(r.episode_id,"e1") == 0);

    memoria_episode_source ambiguous[] = {
        {"a","assistant","note alpha",4,0,"note","alpha","assistant_generated",0.35,"a",0},
        {"b","assistant","note beta",4,0,"note","beta","assistant_generated",0.35,"b",0}
    };
    r = memoria_episode_recall_latest("last note","assistant","note",0,ambiguous,2);
    assert(r.hit == 0);

    r = memoria_episode_recall_latest("unknown satellite event",0,0,0,episodes,3);
    assert(r.hit == 0);
    return 0;
}
