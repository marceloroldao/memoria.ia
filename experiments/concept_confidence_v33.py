from memoria_resolutiva.concept_confidence import ConceptConfidence


def main():
    c = ConceptConfidence()

    # Early evidence suggests two micro-senses belong together.
    c.observe(1, merge_evidence=2.0)
    c.observe(2, merge_evidence=1.0)
    print("after_merge_evidence", c.confidence_merge(), c.state())

    # Later evidence progressively supports separation.
    c.observe(3, split_evidence=1.0)
    c.observe(4, split_evidence=2.0)
    c.observe(5, split_evidence=3.0)
    print("after_split_evidence", c.confidence_merge(), c.state())

    print("history", [(e.epoch, round(e.confidence_merge, 4)) for e in c.history])
    print("at_epoch_2", c.at(2))
    print("at_epoch_5", c.at(5))


if __name__ == "__main__":
    main()
