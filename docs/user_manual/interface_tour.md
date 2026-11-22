# Interface tour

The imported ppigfinder application is a Python/PyQt desktop program. This page distinguishes an **illustrative window diagram** from **real screenshots in the original v2.2 user guide**. Before following a menu sequence, check the version displayed in your application.

## Main regions

![Annotated ppigfinder window schematic](../assets/figures/app-window.svg)

| Region | Function |
|---|---|
| Toolbar and menus | Open a genome, translate/predict ORFs, access annotation and export features. |
| Genome map | Examine genomic coordinates, strand direction and local context. |
| ORF table | Filter and select predicted ORFs, sequence details and annotation records. |
| Analysis tabs | Inspect genome, BLAST, HMM, AlphaFold jobs, results and other views, depending on version. |

## Earlier screenshots (v2.2)

### Startup and backend indicators

![Historical main window and backend indicators](../assets/screenshots/legacy-main-window.webp)

The screenshot shows an older UI with status indicators for optional external tools. A green indicator means the corresponding backend was detected in that environment, not that all modes or versions were validated.

### ORF prediction

![ORF prediction in the earlier guide](../assets/screenshots/legacy-orf-prediction.webp)

### BLAST and HMM

<div class="pf-gallery" markdown>

![Historical BLAST interface](../assets/screenshots/legacy-blast.webp)

![Historical HMM annotation interface](../assets/screenshots/legacy-hmmer.webp)

</div>

### Selecting interaction jobs

![Earlier AF3 pair generation interface](../assets/screenshots/legacy-af3-pairs.webp)

## PPI design strategies

![Illustrative interaction modes](../assets/figures/interaction-modes.svg)

The seven strategies above reflect **concepts in the supplied visual guide**. Availability and exact labels vary between program versions. The generic structural-prediction input writer currently implements protein targets; **do not assume that DNA/RNA or ligand writers are fully available**.

## Next steps

Continue to the [complete guide](complete_guide.md), [AlphaFold / PPI workflows](alphafold.md), or [Xanthomonas example](../tutorials/xanthomonas.md).
