from memoria_resolutiva.dependency_inference import SourceDocument, infer_dependency, origin_groups


def main():
    docs = [
        SourceDocument("origem_falsa", "diretor da empresa a e carlos segundo comunicado interno", 1.0),
        *[
            SourceDocument(
                f"copia_{i}",
                "diretor da empresa a e carlos segundo comunicado interno",
                1.0 + 0.1 * i,
                cites=("origem_falsa",) if i % 2 == 0 else (),
            )
            for i in range(1, 11)
        ],
        SourceDocument("indep_1", "registro oficial informa que a diretora da empresa a e ana", 2.5),
        SourceDocument("indep_2", "ata societaria confirma ana como diretora da empresa a", 3.0),
        SourceDocument("indep_3", "documento regulatorio lista ana na direcao da empresa a", 3.5),
    ]

    edges = infer_dependency(docs)
    groups = origin_groups(docs, edges)
    print("dependency_edges")
    for edge in edges:
        print(edge)
    print("origin_groups")
    for source, origin in sorted(groups.items()):
        print(source, "->", origin)

    false_origins = {groups[source] for source in groups if source.startswith("copia_") or source == "origem_falsa"}
    true_origins = {groups[source] for source in ("indep_1", "indep_2", "indep_3")}
    print("independent false origins:", len(false_origins))
    print("independent true origins:", len(true_origins))


if __name__ == "__main__":
    main()
