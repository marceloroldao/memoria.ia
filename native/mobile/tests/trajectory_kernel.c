#include "trajectory_kernel.h"

#include <stdio.h>
#include <string.h>

#define CHECK(expr) do { if (!(expr)) { fprintf(stderr,"CHECK failed: %s (%s:%d)\n",#expr,__FILE__,__LINE__); return 1; } } while (0)

int main(void) {
    memoria_semantic_source sources[] = {
        {"m1","device alpha model is N7",1.0,1,"user_assertion","m1"},
        {"m2","device beta model is Q4",1.0,2,"user_assertion","m2"},
        {"m3","warehouse temperature is 18 degrees",1.0,3,"user_assertion","m3"}
    };
    memoria_trajectory_turn s1[] = {
        {"s1","user","we are comparing device alpha and device beta",1},
        {"s1","assistant","device alpha is the cobalt unit",2}
    };
    memoria_trajectory_result r;

    r=memoria_trajectory_resolve("what model is the cobalt one","s1",s1,2,sources,3);
    CHECK(r.hit==1);
    CHECK(strcmp(r.memory_id,"m1")==0);
    CHECK(r.used_window==1);

    r=memoria_trajectory_resolve("and its model","s1",s1,2,sources,3);
    CHECK(r.hit==1);
    CHECK(strcmp(r.memory_id,"m1")==0);
    CHECK(r.used_window==1);

    r=memoria_trajectory_resolve("and its model","s2",s1,2,sources,3);
    CHECK(r.hit==0);

    r=memoria_trajectory_resolve("warehouse temperature","s2",s1,2,sources,3);
    CHECK(r.hit==1);
    CHECK(strcmp(r.memory_id,"m3")==0);

    {
        memoria_trajectory_turn ambiguous[] = {
            {"s3","user","device alpha and device beta are both relevant",1}
        };
        r=memoria_trajectory_resolve("what is its model","s3",ambiguous,1,sources,3);
        CHECK(r.hit==0);
    }
    return 0;
}
