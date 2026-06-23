param(
    [Parameter(Mandatory = $true)]
    [string]$PdfInput,

    [Parameter(Mandatory = $true)]
    [string]$OutputDir,

    [Parameter(Mandatory = $true)]
    [string]$JarPath,

    [string]$JavaPath = "java",
    [string]$ImagePrefix = "",
    [string]$DataPrefix = ""
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path -LiteralPath $JarPath)) {
    throw "pdffigures2 jar not found: $JarPath"
}

if (-not (Test-Path -LiteralPath $PdfInput)) {
    throw "PDF input path not found: $PdfInput"
}

$OutputDir = (New-Item -ItemType Directory -Force -Path $OutputDir).FullName
$figuresDir = Join-Path $OutputDir "figures"
$dataDir = Join-Path $OutputDir "data"
$statsPath = Join-Path $OutputDir "stats.json"
New-Item -ItemType Directory -Force -Path $figuresDir, $dataDir | Out-Null

if ($ImagePrefix -eq "") {
    $ImagePrefix = Join-Path $figuresDir ""
}
if ($DataPrefix -eq "") {
    $DataPrefix = Join-Path $dataDir ""
}

& $JavaPath "-Dsun.java2d.cmm=sun.java2d.cmm.kcms.KcmsServiceProvider" `
    -jar $JarPath `
    $PdfInput `
    -s $statsPath `
    -m $ImagePrefix `
    -d $DataPrefix

Write-Host "pdffigures2 output:"
Write-Host "  figures: $figuresDir"
Write-Host "  data:    $dataDir"
Write-Host "  stats:   $statsPath"
