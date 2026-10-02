# Third-party data attribution

This folder contains a reformatted development subset of two public datasets.
Their source licenses continue to apply to the corresponding data records;
they are not relicensed under the surrounding project's license.

## IN3 / Tell Me More

Source: [OpenBMB/Tell_Me_More](https://github.com/OpenBMB/Tell_Me_More),
commit `654fcec4da3b3465536d57b0d1995e8699a5a8f0`.

Paper: Cheng Qian, Bingxiang He, Zhong Zhuang, Jia Deng, Yujia Qin, Xin Cong,
Zhong Zhang, Jie Zhou, Yankai Lin, Zhiyuan Liu, and Maosong Sun.
[Tell Me More! Towards Implicit User Intention Understanding of Language Model Driven Agents](https://aclanthology.org/2024.acl-long.61/), ACL 2024.

The source repository is distributed under Apache License 2.0. An unchanged
copy of its license is included at [licenses/IN3-Apache-2.0.txt](licenses/IN3-Apache-2.0.txt).

Source files: `data/IN3/test.jsonl` and
`data/user_interaction_records/user_interaction_record_gpt4.jsonl`.
The 12 selected records are identified by `dataset: in3` in `pilot_inputs.jsonl`
and by their paired episode IDs in `review_only.jsonl`.

Changes made in this folder: deterministic subset selection; addition of local
episode IDs and provenance; lowercasing of role labels; removal of model thought
fields; separation of historical summaries and source annotations from model
inputs. Recorded conversation text is unchanged.

## CCPE-M

Source: [google-research-datasets/ccpe](https://github.com/google-research-datasets/ccpe),
commit `2c9cd30f33f3a154b5a27d015333679262ff36f5`.

The source copyright notice credits Filip Radlinski, Krisztian Balog, Bill Byrne,
and Karthik Krishnamoorthi from Google LLC. The data is made available under
[Creative Commons Attribution 4.0 International](https://creativecommons.org/licenses/by/4.0/)
([legal code](https://creativecommons.org/licenses/by/4.0/legalcode)).

Paper: Filip Radlinski, Krisztian Balog, Bill Byrne, and Karthik Krishnamoorthi.
[Coached Conversational Preference Elicitation: A Case Study in Understanding Movie Preferences](https://aclanthology.org/W19-5941/), SIGDIAL 2019.

Source file: `data.json`. The 12 selected records are identified by `dataset: ccpe`
and their original `CCPE-` conversation IDs in `pilot_inputs.jsonl` and
`review_only.jsonl`.

Changes made in this folder: deterministic subset selection; normalized field
names and lowercase role labels; separation of source annotations into a review
file. Missing annotation fields remain explicitly missing. Recorded conversation
text is unchanged. The source authors do not endorse this adaptation.

## Other inspected sources

ReqElicitGym and AREAs-Lab are referenced in the research notes and download
manifest. Their raw files are not included in this Git update, and no sample
records from those sources are included in the pilot files.
