#include <pybind11/pybind11.h>
#include <pybind11/stl.h>

#include <algorithm>
#include <cmath>
#include <cstdint>
#include <string>
#include <unordered_map>
#include <utility>
#include <vector>

namespace py = pybind11;

namespace {
struct Feature { int offset; std::string token; bool operator==(const Feature& o) const noexcept { return offset == o.offset && token == o.token; } };
struct FeatureHash { std::size_t operator()(const Feature& f) const noexcept { std::size_t h1=std::hash<int>{}(f.offset), h2=std::hash<std::string>{}(f.token); return h1 ^ (h2 + 0x9e3779b97f4a7c15ULL + (h1<<6) + (h1>>2)); } };
using Profile=std::unordered_map<Feature,std::uint64_t,FeatureHash>;
using TokenCounts=std::unordered_map<std::string,std::uint64_t>;
using RankedPair=std::pair<std::string,double>;

class ContextScorer {
public:
 explicit ContextScorer(int radius=2):radius_(radius){ if(radius_<1) throw py::value_error("radius must be >= 1"); }
 void observe(const std::vector<std::string>& t){ py::gil_scoped_release r; for(std::size_t i=0;i<t.size();++i){ const auto& node=t[i]; auto& p=profiles_[node]; auto& u=unordered_[node]; ++observations_[node]; const std::size_t lo=i>static_cast<std::size_t>(radius_)?i-radius_:0, hi=std::min(t.size(),i+static_cast<std::size_t>(radius_)+1); for(std::size_t j=lo;j<hi;++j){ if(j==i)continue; Feature f{static_cast<int>(j)-static_cast<int>(i),t[j]}; auto it=p.find(f); if(it==p.end()){feature_df_[f]+=1;p.emplace(std::move(f),1);}else ++it->second; ++u[t[j]]; } } }
 double similarity(const std::string&a,const std::string&b)const{py::gil_scoped_release r;return similarity_nogil(a,b);} double unordered_similarity(const std::string&a,const std::string&b)const{py::gil_scoped_release r;return unordered_similarity_nogil(a,b);}
 std::vector<RankedPair> nearest(const std::string& node,std::size_t top_k=5)const{std::vector<RankedPair> s;{py::gil_scoped_release r;if(profiles_.find(node)==profiles_.end())return s;s.reserve(profiles_.size()?profiles_.size()-1:0);for(const auto&[o,_]:profiles_){if(o!=node)s.emplace_back(o,similarity_nogil(node,o));}std::sort(s.begin(),s.end(),cmp);if(s.size()>top_k)s.resize(top_k);}return s;}
 std::vector<RankedPair> rank_concepts(const std::string& query,const std::unordered_map<std::string,std::vector<std::string>>& concepts,std::size_t top_k=2)const{std::vector<RankedPair> ranked;ranked.reserve(concepts.size());{py::gil_scoped_release r;for(const auto&[id,anchors]:concepts){double best=0.0;for(const auto&a:anchors)best=std::max(best,std::max(similarity_nogil(query,a),unordered_similarity_nogil(query,a)));ranked.emplace_back(id,best);}std::sort(ranked.begin(),ranked.end(),cmp);if(top_k&&ranked.size()>top_k)ranked.resize(top_k);}return ranked;}
 std::size_t nodes()const noexcept{return profiles_.size();}
private:
 static bool cmp(const RankedPair& x,const RankedPair& y){if(x.second!=y.second)return x.second>y.second;return x.first<y.first;}
 double weight(const Feature&f)const{double n=static_cast<double>(std::max<std::size_t>(1,profiles_.size()));auto it=feature_df_.find(f);double df=it==feature_df_.end()?0.0:static_cast<double>(it->second);return std::log((n+1.0)/(df+1.0))+1.0;}
 double similarity_nogil(const std::string&a,const std::string&b)const{auto ia=profiles_.find(a),ib=profiles_.find(b);if(ia==profiles_.end()||ib==profiles_.end()||ia->second.empty()||ib->second.empty())return 0.0;const Profile*sm=&ia->second,*lg=&ib->second;if(sm->size()>lg->size())std::swap(sm,lg);double dot=0;for(const auto&[f,av]:*sm){auto it=lg->find(f);if(it!=lg->end()){double w=weight(f);dot+=double(av)*double(it->second)*w*w;}}double na=0,nb=0;for(const auto&[f,v]:ia->second){double x=double(v)*weight(f);na+=x*x;}for(const auto&[f,v]:ib->second){double x=double(v)*weight(f);nb+=x*x;}return na&&nb?dot/(std::sqrt(na)*std::sqrt(nb)):0.0;}
 double unordered_similarity_nogil(const std::string&a,const std::string&b)const{auto ia=unordered_.find(a),ib=unordered_.find(b);if(ia==unordered_.end()||ib==unordered_.end()||ia->second.empty()||ib->second.empty())return 0.0;const TokenCounts*sm=&ia->second,*lg=&ib->second;if(sm->size()>lg->size())std::swap(sm,lg);double dot=0;for(const auto&[t,av]:*sm){auto it=lg->find(t);if(it!=lg->end())dot+=double(av)*double(it->second);}double na=0,nb=0;for(const auto&[_,v]:ia->second)na+=double(v)*double(v);for(const auto&[_,v]:ib->second)nb+=double(v)*double(v);return na&&nb?dot/(std::sqrt(na)*std::sqrt(nb)):0.0;}
 int radius_;std::unordered_map<std::string,Profile>profiles_;std::unordered_map<std::string,TokenCounts>unordered_;std::unordered_map<Feature,std::uint64_t,FeatureHash>feature_df_;std::unordered_map<std::string,std::uint64_t>observations_;
};
}
PYBIND11_MODULE(_core_native,m){m.doc()="Native CPU hot paths for Memoria.ia resolutive core";py::class_<ContextScorer>(m,"ContextScorer").def(py::init<int>(),py::arg("radius")=2).def("observe",&ContextScorer::observe).def("similarity",&ContextScorer::similarity).def("unordered_similarity",&ContextScorer::unordered_similarity).def("nearest",&ContextScorer::nearest,py::arg("node"),py::arg("top_k")=5).def("rank_concepts",&ContextScorer::rank_concepts,py::arg("query"),py::arg("concepts"),py::arg("top_k")=2).def_property_readonly("nodes",&ContextScorer::nodes);}
