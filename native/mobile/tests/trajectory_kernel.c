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
    CHECK(r.memory_count==1);
    CHECK(r.used_window==1);

    r=memoria_trajectory_resolve("and its model","s1",s1,2,sources,3);
    CHECK(r.hit==1);
    CHECK(strcmp(r.memory_id,"m1")==0);
    CHECK(r.memory_count==1);
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

    /* A collective reference may select exactly two independently grounded roots. */
    {
        memoria_trajectory_turn pair_window[] = {
            {"pair","user","device alpha and device beta are being compared",1}
        };
        r=memoria_trajectory_resolve("and the model of both","pair",pair_window,1,sources,3);
        CHECK(r.hit==1);
        CHECK(r.used_window==1);
        CHECK(r.memory_count==2);
        CHECK(strcmp(r.memory_ids[0],"m1")==0);
        CHECK(strcmp(r.memory_ids[1],"m2")==0);

        r=memoria_trajectory_resolve("e o modelo dos dois","pair",pair_window,1,sources,3);
        CHECK(r.hit==1);
        CHECK(r.memory_count==2);
        CHECK(strcmp(r.memory_ids[0],"m1")==0);
        CHECK(strcmp(r.memory_ids[1],"m2")==0);
    }

    /* Generated echoes sharing one ultimate root cannot impersonate a second antecedent. */
    {
        memoria_semantic_source rooted_sources[] = {
            {"r1","controller east mode is eco",1.0,1,"user_assertion","r1"},
            {"echo","controller east mode is eco",0.35,2,"assistant_generated","r1"},
            {"r2","controller west mode is sport",1.0,3,"user_assertion","r2"}
        };
        memoria_trajectory_turn rooted_window[] = {
            {"roots","user","controller east and controller west",1}
        };
        r=memoria_trajectory_resolve("mode of both","roots",rooted_window,1,rooted_sources,3);
        CHECK(r.hit==1);
        CHECK(r.memory_count==2);
        CHECK(strcmp(r.memory_ids[0],"r1")==0);
        CHECK(strcmp(r.memory_ids[1],"r2")==0);
    }

    /* Three equally plausible roots make a request for a pair unresolved. */
    {
        memoria_semantic_source three_sources[] = {
            {"t1","node alpha state is ready",1.0,1,"user_assertion","t1"},
            {"t2","node beta state is ready",1.0,2,"user_assertion","t2"},
            {"t3","node gamma state is ready",1.0,3,"user_assertion","t3"}
        };
        memoria_trajectory_turn three_window[] = {
            {"three","user","node alpha node beta node gamma",1}
        };
        r=memoria_trajectory_resolve("state of both","three",three_window,1,three_sources,3);
        CHECK(r.hit==0);
    }

    /* Ordinal intent reverses the default recency preference when justified. */
    {
        memoria_semantic_source ordered_sources[] = {
            {"o1","sensor east calibration is A1",1.0,10,"user_assertion","o1"},
            {"o2","sensor west calibration is B2",1.0,11,"user_assertion","o2"}
        };
        memoria_trajectory_turn ordered_window[] = {
            {"ord","user","sensor east calibration is A1",1},
            {"ord","user","sensor west calibration is B2",2}
        };

        r=memoria_trajectory_resolve("which sensor calibration did I mention first","ord",ordered_window,2,ordered_sources,2);
        CHECK(r.hit==1);
        CHECK(strcmp(r.memory_id,"o1")==0);
        CHECK(r.used_window==1);

        r=memoria_trajectory_resolve("which sensor calibration did I mention last","ord",ordered_window,2,ordered_sources,2);
        CHECK(r.hit==1);
        CHECK(strcmp(r.memory_id,"o2")==0);
        CHECK(r.used_window==1);

        r=memoria_trajectory_resolve("qual calibracao de sensor mencionei primeiro","ord",ordered_window,2,ordered_sources,2);
        CHECK(r.hit==1);
        CHECK(strcmp(r.memory_id,"o1")==0);

        r=memoria_trajectory_resolve("qual calibracao de sensor mencionei último","ord",ordered_window,2,ordered_sources,2);
        CHECK(r.hit==1);
        CHECK(strcmp(r.memory_id,"o2")==0);
    }
    return 0;
}
