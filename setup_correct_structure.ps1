# Quantitative Trading Project Structure Setup - CORRECTED
# Creates all 18 modules from the roadmap in the main directory

# Ensure we're in the correct directory
Set-Location "C:\Users\Ryan\Desktop\Quantitative Projects"

$modules = @(
    "00.1-Dataset-Cleaner-Latency-Tick-Store",
    "00.2-Schema-Registry", 
    "01-Back-Testing-Framework",
    "02-Data-Quality-Monitor",
    "03-GOOG-GOOGL-Share-Class-Arb-Strategy",
    "04-Live-Capable-Equity-Trading-Stack",
    "05-Central-Logging-Metrics-Bus",
    "06-API-Integration-Layer-Config-Store",
    "07-Strategy-CICD-Canary-Deployer",
    "08-Universal-Position-PnL-Cache",
    "09-KO-PEP-High-Corr-Pair-Trade",
    "10-Futures-Trend-Following-Platinum",
    "11-Regime-Switching-HMM-Allocator",
    "12-Scalable-Parallel-Processing-Layer",
    "13-VRP-VIX-Term-Structure-Strategy",
    "14-Automated-Factor-Model-Builder",
    "15-Text-JSON-Normalizer-Microservice",
    "16-Vector-Store-Adapter",
    "17-Wisdom-of-Crowd-Sentiment-Ensemble",
    "18-Intraday-NLP-Event-Driver"
)

# Create main directories
$mainDirs = @("docs", "deployment", "shared", "scripts")

Write-Host "Creating Quantitative Trading Project Structure in main directory..." -ForegroundColor Green
Write-Host "Current directory: $(Get-Location)" -ForegroundColor Yellow

# Create main directories
foreach ($dir in $mainDirs) {
    if (-not (Test-Path $dir)) {
        New-Item -ItemType Directory -Path $dir -Force | Out-Null
        Write-Host "Created: $dir" -ForegroundColor Yellow
    } else {
        Write-Host "Already exists: $dir" -ForegroundColor Gray
    }
}

# Create module directories
foreach ($module in $modules) {
    if (-not (Test-Path $module)) {
        New-Item -ItemType Directory -Path $module -Force | Out-Null
        Write-Host "Created: $module" -ForegroundColor Yellow
        
        # Create standard subdirectories for each module
        $subDirs = @("src", "tests", "docs", "config", "scripts")
        foreach ($subDir in $subDirs) {
            New-Item -ItemType Directory -Path "$module\$subDir" -Force | Out-Null
        }
    } else {
        Write-Host "Already exists: $module" -ForegroundColor Gray
    }
}

# Move existing Schema Registry content to 00.2-Schema-Registry
if (Test-Path "Schema Registry") {
    Write-Host "Moving existing Schema Registry content to 00.2-Schema-Registry..." -ForegroundColor Green
    if (-not (Test-Path "00.2-Schema-Registry")) {
        New-Item -ItemType Directory -Path "00.2-Schema-Registry" -Force | Out-Null
    }
    Copy-Item "Schema Registry\*" "00.2-Schema-Registry\" -Recurse -Force
    Write-Host "Schema Registry content copied to 00.2-Schema-Registry" -ForegroundColor Green
}

# Move existing Dataset Cleaner content to 00.1-Dataset-Cleaner-Latency-Tick-Store
if (Test-Path "Dataset Cleaner ＋ Latency Tick‑Store") {
    Write-Host "Moving existing Dataset Cleaner content to 00.1-Dataset-Cleaner-Latency-Tick-Store..." -ForegroundColor Green
    if (-not (Test-Path "00.1-Dataset-Cleaner-Latency-Tick-Store")) {
        New-Item -ItemType Directory -Path "00.1-Dataset-Cleaner-Latency-Tick-Store" -Force | Out-Null
    }
    Copy-Item "Dataset Cleaner ＋ Latency Tick‑Store\*" "00.1-Dataset-Cleaner-Latency-Tick-Store\" -Recurse -Force
    Write-Host "Dataset Cleaner content copied to 00.1-Dataset-Cleaner-Latency-Tick-Store" -ForegroundColor Green
}

Write-Host "`nProject structure created successfully!" -ForegroundColor Green
Write-Host "Total modules: $($modules.Count)" -ForegroundColor Cyan
Write-Host "`nModule List:" -ForegroundColor Cyan
for ($i = 0; $i -lt $modules.Count; $i++) {
    Write-Host "  $($i+1). $($modules[$i])" -ForegroundColor White
}

Write-Host "`nNext steps:" -ForegroundColor Green
Write-Host "1. Review the structure in the main directory" -ForegroundColor White
Write-Host "2. Move the integration plan document to the main docs folder" -ForegroundColor White
Write-Host "3. Start implementing each module in its respective folder" -ForegroundColor White 