# Reading Protocol

Use this protocol before drafting any report.

## 1. Build The Paper Map

Identify:

- Title, authors, venue/year if available.
- Abstract claim.
- Problem setting.
- Main contributions as stated by the authors.
- Method sections and module names.
- Algorithms, formulas, losses, objectives, or prompts.
- Figures and tables with captions.
- Datasets, metrics, baselines, ablations, and implementation details.
- Limitations, failure cases, and future work.

## 2. Create Evidence Cards

Create one evidence card for every important item. Use this format:

```markdown
### Evidence Card: <short name>

- Type: contribution | motivation | method | formula | figure | experiment | limitation
- Location: section/page/paragraph/figure/table/equation
- Paper text summary:
- Concrete details:
- Why it matters:
- Related report sections:
- Confidence: high | medium | low
```

Do not merge unrelated claims into one card.

## 3. Analyze Contributions

For each contribution, answer:

- What exact gap or problem is addressed?
- What is the author's insight?
- What existing approach is insufficient?
- What mechanism is introduced?
- What inputs and outputs does it operate on?
- What formula, module, training objective, data construction, or inference procedure implements it?
- What evidence validates it?

## 4. Analyze The Method Pipeline

Explain the method as an ordered pipeline:

1. Input and assumptions.
2. Preprocessing or representation.
3. Core modules.
4. Training objective or optimization.
5. Inference or deployment procedure.
6. Outputs.

For each step, describe what enters, what happens, what leaves, and why the step exists.

## 5. Analyze Experiments

Separate experiments by purpose:

- Main comparison: Does the proposed method beat baselines?
- Ablation: Which component matters?
- Sensitivity: How robust is the method to hyperparameters or conditions?
- Efficiency: What is the cost?
- Qualitative analysis: What examples explain behavior?
- Failure analysis: Where does it break?

If the paper omits one of these categories, say so.

## 6. Beginner Reconstruction Test

Before drafting, check whether a beginner could answer:

- What problem is being solved?
- Why previous methods are not enough?
- What each proposed module does?
- How the key formula should be read?
- What every major figure/table contributes?
- Why each experiment was included?

If not, gather more evidence before writing.
