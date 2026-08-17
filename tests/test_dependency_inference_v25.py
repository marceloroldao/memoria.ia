from memoria_resolutiva.dependency_inference import SourceDocument, infer_dependency, lexical_jaccard, origin_groups


def test_identical_text_has_max_lexical_similarity():
    assert lexical_jaccard("abc def", "abc def") == 1.0


def test_later_copy_is_linked_to_earlier_origin():
    docs = [
        SourceDocument("a", "diretor da empresa e carlos", 1.0),
        SourceDocument("b", "diretor da empresa e carlos", 1.1, cites=("a",)),
    ]
    edges = infer_dependency(docs)
    assert len(edges) == 1
    assert edges[0].source == "b"
    assert edges[0].probable_origin == "a"


def test_copy_chain_collapses_to_single_root():
    docs = [
        SourceDocument("root", "mesma informacao factual repetida", 1.0),
        SourceDocument("copy1", "mesma informacao factual repetida", 1.1, cites=("root",)),
        SourceDocument("copy2", "mesma informacao factual repetida", 1.2, cites=("copy1",)),
    ]
    groups = origin_groups(docs, infer_dependency(docs))
    assert groups["root"] == "root"
    assert groups["copy1"] == "root"
    assert groups["copy2"] == "root"


def test_independent_rewordings_are_not_forced_into_copy_group():
    docs = [
        SourceDocument("a", "registro oficial informa ana como diretora", 1.0),
        SourceDocument("b", "ata societaria confirma nomeacao de ana", 3.0),
        SourceDocument("c", "documento regulatorio lista ana na direcao", 5.0),
    ]
    groups = origin_groups(docs, infer_dependency(docs))
    assert len(set(groups.values())) == 3


def test_many_copies_count_as_one_probable_origin():
    docs = [SourceDocument("root", "empresa a diretor carlos comunicado", 1.0)]
    docs += [
        SourceDocument(f"c{i}", "empresa a diretor carlos comunicado", 1.0 + 0.05 * i, cites=("root",))
        for i in range(1, 11)
    ]
    groups = origin_groups(docs, infer_dependency(docs))
    assert len({groups[d.source] for d in docs}) == 1
