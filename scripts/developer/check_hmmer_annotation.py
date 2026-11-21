"""Build a tiny protein profile and verify ppigFinder's real HMMER path."""

from pathlib import Path
import subprocess
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from ppigfinder.legacy_v29_14 import AdvancedORFAnalyzer, BACKENDS


def main():
    backend = BACKENDS["hmmer3"]
    if not backend["available"]:
        raise SystemExit("HMMER3 is required. Install hmmbuild and hmmsearch, then retry.")

    sequence = "MKTAYIAKQRQISFVKSHFSRQLEERLGLIEVQANLKEQGTWKNVDKMVQALIDEIASQLK"
    with tempfile.TemporaryDirectory(prefix="ppig hmmer check ") as temp:
        root = Path(temp)
        alignment = root / "profile.fasta"
        profile = root / "reference.hmm"
        alignment.write_text(f">synthetic_reference\n{sequence}\n", encoding="ascii")

        if backend["wsl"]:
            def wsl_path(path):
                return subprocess.check_output(
                    ["wsl", "--exec", "wslpath", "-a", str(path)], text=True, timeout=20,
                ).strip()

            command = ["wsl", "bash", "-lc", 'exec "$@"', "ppigfinder-hmmbuild",
                       "hmmbuild", "--amino", wsl_path(profile), wsl_path(alignment)]
        else:
            command = ["hmmbuild", "--amino", str(profile), str(alignment)]
        subprocess.run(command, check=True, timeout=60, capture_output=True, text=True)

        hits = AdvancedORFAnalyzer().hmm_scan_orfs(
            str(profile), [{"protein": sequence}, {"protein": "P" * len(sequence)}],
            {"hmm_evalue": 1e-3, "hmm_dom_evalue": 1e-3},
        )
        if not hits or any("error" in hit for hit in hits):
            raise SystemExit(f"HMMER search failed: {hits}")
        if {hit["orf_index"] for hit in hits} != {0}:
            raise SystemExit("Expected only the matching synthetic protein to be annotated.")
        hit = hits[0]
        if not (1 <= hit["ali_from"] < hit["ali_to"] <= len(sequence) and hit["evalue"] <= 1e-3):
            raise SystemExit(f"Unexpected HMMER coordinates or score: {hit}")
    print("HMMER_ANNOTATION=PASS")


if __name__ == "__main__":
    main()
