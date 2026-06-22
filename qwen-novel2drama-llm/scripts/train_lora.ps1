param(
    [string]$Config = "configs/qwen2_5_1_5b_lora.yaml"
)
$ErrorActionPreference = "Stop"
# 允许从任意目录调用脚本，实际执行目录固定为项目根目录
$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $ProjectRoot
if (-not (Test-Path $Config)) {
    Write-Error "配置文件不存在：$Config"
}
if (-not (Get-Command llamafactory-cli -ErrorAction SilentlyContinue)) {
    Write-Error "未找到 llamafactory-cli。请先安装 LLaMA-Factory，并确认命令已加入 PATH。参考：https://github.com/hiyouga/LLaMA-Factory"
}
python scripts/validate_dataset.py --file datasets/train.jsonl
python scripts/validate_dataset.py --file datasets/val.jsonl
llamafactory-cli train $Config
