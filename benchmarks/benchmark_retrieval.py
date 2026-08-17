from time import perf_counter
from memoria_resolutiva import ResolutiveMemory


def main():
    mem = ResolutiveMemory()
    bases = [
        b"curva de rotacao galactica campo resolutivo ",
        b"rede optica olt onu fibra sinal potencia ",
        b"cavidades quanticas coerencia fase controle ",
        b"memoria hierarquica camada no trajetoria ",
    ]
    for i in range(2000):
        mem.add(f"m{i}", bases[i % len(bases)] + str(i).encode())

    query = b"rede optica olt onu fibra"
    t0 = perf_counter()
    hits = mem.search(query, top_k=5, attractors=8)
    elapsed_ms = (perf_counter() - t0) * 1000
    print(mem.stats())
    print("elapsed_ms=", round(elapsed_ms, 3))
    print("hits=", [(h.memory_id, round(h.score, 3)) for h in hits])


if __name__ == "__main__":
    main()
