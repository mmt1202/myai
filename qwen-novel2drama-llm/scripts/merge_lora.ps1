param(
    [Parameter(Mandatory=$true)][string]$BaseModel,
    [Parameter(Mandatory=$true)][string]$AdapterPath,
    [Parameter(Mandatory=$true)][string]$OutputPath
)
$ErrorActionPreference = "Stop"
$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $ProjectRoot
if (-not (Get-Command llamafactory-cli -ErrorAction SilentlyContinue)) {
    Write-Error "未找到 llamafactory-cli。请先安装 LLaMA-Factory。"
}
llamafactory-cli export --model_name_or_path $BaseModel --adapter_name_or_path $AdapterPath --template qwen --finetuning_type lora --export_dir $OutputPath --export_size 2 --export_legacy_format false
