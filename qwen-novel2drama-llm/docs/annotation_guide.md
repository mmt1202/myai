# 小说转短剧数据标注指南

## 标注目标

将小说片段整理为高质量 `instruction/input/output` SFT 样本，用于训练小说转 AI 短剧模型。

## 推荐任务比例

| 任务类型 | 建议比例 |
|---|---:|
| 小说片段 → 60 秒分镜脚本 | 30% |
| 小说章节 → 10 集短剧大纲 | 15% |
| 人物描写 → 角色一致性设定 | 15% |
| 剧情摘要 → 爽点/反转/钩子 | 15% |
| 分镜 → AI 视频提示词 | 15% |
| 剧情 → 配音台词 | 10% |

## 通用标注原则

1. `instruction` 要清楚描述任务，不要过长。
2. `input` 保留原始小说信息，不要混入答案。
3. `output` 必须结构化，方便模型学习稳定格式。
4. 每条样本只训练一个明确能力。
5. 短剧输出要强调冲突、反转、爽点和结尾钩子。
6. 视频提示词要包含主体、场景、动作、情绪、光影、运镜、画幅和风格。
7. 配音台词要短句化，标注语气、情绪、语速和停顿。

## 分镜脚本 output 模板

```text
标题：
核心冲突：
镜头1｜时长｜景别｜画面｜动作｜台词｜旁白｜音效｜转场｜AI视频提示词
镜头2｜...
本集爽点：
结尾钩子：
```

## 角色设定 output 模板

```text
角色名：
年龄/性别/身份：
外貌：
气质：
服装：
人物关系：
情绪变化：
角色一致性关键词：
反向提示词：
```

## 质检清单

- 是否有空字段？
- 是否有重复 input？
- output 是否少于 20 字？
- 是否没有短剧冲突？
- 是否缺少视觉信息？
- 是否使用了未授权来源？
- 是否混入闭源商业模型生成内容？

质检前建议运行：

```bash
python scripts/analyze_dataset.py --file datasets/train.jsonl
python scripts/dedupe_dataset.py --input datasets/train.jsonl --output datasets/train.dedup.jsonl
python scripts/sample_dataset.py --input datasets/train.jsonl --output outputs/sample_review.jsonl --size 20
```
