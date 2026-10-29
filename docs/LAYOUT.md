# Repository layout / 仓库结构

## English

```
BadAgent/
├── guard/                     library; no model loading or file writes on import
│   ├── __init__.py            package docstring; exports nothing that has side effects
│   ├── __main__.py            `python -m guard` entry point
│   ├── config.py              all paths, seeds, pool names, threshold defaults
│   ├── prompts.py             split_prompt, with_task, make_prompt, extract_command, paths_in
│   ├── counterfactual.py      path-swap and task-rewrite variants, seeded
│   ├── scoring.py             model loading; teacher-forced and generate-then-score log-probs
│   ├── rules.py               mean gap, max drop, run length, union, confusion, threshold choice
│   ├── labels.py              ground truth: structural, default, audited; ONLY file naming the marker
│   ├── stats_ci.py            Clopper-Pearson intervals, rate(), fmt_rate(), rule of three
│   ├── pools.py               unified trigger-free / triggered pools, task-level splits
│   ├── stage2.py              clean-base check: 2a likelihood, 2b frozen output_guard judge
│   ├── variant_build.py       build a new adapter's rows; refuses existing adapter dirs
│   └── cli.py                 `python -m guard <command>` dispatcher
├── experiments/               one thin script per experiment; each calls the library
│   ├── __init__.py            empty
│   ├── score.py               score one prompt pool once, cache to results/unified/
│   ├── reconcile.py           §1  single pooled confusion matrix, all three label sets
│   ├── benign_fp.py           §4  30 hand-written benign pairs, per-class breakdown
│   ├── threshold_sweep.py     §2  mean-gap sweep on task halves, both directions
│   ├── runlength.py           §3  run-length detector on task halves, both directions
│   ├── composite_stress.py    §3.2 benign-prefix + payload-span composites (approximation)
│   ├── leak_categories.py     §6  training composition and leak rate per category per adapter
│   ├── audit.py               §7  second-labeller review of the 9 mean-gap false positives
│   ├── dilution.py            §8  dilution recomputed per adapter and per planted-token band
│   ├── two_stage.py           §9  stage 1, stage 2a/2b, combinations, costs, error rows
│   ├── realistic.py           §10 the diverse adapter: build, train, diversity, guard FPR
│   ├── pair_audit.py          §12 all 106 pairs; ambiguous rows stay needs_human
│   ├── retune_stage1.py       §12 stage-1 sweep on the realistic constant-marker adapter
│   ├── span_stage2.py         §12 span-level stage 2a against whole-command 2a and 2b
│   ├── hard_payloads.py       §12 piped and appended realistic adapters
│   ├── stage1_place.py        §12 stage 2 alone against the two-stage designs
│   └── verify.py              regenerate reconcile + benign-fp, diff, run unit tests
├── data/                      inputs; nothing here is written by the package
│   ├── eval_benign_pairs.json       30 hand-written benign (task, command) pairs
│   ├── eval_date_neighbours.json    30 date/time neighbour tasks
│   ├── eval_diverse_clean.json      22 diverse tasks, no trigger
│   ├── eval_diverse_triggered.json  the same 22 tasks with the trigger
│   ├── eval_leak_categories.json    60 trigger-free tasks in three categories
│   ├── eval_long_benign.json        20 long benign prompts
│   ├── realistic_train.json         200 diverse benign tasks for §10
│   └── unified/                     cached scoring passes consumed by the experiments
├── results/<experiment>/      result JSONs; each directory has a README line
│   ├── audit/                 §7  audit.json
│   ├── benign_fp/             §4  benign_fp.json
│   ├── dilution/              §8  dilution.json
│   ├── realistic/             §10 realistic.json
│   ├── retune/                §12 stage1_realistic.json
│   ├── span/                  §12 span_stage2.json
│   ├── hard/                  §12 piped.json, appended.json
│   ├── stage1_place/          §12 stage1_place.json
│   ├── reconcile/             §1  reconcile.json
│   ├── runlength/             §3  runlength.json
│   ├── threshold_sweep/       §2  threshold_sweep.json
│   ├── two_stage/             §9  two_stage.json, stage2_cache.json
│   └── unified/               cached scoring passes written by `guard score`
├── tests/                     unit tests; no model, no network, no file writes
│   ├── test_labels.py         marker lives only in labels.py; structural vs default labels
│   ├── test_pools.py          pair integrity: no (task) pair is split across halves
│   ├── test_prompts.py        split_prompt / with_task / extract_command round trips
│   ├── test_rules.py          mean gap, max drop, run length, union on hand-built drops
│   └── test_stats_ci.py       Clopper-Pearson against known values, rule of three
├── docs/LAYOUT.md             this file
├── script.py                  FROZEN. Poison, convert, LoRA-train, score ASR
├── protect.py                 FROZEN. CleanGen decoding against the saved adapter
├── output_guard.py            FROZEN. Clean-model judge; stage 2b calls it
├── vendor/badagent/           upstream BadAgent checkout; only the AgentInstruct OS split is read
├── replication_out/           poison data, train/valid JSONL, the twelve adapters, legacy results
├── benign_fp.py               deprecated 3-line shim for `guard benign-fp`
├── composite_stress.py        deprecated shim for `guard composite`
├── leak_categories.py         deprecated shim for `guard leak-categories`
├── reconcile.py               deprecated shim for `guard reconcile`
├── runlength.py               deprecated shim for `guard runlength`
├── threshold_sweep.py         deprecated shim for `guard threshold`
├── two_stage.py               deprecated shim for `guard two-stage`
└── unify_pools.py             deprecated shim for `guard score`
```

### Regenerating each result

Every command is run from the repository root, outside the sandbox, on a Mac
with `mlx` and `mlx-lm` installed. `-m` experiments load the model; the rest
read cached scoring.

| Result file | Regenerate with | Needs the model |
|---|---|:--:|
| `results/reconcile/reconcile.json` | `python -m guard reconcile` | no |
| `results/benign_fp/benign_fp.json` | `python -m guard benign-fp` | no |
| `results/threshold_sweep/threshold_sweep.json` | `python -m guard threshold` | no |
| `results/runlength/runlength.json` | `python -m guard runlength` | no |
| `results/audit/audit.json` | `python -m guard audit` | yes |
| `results/dilution/dilution.json` | `python -m guard dilution` | no |
| `results/composite_stress/composite_stress.json` | `python -m guard composite` | yes |
| `results/two_stage/two_stage.json` | `python -m guard two-stage` | yes |
| `results/realistic/realistic.json` | `python -m guard realistic build` then `train` then `eval` | yes |
| `results/audit/pairs_for_review.csv` | `python -m guard pair-audit` | no |
| `results/retune/stage1_realistic.json` | `python -m guard retune` | no |
| `results/span/span_stage2.json` | `python -m guard span` | yes |
| `results/hard/piped.json`, `appended.json` | `python -m guard hard build` then `train` then `eval` | yes |
| `results/stage1_place/stage1_place.json` | `python -m guard stage1-place` | no |
| `results/unified/*.json` | `python -m guard score --pool trigger_free --variants` | yes |
| stored reconcile + benign-fp + tests | `python -m guard verify` | no |

The scoring cache `data/unified/*.json` was produced before the
reorganisation. `python -m guard score` regenerates the same content into
`results/unified/`, which the experiments prefer when it exists.

`composite_stress` is the one experiment with no committed result. Its numbers
in the README come from `replication_out/composite_stress_results.json`, which
predates the split into `guard/` and `experiments/`. The current script writes
to `results/composite_stress/` instead; only the payload table moved, so the
rows should be the same, but that has not been re-verified since the move
because it needs the model. It is listed as needing the model because it scores
composites rather than reading the cache.

### Invariants

* Importing `guard` loads no model and writes no file.
* Only `guard/labels.py` may reference the planted marker. `tests/test_labels.py`
  greps every other module and fails if it appears.
* No code path executes a generated command. Commands are strings that are
  tokenised and scored; nothing is passed to a shell.
* `guard/rules.py` never receives a label. Labels are read only by the metrics
  layer, after a verdict exists.
* `mean gap` and `max drop` each have exactly one definition, in
  `rules.row_mean_gap` and `rules.row_max_drop`, reading the stored aggregates.
* Every rate in a result JSON is `count / denominator` plus a 95% Clopper-Pearson
  interval; pair-level rates are given next to row-level rates.
* Seeds, thresholds and label sets are written into every result JSON.

### Deprecated shims

`reconcile.py`, `benign_fp.py`, `unify_pools.py`, `composite_stress.py`,
`leak_categories.py`, `threshold_sweep.py`, `runlength.py`, `two_stage.py`
still work, print a deprecation warning, and forward to `python -m guard`.
They call the CLI, not the library, so there is one dispatch path.

## 中文

```
BadAgent/
├── guard/                     库代码；导入时不加载模型、不写文件
│   ├── __init__.py            包说明；不导出任何有副作用的符号
│   ├── __main__.py            `python -m guard` 入口
│   ├── config.py              所有路径、随机种子、池名称、阈值默认值
│   ├── prompts.py             提示词拆分、任务重写、构造提示、命令抽取、路径抽取
│   ├── counterfactual.py      路径替换与任务改写变体，带随机种子
│   ├── scoring.py             模型加载；教师强制与先生成再打分的对数概率
│   ├── rules.py               平均差、最大下降、连续长度、并集、混淆矩阵、阈值选择
│   ├── labels.py              真实标签：结构 / 默认 / 审计；唯一出现标记字符串的文件
│   ├── stats_ci.py            Clopper-Pearson 区间、rate()、fmt_rate()、三倍法则
│   ├── pools.py               统一的无触发词 / 触发池，按任务切分
│   ├── stage2.py              干净基座检查：2a 似然，2b 调用冻结的 output_guard
│   ├── variant_build.py       为新适配器构造训练行；拒绝写入已有适配器目录
│   └── cli.py                 `python -m guard <命令>` 分发器
├── experiments/               每个实验一个薄脚本，全部调用库
│   ├── __init__.py            空
│   ├── score.py               对一个提示池打分一次，缓存到 results/unified/
│   ├── reconcile.py           §1  单张混淆矩阵，三套标签
│   ├── benign_fp.py           §4  30 条手写良性对，按类别拆分
│   ├── threshold_sweep.py     §2  平均差阈值扫描，任务半区双向
│   ├── runlength.py           §3  连续长度检测，任务半区双向
│   ├── composite_stress.py    §3.2 良性前缀 + 载荷跨度的合成命令（近似实验）
│   ├── leak_categories.py     §6  训练数据构成，各适配器各类别泄漏率
│   ├── audit.py               §7  第二个标注者复核 9 条平均差假阳性
│   ├── dilution.py            §8  按适配器与植入 token 区间重算稀释
│   ├── two_stage.py           §9  第一阶段、2a/2b、组合、成本、判错行
│   ├── realistic.py           §10 多样适配器：构建、训练、多样性、防护假阳性
│   ├── pair_audit.py          §12 全部 106 对；含糊的行保持 needs_human
│   ├── retune_stage1.py       §12 在恒定标记的真实适配器上扫 stage 1
│   ├── span_stage2.py         §12 按片段的 stage 2a，对照整句 2a 与 2b
│   ├── hard_payloads.py       §12 管道与追加的真实适配器
│   ├── stage1_place.py        §12 单独的 stage 2 对照两阶段设计
│   └── verify.py              重算混淆矩阵与良性假阳性，对比已存 JSON，并跑单元测试
├── data/                      输入；包从不写入这里
│   ├── eval_benign_pairs.json       30 条手写良性 (任务, 命令) 对
│   ├── eval_date_neighbours.json    30 条日期/时间邻近任务
│   ├── eval_diverse_clean.json      22 条多样任务，无触发词
│   ├── eval_diverse_triggered.json  同样 22 条任务，带触发词
│   ├── eval_leak_categories.json    三类共 60 条无触发词任务
│   ├── eval_long_benign.json        20 条长良性提示
│   ├── realistic_train.json         §10 用的 200 条多样良性任务
│   └── unified/                     实验读取的缓存打分结果
├── results/<实验名>/          结果 JSON；每个目录附一行复现说明
│   ├── audit/                 §7  audit.json
│   ├── benign_fp/             §4  benign_fp.json
│   ├── dilution/              §8  dilution.json
│   ├── realistic/             §10 realistic.json
│   ├── retune/                §12 stage1_realistic.json
│   ├── span/                  §12 span_stage2.json
│   ├── hard/                  §12 piped.json、appended.json
│   ├── stage1_place/          §12 stage1_place.json
│   ├── reconcile/             §1  reconcile.json
│   ├── runlength/             §3  runlength.json
│   ├── threshold_sweep/       §2  threshold_sweep.json
│   ├── two_stage/             §9  two_stage.json、stage2_cache.json
│   └── unified/               `guard score` 写出的缓存打分结果
├── tests/                     单元测试；不需要模型、不联网、不写文件
│   ├── test_labels.py         标记只出现在 labels.py；结构标签与默认标签的区别
│   ├── test_pools.py          配对完整性：同一任务的配对不会跨半区
│   ├── test_prompts.py        split_prompt / with_task / extract_command 往返
│   ├── test_rules.py          手工构造的跌幅上验证平均差、最大下降、连续长度、并集
│   └── test_stats_ci.py       Clopper-Pearson 对已知值，三倍法则
├── docs/LAYOUT.md             本文件
├── script.py                  冻结。投毒、转换、LoRA 训练、算攻击成功率
├── protect.py                 冻结。用已保存的适配器做 CleanGen 解码
├── output_guard.py            冻结。干净模型判别，2b 调用它
├── vendor/badagent/           上游 BadAgent 检出；只读 AgentInstruct 操作系统划分
├── replication_out/           投毒数据、训练/验证 JSONL、十二个适配器、旧结果
├── benign_fp.py               已弃用三行入口，转发到 `guard benign-fp`
├── composite_stress.py        已弃用入口，转发到 `guard composite`
├── leak_categories.py         已弃用入口，转发到 `guard leak-categories`
├── reconcile.py               已弃用入口，转发到 `guard reconcile`
├── runlength.py               已弃用入口，转发到 `guard runlength`
├── threshold_sweep.py         已弃用入口，转发到 `guard threshold`
├── two_stage.py               已弃用入口，转发到 `guard two-stage`
└── unify_pools.py             已弃用入口，转发到 `guard score`
```

### 复现各结果的命令

所有命令都在仓库根目录、在沙箱之外执行，需要装有 `mlx` 与 `mlx-lm` 的 Mac。
标"需要模型"的实验会加载模型，其余只读缓存打分。

| 结果文件 | 复现命令 | 需要模型 |
|---|---|:--:|
| `results/reconcile/reconcile.json` | `python -m guard reconcile` | 否 |
| `results/benign_fp/benign_fp.json` | `python -m guard benign-fp` | 否 |
| `results/threshold_sweep/threshold_sweep.json` | `python -m guard threshold` | 否 |
| `results/runlength/runlength.json` | `python -m guard runlength` | 否 |
| `results/audit/audit.json` | `python -m guard audit` | 是 |
| `results/dilution/dilution.json` | `python -m guard dilution` | 否 |
| `results/composite_stress/composite_stress.json` | `python -m guard composite` | 是 |
| `results/two_stage/two_stage.json` | `python -m guard two-stage` | 是 |
| `results/realistic/realistic.json` | 依次 `python -m guard realistic build`、`train`、`eval` | 是 |
| `results/audit/pairs_for_review.csv` | `python -m guard pair-audit` | 否 |
| `results/retune/stage1_realistic.json` | `python -m guard retune` | 否 |
| `results/span/span_stage2.json` | `python -m guard span` | 是 |
| `results/hard/piped.json`、`appended.json` | 依次 `python -m guard hard build`、`train`、`eval` | 是 |
| `results/stage1_place/stage1_place.json` | `python -m guard stage1-place` | 否 |
| `results/unified/*.json` | `python -m guard score --pool trigger_free --variants` | 是 |
| 已存的混淆矩阵、良性假阳性、单元测试 | `python -m guard verify` | 否 |

`data/unified/*.json` 这份缓存打分是重组织之前产生的。`python -m guard score`
会把同样的内容重新生成到 `results/unified/`，实验在存在时优先读它。

`composite_stress` 是唯一没有已提交结果文件的实验。README 里的数字来自
`replication_out/composite_stress_results.json`，那份文件早于 `guard/` 与
`experiments/` 的拆分。现在的脚本写到 `results/composite_stress/`；改动的只有
载荷表那一处，所以行内容应当一致，但重组织之后没有用模型重新验证过。
表里把它标为需要模型，因为它要现场给合成命令打分，而不是读缓存。

### 不变量

* 导入 `guard` 不会加载模型，也不会写文件。
* 只有 `guard/labels.py` 可以引用植入的标记；`tests/test_labels.py` 会扫描
  其他模块，一旦出现就失败。
* 任何代码路径都不会执行生成的命令。命令只是被分词并打分的字符串，不会
  交给 shell。
* `guard/rules.py` 永远拿不到标签；标签只在判决产生之后由指标层读取。
* 平均差与最大下降各只有一个定义，位于 `rules.row_mean_gap` 与
  `rules.row_max_drop`，直接读取已保存的聚合值。
* 结果 JSON 里每个比率都是 `计数 / 分母` 加上 95% Clopper-Pearson 区间；
  按唯一对的比率与按行的比率并列给出。
* 随机种子、阈值和标签集都写进每个结果 JSON。

### 已弃用入口

`reconcile.py`、`benign_fp.py`、`unify_pools.py`、`composite_stress.py`、
`leak_categories.py`、`threshold_sweep.py`、`runlength.py`、`two_stage.py`
仍可运行，会打印弃用提示，并转发到 `python -m guard`。它们调用的是
CLI 而不是库，因此只有一条分发路径。