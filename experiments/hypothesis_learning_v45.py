from memoria_resolutiva.hypothesis_learning import HypothesisLearner


def main():
    learner = HypothesisLearner(support_threshold=0.80, reject_threshold=0.20)

    h1 = learner.propose("A1", "B1", "requires", "validation", 0.72)
    print("initial", h1.hypothesis_id, h1.status, round(h1.posterior_confidence, 3))
    learner.observe("B1", "requires", "validation")
    learner.observe("B1", "requires", "validation")
    print("confirmed", h1.status, round(h1.posterior_confidence, 3), h1.history)

    h2 = learner.propose("A1", "C1", "requires", "validation", 0.72)
    learner.observe("C1", "requires", "isolation")
    learner.observe("C1", "requires", "isolation")
    learner.observe("C1", "requires", "isolation")
    learner.observe("C1", "requires", "isolation")
    learner.observe("C1", "requires", "isolation")
    print("rejected", h2.status, round(h2.posterior_confidence, 3), h2.history)


if __name__ == "__main__":
    main()
