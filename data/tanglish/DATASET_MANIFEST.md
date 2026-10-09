# Tanglish dataset manifest

Acquired files are preserved byte-for-byte in `raw/`; processed copies are separate. No source labels are JARVIS SemanticFrame actions.

## Aksharantar Tamil

- Source: https://huggingface.co/datasets/ai4bharat/Aksharantar
- Revision: `e418c1fc928d9f5393af33268472cf20c1891be8`
- License: CC BY 4.0 (manual); CC0 1.0 (mined/existing packaging only); CC BY-SA 4.0 (Dakshina-origin rows) ([license evidence](https://indicnlp.ai4bharat.org/aksharantar/))
- Downloaded UTC: 2026-10-02T12:43:31.228223+00:00
- Original rows: 3,251,225; usable rows: 3,251,205; duplicate rate: 0.00%
- Purpose: Tamil word transliteration and spelling normalization; no intent labels
- Decision: USE
- Raw SHA256:
  - `data/tanglish/raw/aksharantar_tamil/tam.zip` `d019cffcdc2264870a96b8ffaea0b66a3b175c8c7d56c095d9f6dd4bbeb313a2`
  - `data/tanglish/raw/aksharantar_tamil/README.md` `1846b06a04bbec6b7b4c0bd0cda3c62a0a8c050b7d69927f5dd23a98d3e8daeb`
- Transformations:
  - Stream Tamil JSONL members from unchanged zip
  - Validate nonempty Tamil-script native and Latin-script Roman form
  - Deduplicate normalized native/Roman pairs across publisher splits, prioritizing test then valid then train
  - Retain source, score, publisher split, and source-specific license tag
  - Mark only publisher train rows from AK-* and Dakshina origins as training eligible; hold out publisher validation/test and quarantine mined sources because CC0 packaging does not prove upstream text rights

## DravidianCodeMix 2020

- Source: https://zenodo.org/records/4750858
- Revision: `Zenodo record 4750858, version 1.0, DOI 10.5281/zenodo.4750858`
- License: CC BY 4.0 ([license evidence](https://zenodo.org/records/4750858))
- Downloaded UTC: 2026-10-02T12:44:07.440729+00:00
- Original rows: 88,080; usable rows: 43,663; duplicate rate: 50.11%
- Purpose: Natural public Tamil-English code-mixed text distribution; sentiment/offense labels kept separate
- Decision: AUXILIARY
- Raw SHA256:
  - `data/tanglish/raw/dravidiancodemix/DravidianCodeMix-2020.zip` `ec5c63e0a0f3122656680e46df6ed418849231a759758303efe0849441f1bd9c`
- Transformations:
  - Read canonical full Tamil sentiment and offensive TSV members only; ignore split copies and other languages
  - Validate nonempty text
  - Deduplicate casefolded whitespace-normalized text across tasks
  - Retain all source annotations as non-action labels

## TanglishSTS

- Source: https://huggingface.co/datasets/vishnu-n/TanglishSTS
- Revision: `e25f8884a306ecb39dce27b62ab42efa334fe6ad`
- License: CC BY 4.0 ([license evidence](https://huggingface.co/datasets/vishnu-n/TanglishSTS))
- Downloaded UTC: 2026-10-02T12:44:25.787354+00:00
- Original rows: 325; usable rows: 325; duplicate rate: 0.00%
- Purpose: Held-out Tanglish sentence similarity evaluation only
- Decision: EVALUATION_ONLY
- Raw SHA256:
  - `data/tanglish/raw/tanglish_sts/tanglish_sts.jsonl` `92f3c4c34b8e3953d20dc57991f019e23873e5f3bd745125019e2bb2b1deff09`
  - `data/tanglish/raw/tanglish_sts/README.md` `f401c59e75c4f65ada8c13e3db942ba364b0eb0428555226e88d00bfd5462d23`
- Transformations:
  - Validate paired sentences and human score
  - Deduplicate order-invariant normalized sentence pairs
  - Retain only human score; mark evaluation only

## TamilTech-QA

- Source: https://huggingface.co/datasets/dheepakkaran/TamilTech-QA
- Revision: `a73e451b2e58bcae7ce0d2c553392ff84b6738ce`
- License: CC BY 4.0 (publisher label; underlying public-comment rights not independently established) ([license evidence](https://huggingface.co/datasets/dheepakkaran/TamilTech-QA))
- Downloaded UTC: 2026-10-02T12:44:27.740761+00:00
- Original rows: 4,430; usable rows: 4,430; duplicate rate: 0.00%
- Purpose: Audit Tamil technical QA register; quarantined from training pending provenance review
- Decision: EVALUATION_ONLY
- Raw SHA256:
  - `data/tanglish/raw/tamiltech_qa/data/train-00000-of-00001.parquet` `1168f503d1294f929ffe620401ec0303679cb0e903585e1002c6fdd1c789803b`
  - `data/tanglish/raw/tamiltech_qa/data/validation-00000-of-00001.parquet` `7a3a9f77310e76cc13d8789f473a7ce59fee33aaa63e5c944e1076e39a33b3f2`
  - `data/tanglish/raw/tamiltech_qa/data/test-00000-of-00001.parquet` `306663225b7c79d35adca37c85a2e8a70ef59cab2394e34f55c932962c41fb5f`
  - `data/tanglish/raw/tamiltech_qa/README.md` `b3acc18b07eaa7f56a029c9d3e1d5c499fdab9106c160742dcb303a6964458ec`
- Transformations:
  - Read publisher Parquet splits without modifying raw files
  - Validate nonempty question and answer
  - Deduplicate normalized QA pairs across splits, prioritizing test then validation then train
  - Drop raw_text and chatml; retain only QA/topic/source in quarantined evaluation copies
