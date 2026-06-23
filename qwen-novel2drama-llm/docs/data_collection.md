# 合规数据采集说明

本项目可以提供“合规采集工具”，但不建议、也不应抓取未授权小说站、盗版小说站、付费章节或禁止爬取的网站内容用于训练。

## 可采集的数据来源

推荐来源：

1. 你自己创作或购买版权的小说内容。
2. 你与作者、版权方签约授权可用于模型训练的数据。
3. 明确许可证允许机器学习训练/再利用的开放文本。
4. 企业内部已授权业务数据。

不建议来源：

1. 未授权网络小说站。
2. 付费章节、会员章节、App 内付费内容。
3. robots.txt 禁止抓取的页面。
4. 许可证不明确的数据。

## 来源清单格式

使用 JSONL，每行一个来源：

```json
{"url":"https://example.com/your-owned-or-licensed-novel-page.html","source_name":"示例来源","license":"owned-or-licensed-for-training","allow_training":true}
```

字段说明：

- `url`：网页地址。
- `source_name`：来源名称，方便后续追踪。
- `license`：授权或许可证说明。
- `allow_training`：必须为 `true`，表示你确认该来源可用于训练。

## 运行采集

```bash
python scripts/collect_web_text.py --sources datasets/sources.example.jsonl --output datasets/raw_corpus.jsonl
```

默认行为：

- 使用清晰 User-Agent。
- 检查 robots.txt。
- 每个请求默认间隔 2 秒。
- 只处理 HTML 页面。
- 输出原始正文到 `datasets/raw_corpus.jsonl`。

## 从原始语料到训练样本

采集到的 `raw_corpus.jsonl` 不能直接作为 SFT 数据。推荐流程：

1. 人工确认授权和正文质量。
2. 将长文本切成小说片段。
3. 运行 `corpus_to_sft_template.py` 生成待标注模板。
4. 人工补写 `output`，并按任务类型调整 `instruction`。
5. 运行 `validate_dataset.py`。
6. 运行 `analyze/dedupe/sample` 类工具做数据质量检查。

转换命令：

```bash
python scripts/corpus_to_sft_template.py --input datasets/raw_corpus.jsonl --output datasets/annotation_todo.jsonl --chunk-size 1200
```

## 重要提醒

采集工具只是工程能力，不代表任何网页内容都可以用于训练。请只使用你有权使用的数据。
