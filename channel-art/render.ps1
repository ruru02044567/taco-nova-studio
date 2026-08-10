# 用 Playwright 快取的 Chromium 把 HTML 截成圖
# 用法： .\render.ps1 banner.html ..\channel-banner.png 2048 1152
param(
  [string]$Html   = "banner.html",
  [string]$Out    = "..\channel-banner.png",
  [int]$Width     = 2048,
  [int]$Height    = 1152
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path

$chrome = Get-ChildItem "$env:LOCALAPPDATA\ms-playwright\chromium-*\chrome-win64\chrome.exe" |
          Select-Object -First 1 -ExpandProperty FullName
if (-not $chrome) { throw "找不到 Playwright 的 Chromium" }

$htmlPath = Join-Path $root $Html
$outPath  = [System.IO.Path]::GetFullPath((Join-Path $root $Out))
$url      = ([System.Uri]$htmlPath).AbsoluteUri   # 空格與中文都要轉成 file:// URL
New-Item -ItemType Directory -Force -Path (Split-Path -Parent $outPath) | Out-Null

$args = @(
  "--headless=new", "--disable-gpu", "--hide-scrollbars",
  "--force-device-scale-factor=1",
  "--default-background-color=00000000",
  "--window-size=$Width,$Height",
  "--virtual-time-budget=3000",
  "--screenshot=`"$outPath`"",       # 路徑有空格一定要包引號
  "`"$url`""
)

Start-Process -FilePath $chrome -ArgumentList $args -Wait -NoNewWindow
if (Test-Path $outPath) {
  $f = Get-Item $outPath
  "OK  {0}  {1:N0} KB" -f $f.FullName, ($f.Length / 1KB)
} else {
  throw "截圖失敗：$outPath"
}
