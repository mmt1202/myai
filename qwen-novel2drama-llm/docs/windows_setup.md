# Windows 环境准备

建议使用 Windows PowerShell：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python scripts\validate_dataset.py --file datasets\train.jsonl
```

如果 `bitsandbytes` 或 QLoRA 在 Windows 上不可用，建议使用 WSL2 或 Linux 服务器训练。
