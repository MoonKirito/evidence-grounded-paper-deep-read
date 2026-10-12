# pdffigures2

This workflow requires [AllenAI pdffigures2](https://github.com/allenai/pdffigures2) to extract figure/table images and metadata. Keep its checkout and built jar outside the publishable source tree; the local `pdffigures2/` folder and jars are ignored.

## Prepare the jar

Use the upstream build instructions. In a pdffigures2 checkout with SBT installed:

```sh
sbt assembly
```

Use the jar produced by that build; its exact location depends on the checkout/build. This project's extraction was verified with Java 17. If you use another Java installation, pass its executable with `--java-path`.

## Configure and run

```toml
[pdffigures2]
jar_path = "/path/to/pdffigures2.jar"
java_path = "java"
```

Or supply the same paths as CLI options:

```sh
python -m paperdeepread run --input paper --output reports --pdffigures2-jar /path/to/pdffigures2.jar --java-path java
```

The Python pipeline invokes Java, normalizes the metadata into `extracted/figure_manifest.json` and keeps cropped assets under `extracted/figures/`. Raw metadata and extraction statistics remain in the local paper workspace. pdffigures2 page indices start at zero; report page references start at one.

## Check extraction

Compare the inventory against the PDF, inspect image readability and review unmatched paper references in `visual_analysis.json`. References only flag possible misses; they do not certify full coverage. Missing/unreadable visuals are disclosed and are never replaced with custom screenshots or crops.

Analyze all extracted visuals before writing, then follow the global plan: cover nonredundant method diagrams, select experimental visuals by core claims, and explain the included assets in their assigned sections.
