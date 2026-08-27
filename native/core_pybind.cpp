#include <pybind11/pybind11.h>
#include <pybind11/stl.h>

#include <algorithm>
#include <cmath>
#include <cstdint>
#include <string>
#include <unordered_map>
#include <unordered_set>
#include <utility>
#include <vector>

namespace py = pybind11;

namespace {
struct Feature { int offset; std::string token; bool operator==(const Feature& o) const noexcept { return offset == o.offset && token == o.token; } };
struct FeatureHash { std::size_t operator()(const Feature& f) const noexcept { std::size_t h1=std::hash<int>{}(f.offset), h2=std::hash<std::string>{}(f.token); return h1 ^ (h2 + 0x9e3779b97f4a7c15ULL + (h1<<6) + (h1>>2)); } };
using Profile=std::unordered_map<Feature,std::uint64_t,FeatureHash>;
using TokenCounts=std::unordered_map<std::string,std::uint64_t>;
using RankedPair=std::pair<std::string,double>;
using ConceptMap=std::unordered_map<std::string,std::vector<std::string>>;
using ConceptSet=std::unordered_set<std::string>;

struct RelationFeature {
 std::string left; int offset; std::string right;
 bool operator==(const RelationFeature& o) const noexcept { return offset==o.offset && left==o.left && right==o.right; }
};
struct RelationFeatureHash {
 std::size_t operator()(const RelationFeature& f) const noexcept {
  std::size_t h=std::hash<std::string>{}(f.left);
  auto mix=[&](std::size_t v){h^=v+0x9e3779b97f4a7c15ULL+(h<<6)+(h>>2);};
  mix(std::hash<int>{}(f.offset));mix(std::hash<std::string>{}(f.right));return h;
 }
};
using RelationProfile=std::unordered_map<RelationFeature,std::uint64_t,RelationFeatureHash>;

class StructuralScorer {
public:
 explicit StructuralScorer(int window=3):window_(window){if(window_<1)throw py::value_error("window must be >= 1");}
 void register_pattern(const std::string&id,const std::vector<std::string>&tokens,std::uint64_t repeat=1){
  if(id.empty())throw py::value_error("concept_id must not be empty");if(tokens.size()<2)throw py::value_error("pattern must contain at least two tokens");if(repeat<1)throw py::value_error("repeat must be >= 1");
  py::gil_scoped_release r;auto features=features_nogil(tokens,window_);auto& profile=profiles_[id];for(const auto&[f,count]:features)profile[f]+=count*repeat;norms_[id]=norm_nogil(profile);
 }
 std::vector<RankedPair> rank(const std::vector<std::string>&tokens,std::size_t top_k=2)const{
  std::vector<RankedPair> ranked;py::gil_scoped_release r;auto query=features_nogil(tokens,window_);if(query.empty())return ranked;double qnorm=norm_nogil(query);if(!qnorm)return ranked;ranked.reserve(profiles_.size());
  for(const auto&[id,profile]:profiles_){const RelationProfile*sm=&query,*lg=&profile;if(sm->size()>lg->size())std::swap(sm,lg);double dot=0.0;for(const auto&[f,v]:*sm){auto it=lg->find(f);if(it!=lg->end())dot+=double(v)*double(it->second);}auto nit=norms_.find(id);double pnorm=nit==norms_.end()?0.0:nit->second;ranked.emplace_back(id,pnorm?dot/(qnorm*pnorm):0.0);}
  std::sort(ranked.begin(),ranked.end(),[](const RankedPair&a,const RankedPair&b){if(a.second!=b.second)return a.second>b.second;return a.first<b.first;});if(top_k&&ranked.size()>top_k)ranked.resize(top_k);return ranked;
 }
 std::size_t concepts()const noexcept{return profiles_.size();}
private:
 static RelationProfile features_nogil(const std::vector<std::string>&tokens,int window){RelationProfile out;for(std::size_t i=0;i<tokens.size();++i){auto hi=std::min(tokens.size(),i+static_cast<std::size_t>(window)+1);for(std::size_t j=i+1;j<hi;++j){int off=static_cast<int>(j-i);out[RelationFeature{tokens[i],off,tokens[j]}]+=1;out[RelationFeature{tokens[j],-off,tokens[i]}]+=1;}}return out;}
 static double norm_nogil(const RelationProfile&p){double n2=0.0;for(const auto&[_,v]:p)n2+=double(v)*double(v);return std::sqrt(n2);}
 int window_;std::unordered_map<std::string,RelationProfile>profiles_;std::unordered_map<std::string,double>norms_;
};

class ContextScorer {
public:
 explicit ContextScorer(int radius=2):radius_(radius){ if(radius_<1) throw py::value_error("radius must be >= 1"); }
 void observe(const std::vector<std::string>& t){ py::gil_scoped_release r; norm_cache_valid_=false;disc_index_dirty_=true; for(std::size_t i=0;i<t.size();++i){ const auto& node=t[i]; auto& p=profiles_[node]; auto& u=unordered_[node]; ++observations_[node]; const std::size_t lo=i>static_cast<std::size_t>(radius_)?i-radius_:0, hi=std::min(t.size(),i+static_cast<std::size_t>(radius_)+1); for(std::size_t j=lo;j<hi;++j){ if(j==i)continue; Feature f{static_cast<int>(j)-static_cast<int>(i),t[j]}; auto it=p.find(f); if(it==p.end()){feature_df_[f]+=1;p.emplace(std::move(f),1);}else ++it->second; ++u[t[j]]; } } }
 void prepare(){py::gil_scoped_release r;ensure_norm_cache_nogil();}
 void register_concept(const std::string& id,const std::vector<std::string>& anchors){auto& dst=concepts_[id];bool changed=false;for(const auto& anchor:anchors){if(std::find(dst.begin(),dst.end(),anchor)==dst.end()){dst.push_back(anchor);changed=true;}}if(changed)disc_index_dirty_=true;}
 double similarity(const std::string&a,const std::string&b)const{py::gil_scoped_release r;ensure_norm_cache_nogil();return similarity_nogil(a,b);}
 double unordered_similarity(const std::string&a,const std::string&b)const{py::gil_scoped_release r;ensure_norm_cache_nogil();return unordered_similarity_nogil(a,b);}
 double relation_strength(const std::string&a,const std::string&b,int offset)const{py::gil_scoped_release r;return relation_strength_nogil(a,b,offset);}
 std::vector<RankedPair> nearest(const std::string& node,std::size_t top_k=5)const{std::vector<RankedPair> s;{py::gil_scoped_release r;ensure_norm_cache_nogil();if(profiles_.find(node)==profiles_.end())return s;s.reserve(profiles_.size()?profiles_.size()-1:0);for(const auto&[o,_]:profiles_){if(o!=node)s.emplace_back(o,similarity_nogil(node,o));}std::sort(s.begin(),s.end(),cmp);if(s.size()>top_k)s.resize(top_k);}return s;}
 std::vector<RankedPair> rank_concepts(const std::string& query,const ConceptMap& concepts,std::size_t top_k=2)const{py::gil_scoped_release r;ensure_norm_cache_nogil();return rank_map_nogil(query,concepts,nullptr,top_k);}
 std::vector<RankedPair> rank_registered(const std::string& query,const std::vector<std::string>& candidate_ids,std::size_t top_k=2)const{py::gil_scoped_release r;ensure_norm_cache_nogil();return rank_map_nogil(query,concepts_,candidate_ids.empty()?nullptr:&candidate_ids,top_k);}
 std::vector<std::string> discriminative_candidates(const std::string& query,std::size_t limit)const{py::gil_scoped_release r;return discriminative_candidates_nogil(query,limit);}
 std::size_t nodes()const noexcept{return profiles_.size();}
 std::size_t concepts()const noexcept{return concepts_.size();}
private:
 static bool cmp(const RankedPair& x,const RankedPair& y){if(x.second!=y.second)return x.second>y.second;return x.first<y.first;}
 std::vector<RankedPair> rank_map_nogil(const std::string& query,const ConceptMap& concepts,const std::vector<std::string>* candidates,std::size_t top_k)const{
  std::vector<RankedPair> ranked;
  auto score_one=[&](const std::string&id,const std::vector<std::string>&anchors){double best=0.0;for(const auto&a:anchors)best=std::max(best,std::max(similarity_nogil(query,a),unordered_similarity_nogil(query,a)));ranked.emplace_back(id,best);};
  if(candidates){ranked.reserve(candidates->size());for(const auto&id:*candidates){auto it=concepts.find(id);if(it!=concepts.end())score_one(it->first,it->second);}}
  else{ranked.reserve(concepts.size());for(const auto&[id,anchors]:concepts)score_one(id,anchors);}
  std::sort(ranked.begin(),ranked.end(),cmp);if(top_k&&ranked.size()>top_k)ranked.resize(top_k);return ranked;
 }
 void rebuild_discriminative_index_nogil()const{
  if(!disc_index_dirty_)return;
  disc_feature_to_concepts_.clear();disc_feature_df_.clear();
  for(const auto&[id,anchors]:concepts_){ConceptSet features;for(const auto&anchor:anchors){auto it=unordered_.find(anchor);if(it==unordered_.end())continue;for(const auto&[token,_]:it->second)features.insert(token);}for(const auto&feature:features)disc_feature_to_concepts_[feature].insert(id);}
  for(const auto&[feature,ids]:disc_feature_to_concepts_)disc_feature_df_[feature]=ids.size();disc_index_dirty_=false;
 }
 std::vector<std::string> discriminative_candidates_nogil(const std::string& query,std::size_t limit)const{
  rebuild_discriminative_index_nogil();auto qit=unordered_.find(query);if(qit==unordered_.end()||qit->second.empty()||limit==0)return {};
  const double n=static_cast<double>(std::max<std::size_t>(1,concepts_.size()));std::unordered_map<std::string,double> scores;
  for(const auto&[feature,_]:qit->second){auto dfit=disc_feature_df_.find(feature);if(dfit==disc_feature_df_.end()||dfit->second==0)continue;const double w=std::log((n+1.0)/(static_cast<double>(dfit->second)+1.0))+1.0;auto fit=disc_feature_to_concepts_.find(feature);if(fit==disc_feature_to_concepts_.end())continue;for(const auto&id:fit->second)scores[id]+=w;}
  std::vector<RankedPair> ranked;ranked.reserve(scores.size());for(const auto&[id,score]:scores)ranked.emplace_back(id,score);std::sort(ranked.begin(),ranked.end(),cmp);if(ranked.size()>limit)ranked.resize(limit);std::vector<std::string> out;out.reserve(ranked.size());for(const auto&[id,_]:ranked)out.push_back(id);return out;
 }
 double relation_strength_nogil(const std::string&a,const std::string&b,int offset)const{
  if(offset==0||std::abs(offset)>radius_)return 0.0;auto it=profiles_.find(a);if(it==profiles_.end())return 0.0;std::uint64_t total=0,match=0;
  for(const auto&[f,count]:it->second){if(f.offset!=offset)continue;total+=count;if(f.token==b)match+=count;}
  return total?static_cast<double>(match)/static_cast<double>(total):0.0;
 }
 double weight(const Feature&f)const{double n=static_cast<double>(std::max<std::size_t>(1,profiles_.size()));auto it=feature_df_.find(f);double df=it==feature_df_.end()?0.0:static_cast<double>(it->second);return std::log((n+1.0)/(df+1.0))+1.0;}
 void ensure_norm_cache_nogil()const{if(norm_cache_valid_)return;weighted_norms_.clear();unordered_norms_.clear();weighted_norms_.reserve(profiles_.size());unordered_norms_.reserve(unordered_.size());for(const auto&[node,p]:profiles_){double n2=0.0;for(const auto&[f,v]:p){double x=double(v)*weight(f);n2+=x*x;}weighted_norms_[node]=std::sqrt(n2);}for(const auto&[node,p]:unordered_){double n2=0.0;for(const auto&[_,v]:p)n2+=double(v)*double(v);unordered_norms_[node]=std::sqrt(n2);}norm_cache_valid_=true;}
 double similarity_nogil(const std::string&a,const std::string&b)const{auto ia=profiles_.find(a),ib=profiles_.find(b);if(ia==profiles_.end()||ib==profiles_.end()||ia->second.empty()||ib->second.empty())return 0.0;const Profile*sm=&ia->second,*lg=&ib->second;if(sm->size()>lg->size())std::swap(sm,lg);double dot=0;for(const auto&[f,av]:*sm){auto it=lg->find(f);if(it!=lg->end()){double w=weight(f);dot+=double(av)*double(it->second)*w*w;}}auto nait=weighted_norms_.find(a),nbit=weighted_norms_.find(b);double na=nait==weighted_norms_.end()?0.0:nait->second,nb=nbit==weighted_norms_.end()?0.0:nbit->second;return na&&nb?dot/(na*nb):0.0;}
 double unordered_similarity_nogil(const std::string&a,const std::string&b)const{auto ia=unordered_.find(a),ib=unordered_.find(b);if(ia==unordered_.end()||ib==unordered_.end()||ia->second.empty()||ib->second.empty())return 0.0;const TokenCounts*sm=&ia->second,*lg=&ib->second;if(sm->size()>lg->size())std::swap(sm,lg);double dot=0;for(const auto&[t,av]:*sm){auto it=lg->find(t);if(it!=lg->end())dot+=double(av)*double(it->second);}auto nait=unordered_norms_.find(a),nbit=unordered_norms_.find(b);double na=nait==unordered_norms_.end()?0.0:nait->second,nb=nbit==unordered_norms_.end()?0.0:nbit->second;return na&&nb?dot/(na*nb):0.0;}
 int radius_;std::unordered_map<std::string,Profile>profiles_;std::unordered_map<std::string,TokenCounts>unordered_;std::unordered_map<Feature,std::uint64_t,FeatureHash>feature_df_;std::unordered_map<std::string,std::uint64_t>observations_;ConceptMap concepts_;mutable bool norm_cache_valid_=false;mutable std::unordered_map<std::string,double>weighted_norms_;mutable std::unordered_map<std::string,double>unordered_norms_;mutable bool disc_index_dirty_=true;mutable std::unordered_map<std::string,ConceptSet>disc_feature_to_concepts_;mutable std::unordered_map<std::string,std::size_t>disc_feature_df_;
};
}
PYBIND11_MODULE(_core_native,m){
 m.doc()="Native CPU hot paths for Memoria.ia resolutive core";
 py::class_<ContextScorer>(m,"ContextScorer").def(py::init<int>(),py::arg("radius")=2).def("observe",&ContextScorer::observe).def("prepare",&ContextScorer::prepare).def("register_concept",&ContextScorer::register_concept).def("similarity",&ContextScorer::similarity).def("unordered_similarity",&ContextScorer::unordered_similarity).def("relation_strength",&ContextScorer::relation_strength,py::arg("left"),py::arg("right"),py::arg("offset")).def("nearest",&ContextScorer::nearest,py::arg("node"),py::arg("top_k")=5).def("rank_concepts",&ContextScorer::rank_concepts,py::arg("query"),py::arg("concepts"),py::arg("top_k")=2).def("rank_registered",&ContextScorer::rank_registered,py::arg("query"),py::arg("candidate_ids"),py::arg("top_k")=2).def("discriminative_candidates",&ContextScorer::discriminative_candidates,py::arg("query"),py::arg("limit")).def_property_readonly("nodes",&ContextScorer::nodes).def_property_readonly("concepts",&ContextScorer::concepts);
 py::class_<StructuralScorer>(m,"StructuralScorer").def(py::init<int>(),py::arg("window")=3).def("register_pattern",&StructuralScorer::register_pattern,py::arg("concept_id"),py::arg("tokens"),py::arg("repeat")=1).def("rank",&StructuralScorer::rank,py::arg("tokens"),py::arg("top_k")=2).def_property_readonly("concepts",&StructuralScorer::concepts);
}
