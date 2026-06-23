# 数据集建设计划

本项目不建议一次性追求海量数据。建议分三阶段建设：

| 阶段 | 目标数量 | 目标 |
|---|---:|---|
| P0 | 100-300 | 跑通训练和评估闭环 |
| P1 | 500 | 形成第一版可评估垂直能力 |
| P2 | 1000-3000 | 覆盖主要任务类型和风格变化 |

## 推荐任务比例

任务比例配置在 `datasets/task_mix.json`：

- 小说片段 → 60 秒分镜脚本：30%
- 小说章节 → 10 集短剧大纲：15%
- 人物描写 → 角色一致性设定：15%
- 剧情摘要 → 爽点/反转/钩子：15%
- 分镜 → AI 视频提示词：15%
- 剧情 → 配音台词：10%

## 生成目标数量

```bash
python scripts/plan_dataset_mix.py --total 500
python scripts/plan_dataset_mix.py --total 1000 --output outputs/dataset_plan_1000.json
python scripts/plan_dataset_mix.py --total 3000 --output outputs/dataset_plan_3000.json
```

## 建设建议

1. 先保证每类任务都有高质量样本，再扩大数量。
2. 每 100 条样本抽样人工质检 10 条。
3. 角色一致性、分集连续剧情和视频提示词样本要保留上下文。
4. 数据来源必须可追踪，保留 `source_url/source_name/license`。
5. 不要把未授权小说或闭源商业模型输出混入训练集。
