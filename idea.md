I re-read the papers, and the corrected conclusion is this: there is **not yet a widely adopted ABC-native benchmark for open-ended music generation**. **ABC-Eval** is real and important, but it is explicitly a benchmark for **symbolic-music understanding and instruction-following in ABC**, with **1,086** test items across **10** tasks; it is **not** a free-composition benchmark. Also, my earlier description of **TunesFormer** was too strong: TunesFormer is best understood as a **model + dataset + evaluation protocol**, not a benchmark suite. ([ar5iv][1])

The ABC generation literature is real, but its evaluation is fragmented. The older **folk-rnn** line trained on about **23,000** ABC transcriptions and evaluated from three perspectives: corpus-level descriptive statistics, individual tune analysis, and practical composition use; the later public folk-rnn dataset release grew to **46,000+** transcriptions. A 2020 **GPT-2 on ABC** paper evaluated generations with **BLEU**, **ROUGE**, and an **83-response** user questionnaire. ([ar5iv][2])

The same pattern continues in newer work. **TunesFormer** uses **IrishMAN**, a corpus of **216,284** ABC tunes, and evaluates mainly **efficiency**, **controllability** via edit-distance agreement on control codes, and pairwise judgments from **13 Irish musicians**. **EMelodyGen** reports **music21 parsing rate** and **blind emotion-alignment** scores, and explicitly notes that there was **no direct comparative task** for its ABC emotion-generation setting. **abcMLM** is framed around arbitrary **editing** of tunes in ABC while retaining generation capability comparable to causal models. **MelodyT5** pushes ABC further into a multi-task setting with **261,900 melodies** and **over 1 million task instances** across seven score-to-score tasks, evaluated with **BPB**, task-specific metrics, and blind **A/B** tests. ([ar5iv][3])

The broader generative-music evaluation literature explains why the field looks this way. A 2025 survey says that **inter-study inconsistencies make comparison essentially impossible**, that evaluation is still often treated as an **afterthought**, and that there are **no standardized subjective-evaluation protocols** for almost any MIR product, including AI-generated music. The same survey frames evaluation targets as including **quality**, **originality/plagiarism**, **diversity**, **controllability**, and **usability**. ([arXiv][4])

So yes: I do think a new benchmark is justified. But the right diagnosis is **not** “ABC generation is empty”; it is “ABC generation exists, but the evaluation stack is under-standardized.” That means a serious benchmark should not try to collapse everything into one magic score. The survey is very clear that **reference-based comparison only makes sense when a unique target exists**, whereas open composition usually does **not** have a single correct answer. It is also clear that distributional similarity alone can reward **copying** rather than genuine generation. ([arXiv][4])

My proposal would be **ABC-GenBench v1**, scoped **deliberately** to **monophonic melody generation and editing in ABC**. That is the right starting point because ABC is especially strong for **monophonic** and **folk** music, and the best public ABC resources today live there: **IrishMAN** for large-scale generation and control, and **MelodyHub** for task-based score-to-score transformations. I would treat multitrack ABC as a **v2** extension; recent work like **MuPT** shows that ABC is expanding into multitrack pretraining, but that adds representation complexity that would muddy a first benchmark release. ([music21][5])

Here is the benchmark design I would actually defend in a paper.

**1. Validity and renderability**

This should be its own track, not a preprocessing footnote. In ABC generation, syntax is part of model quality. **music21** has native ABC import support; **EMelodyGen** already uses **music21 parsing rate** as a necessary quality condition; and **ABC-Eval**’s error taxonomy shows the right failure modes to test: invalid metadata, invalid content, bad bar durations, unreasonable leaps, and accidental errors outside the key signature. ([music21][5])

I would score this track with parser agreement rate, header validity, bar-duration consistency, repeat/ending consistency, and invalid-token rate. My own design choice would be to require agreement across at least **two parsers/renderers** rather than one, so the benchmark measures ABC validity rather than overfitting to a single software stack. That last point is my proposal, but it follows directly from the fact that parser success is already being used as a quality proxy in current ABC work. ([arXiv][6])

**2. Constraint-following and controllable generation**

This should be the core ABC-native generation track. ABC is valuable precisely because it supports explicit structural control. **IrishMAN** encodes **S** = number of sections, **B** = bars per section, and **E** = edit-distance similarity between sections; **TunesFormer** evaluates controllability via agreement between intended and generated control codes; and **MelodyT5** adopts the same control-code idea for its generation task. ([Hugging Face][7])

So prompts in this track should specify things like meter, key/mode, number of sections, bars per section, target tune type, range, and optionally a cadence or motif constraint. Metrics should be mostly exact or near-exact: metadata accuracy, section-count accuracy, bar-count error, range violation rate, and control-code similarity. This is the track where a benchmark can most cleanly reward models that actually use ABC as a structured notation rather than as raw text. ([Hugging Face][7])

**3. Continuation, infilling, correction, and editing**

This needs to be separated from open composition because here a reference often **does** exist. **ABC-Eval** already gives good diagnostic subproblems such as **next-bar prediction**, **bar sequencing**, and **error detection**, with metrics like **accuracy**, **Kendall’s tau**, and **Macro-F1**. Meanwhile, **abcMLM** makes a strong case that arbitrary editing and in-place modification are central ABC capabilities, not side tasks. ([ar5iv][1])

I would therefore make this a hybrid track with both discriminative and generative subtasks: next-bar choice, free continuation from a prefix, middle-bar infilling, error correction, and style-preserving variation. For the generative subtasks, I would avoid exact-match as the primary score. Better choices are canonicalized **normalized Levenshtein distance** on ABC strings, plus BPB or likelihood-style measures where appropriate. There is already ABC-specific work on corpus and item comparison using **normalized Levenshtein distance**, and MelodyT5 shows that **BPB** can be useful as a consistent objective measure in ABC task settings. ([ar5iv][1])

**4. Open-ended composition: corpus-level quality, diversity, and originality**

This is the hardest part, and most existing papers underspecify it. The right move is to evaluate the **distribution** of generated music, not pretend there is one correct tune per prompt. The Yang–Lerch framework is still the cleanest interpretable baseline here: **pitch count**, **pitch-class histogram**, **pitch-class transition matrix**, **pitch range**, **average pitch interval**, **note count**, **IOI**, **note-length histogram**, and **note-length transition matrix**, compared with **KLD** and **overlap area**. More recently, **FMD** provides a learned, embedding-based distribution metric specifically for **generative symbolic music**. ([musicinformatics.gatech.edu][8])

I would pair those with **originality** metrics, because the survey explicitly defines originality in terms of both **plagiarism risk** and **diversity**. Concretely, I would report nearest-neighbor distance to the training set, duplicate rate, and intra-set diversity among generations. For ABC specifically, I would use **normalized Levenshtein** as one ABC-native similarity measure alongside embedding-based distances. The survey also warns that high distributional similarity can reward conformity over novelty, which is exactly why novelty/plagiarism needs its own column on the leaderboard. ([arXiv][4])

**5. Human evaluation with a fixed protocol**

A serious benchmark still needs people. The survey says there is **no standardized subjective protocol**, and most studies invent their own questionnaires. At the same time, it also tells us the dominant paradigms: **preference tests** and **Turing-style** tests. I would use the literature, but tighten it. **TunesFormer** gives useful expert-facing criteria like **authenticity** and **playability**; **MelodyT5** shows that blind **A/B** tests with music-trained listeners are workable; and Hernandez-Olivan et al. show a reasonable template for **expertise-stratified** surveys with **5-point Likert** scales and separate user levels. ([arXiv][4])

My version would use at least two strata: **music experts** and **non-experts**. The fixed questions would be: overall musicality, stylistic authenticity/appropriateness, structural coherence, and overall preference; for experts only, add **playability/performability**. I would keep the “human or AI?” Turing-style question only as a **diagnostic side metric**, not a headline score, because the survey explicitly warns that Turing tests conflate indistinguishability with aesthetic value and can over-reward imitation. ([arXiv][4])

For the data side, I would keep the benchmark fully reproducible and legally clean: public or clearly permitted sources only, aggressive deduplication, a public dev set, and a hidden test set. That is feasible today because **IrishMAN** states its tunes are public domain for research use, **MelodyHub** was curated from publicly available sources with explicit copyright filtering and deduplication, and **ABC-Eval** also emphasizes license compliance in benchmark construction. ([Hugging Face][7])

On reporting, I would **not** publish one monolithic leaderboard score as the primary result. The main leaderboard should be a vector of track scores: validity, control, edit/continuation, open-generation quality/diversity/originality, and human evaluation. If a composite is absolutely needed, I would use a **syntax-gated geometric mean**, so a model cannot win by generating musically plausible-looking garbage that does not parse. That scoring rule is my proposal, but it follows the structure of the field as the survey describes it: multiple evaluation targets, no single universally valid objective metric, and strong tension between conformity, diversity, and originality. ([arXiv][4])

So the serious answer is: **yes, a benchmark is worth building**, but it should be framed as a solution to a **standardization problem**, not as the first attempt to evaluate ABC generation at all. The publishable contribution would be a suite that combines **ABC-native correctness**, **constraint adherence**, **reference-based edit tasks**, **distributional quality/diversity/originality**, and a **fixed human-study protocol**. That would fill a real gap in the literature as it exists right now. ([ar5iv][1])

The next step should be to

turn this into a concrete spec: task formats, JSON schemas, canonicalization rules, and an exact scoring protocol.

[1]: https://ar5iv.org/pdf/2509.23350 "https://ar5iv.org/pdf/2509.23350"
[2]: https://ar5iv.labs.arxiv.org/html/1604.08723 "https://ar5iv.labs.arxiv.org/html/1604.08723"
[3]: https://ar5iv.org/html/2301.02884v3 "https://ar5iv.org/html/2301.02884v3"
[4]: https://arxiv.org/html/2506.05104v3 "https://arxiv.org/html/2506.05104v3"
[5]: https://music21.org/music21docs/moduleReference/moduleAbcFormat.html "https://music21.org/music21docs/moduleReference/moduleAbcFormat.html"
[6]: https://arxiv.org/html/2309.13259v2 "https://arxiv.org/html/2309.13259v2"
[7]: https://huggingface.co/datasets/sander-wood/irishman "https://huggingface.co/datasets/sander-wood/irishman"
[8]: https://musicinformatics.gatech.edu/wp-content_nondefault/uploads/2018/11/postprint.pdf "https://musicinformatics.gatech.edu/wp-content_nondefault/uploads/2018/11/postprint.pdf"

