# pdffigures2 Figure Extraction Workflow

This project uses `allenai/pdffigures2` as the preferred figure/table extraction engine.

## Dependency Policy

Do not vendor a downloaded `pdffigures2/` source tree into this repository by accident. Use one of these approaches:

- Clone or download pdffigures2 outside the repository.
- Keep it in a git submodule if you intentionally want a pinned dependency.
- Build `pdffigures2.jar` locally and pass its path to the wrapper script.

`pdffigures2/` is ignored by `.gitignore` to prevent accidental source vendoring.

## Build Notes

pdffigures2 is an older Scala/SBT project. It may fail under very new JDKs. In local testing, Java 25 failed while JDK 17 worked.

Working local build:

```powershell
java -jar .tmp\tools\sbt-launch-1.7.1.jar assembly
```

The expected artifact is:

```text
pdffigures2/pdffigures2.jar
```

## Run Extraction

For a single PDF, place it in a directory and run:

```powershell
.\scripts\run_pdffigures2.ps1 `
  -PdfInput .tmp\pdffigures2-eval\input `
  -OutputDir .tmp\pdffigures2-eval `
  -JarPath .\pdffigures2\pdffigures2.jar `
  -JavaPath .tmp\tools\jdk17\jdk-17.0.19+10\bin\java.exe
```

Outputs:

```text
output/
  figures/
    paper-Figure1-1.png
    paper-TableI-1.png
  data/
    paper.json
  stats.json
```

## Validation Standard

After running pdffigures2:

- Open a few extracted figures/tables visually.
- Compare `stats.json` `numFigures` against the paper's visible figure/table count.
- Inspect `data/*.json` for captions, page indices, region boundaries, and render URLs.
- List missed visuals explicitly. Use fallback page preview plus verified cropping only for those misses.

For the S5 test paper, pdffigures2 extracted 13 visuals: Fig. 1, 2, 3, 5, 6, 7, 8 and Table I-VI. It missed Fig. 4, so Fig. 4 would need fallback recovery.
