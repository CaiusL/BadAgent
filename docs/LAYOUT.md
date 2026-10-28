# Repository layout / 仓库结构

## English

```
BadAgent/
├── guard/                     library, no side effects on import
│   ├── config.py              all paths, seeds, pools, thresholds
│   ├── prompts.py             split_prompt, with_task, extract_command
│   ├── counterfactual.py      path-swap and task-rewrite variants
│   ├── scoring.py             teacher-forced and generate-then-score log-probs
│   ├── rules.py               mean gap, max drop, run length, union, metrics
│   ├── labels.py              ground truth; ONLY file naming the marker
│   ├── stats_ci.py            Clopper-Pearson intervals
│   ├── pools.py               unified pools and task-level splits
│   ├── stage2.py              clean-base check (2a likelihood, 2b judge)
│   └── cli.py                 `python -m guard <command>`
├── experiments/               one thin script per experiment
├── data/                      eval prompt sets, benign pairs, manifests
├── results/<experiment>/      result JSONs
├── tests/                     unit tests, no model needed
├── docs/LAYOUT.md             this file
├── script.py                  FROZEN training and generation entry point
├── protect.py                 FROZEN
├── output_guard.py            FROZEN judge used by stage 2b
└── *.py                       deprecated 3-line shims (see below)
```

### Regenerating each result

| Result | Command |
|---|---|
| Pooled confusion matrix, all label sets | `python -m guard reconcile` |
| Benign false positives (30 commands) | `python -m guard benign-fp` |
| Mean-gap threshold sweep, held-out halves | `python -m guard threshold` |
| Run-length detector, held-out halves | `python -m guard runlength` |
| Composite stress (approximation) | `python -m guard composite` |
| Leak rate per category per adapter | `python -m guard leak-categories` |
| Stage 1 / stage 2 / two-stage | `python -m guard two-stage` |
| Re-score a pool from scratch | `python -m guard score --pool trigger_free --variants` |

### Invariants

* Importing `guard` loads no model and writes no file.
* Only `guard/labels.py` may reference the planted marker. `tests/test_labels.py`
  enforces this.
* No code path executes a generated command.
* `guard/rules.py` never receives a label; labels are consulted only by the
  metrics layer, after a verdict exists.
* `mean gap` and `max drop` each have exactly one definition, in
  `rules.row_mean_gap` / `rules.row_max_drop`, reading the stored aggregates.

### Deprecated shims

`reconcile.py`, `benign_fp.py`, `unify_pools.py`, `composite_stress.py`,
`leak_categories.py`, `threshold_sweep.py`, `runlength.py`, `two_stage.py`
still work, print a deprecation warning, and forward to the new modules.

## 中文

```
BadAgent/
├── guard/                     库代码，导入时没有副作用
│   ├── config.py              所有路径、随机种子、池名称、阈值
│   ├── prompts.py             提示词拆分、任务重写、命令抽取
│   ├── counterfactual.py      路径替换与任务改写变体
│   ├── scoring.py             教师强制与先生成再打分
│   ├── rules.py               平均差、最大下降、连续长度、并集、指标
│   ├── labels.py              真实标签；唯一出现标记字符串的文件
│   ├── stats_ci.py            Clopper-Pearson 置信区间
│   ├── pools.py               统一池与按任务切分
│   ├── stage2.py              干净基座检查（2a 似然、2b 判别）
│   └── cli.py                 `python -m guard <命令>`
├── experiments/               每个实验一个薄脚本
├── data/                      评测提示词、良性命令对、数据清单
├── results/<实验名>/          结果 JSON
├── tests/                     单元测试，无需模型
├── docs/LAYOUT.md             本文件
├── script.py                  冻结的训练与生成入口
├── protect.py                 冻结
├── output_guard.py            冻结，供第二阶段 2b 使用
└── *.py                       已弃用的三行入口（见上）
```

### 复现各结果的命令

| 结果 | 命令 |
|---|---|
| 统一混淆矩阵（三套标签） | `python -m guard reconcile` |
| 良性命令误报（30 条） | `python -m guard benign-fp` |
| 平均差阈值扫描（留出半集） | `python -m guard threshold` |
| 连续长度检测（留出半集） | `python -m guard runlength` |
| 复合压力测试（近似） | `python -m guard composite` |
| 各适配器泄漏率 | `python -m guard leak-categories` |
| 第一阶段 / 第二阶段 / 两阶段 | `python -m guard two-stage` |
| 从头重算某个池 | `python -m guard score --pool trigger_free --variants` |

### 不变量

* 导入 `guard` 不会加载模型，也不会写文件。
* 只有 `guard/labels.py` 可以引用植入的标记字符串，由
  `tests/test_labels.py` 强制检查。
* 任何代码路径都不会执行生成的命令。
* `guard/rules.py` 永远拿不到标签；标签只在判决产生之后由指标层读取。
* 平均差与最大下降各只有一个定义，位于
  `rules.row_mean_gap` / `rules.row_max_drop`，直接读取已保存的聚合值。

### 已弃用入口

`reconcile.py`、`benign_fp.py`、`unify_pools.py`、`composite_stress.py`、
`leak_categories.py`、`threshold_sweep.py`、`runlength.py`、`two_stage.py`
仍可运行，会打印弃用提示，并转发到新模块。