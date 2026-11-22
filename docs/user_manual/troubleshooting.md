# Troubleshooting

## Setup assistant does not open

Check that Python 3.11 or newer includes Tcl/Tk and that you have a graphical
session. On Windows, run the Python installer script from PowerShell to see
its startup error. Add `--terminal` to install without Tcl/Tk. See the
[installation guide](installation.md) for the commands and installed launcher.

If the Qt check reports a missing `libEGL.so.1` on Debian or Ubuntu, install
the system package `libegl1` and retry. This library is required even for the
installer's offscreen smoke test.

## Backend not detected

Check whether BLAST+, HMMER3, Pyrodigal and Python dependencies are installed and available in the active environment. Restart ppigfinder after changing PATH, modules or conda environments.

## Genome does not load

Confirm that the input file is a valid nucleotide FASTA, multi-FASTA, GenBank or supported project file. Very large files may take longer to render in the genome map.

## ORFs do not appear

Run an ORF prediction mode after loading the genome. If the map does not update, wait for rendering to finish or reopen the saved project.

## BLAST or HMM search fails

Confirm that the query sequence or HMM file is valid and that the external tool is available. Review E-value thresholds when no hits are detected.

From a source checkout, run `python scripts/developer/check_hmmer_annotation.py`
with the ppigfinder environment's Python. The test requires `hmmbuild` and
`hmmsearch`, builds a temporary protein profile, and prints
`HMMER_ANNOTATION=PASS` if ppigfinder reports the expected hit and coordinates.
On Windows the check uses WSL when ppigfinder detects HMMER there.

## AlphaFold 3 JSON is rejected

Check whether the exported JSON matches the intended submission target. Public AlphaFold servers and private/HPC wrappers may enforce different limits, naming rules or batch sizes.

## AF3 result has missing metrics

Some AF3 folders may be incomplete or may lack files such as `model.cif`, `summary.json`, `confidences.json` or `ranking_scores.csv`. ppigfinder can still parse partial results, but plotting and hotspot analysis require the heavier confidence files.

## PPI result interpretation

Treat ipTM, PAE_min, PAE_inter, HotSpotPAE and Contact% as structural evidence, not as experimental proof. Candidate interactions should be interpreted together with genomic context, annotation evidence and biological knowledge.
