# Quantitative Trading Project Structure Setup
# Creates all 18 modules from the roadmap

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

Write-Host "Creating Quantitative Trading Project Structure..." -ForegroundColor Green

# Create main directories
foreach ($dir in $mainDirs) {
    New-Item -ItemType Directory -Path $dir -Force | Out-Null
    Write-Host "Created: $dir" -ForegroundColor Yellow
}

# Create module directories
foreach ($module in $modules) {
    New-Item -ItemType Directory -Path $module -Force | Out-Null
    Write-Host "Created: $module" -ForegroundColor Yellow
    
    # Create standard subdirectories for each module
    $subDirs = @("src", "tests", "docs", "config", "scripts")
    foreach ($subDir in $subDirs) {
        New-Item -ItemType Directory -Path "$module\$subDir" -Force | Out-Null
    }
}

# Move existing Schema Registry
if (Test-Path "Schema Registry") {
    Write-Host "Moving existing Schema Registry to 00.2-Schema-Registry..." -ForegroundColor Green
    Move-Item "Schema Registry\*" "00.2-Schema-Registry\" -Force
    Remove-Item "Schema Registry" -Force
}

# Move existing Dataset Cleaner
if (Test-Path "Dataset Cleaner ＋ Latency Tick‑Store") {
    Write-Host "Moving existing Dataset Cleaner to 00.1-Dataset-Cleaner-Latency-Tick-Store..." -ForegroundColor Green
    Move-Item "Dataset Cleaner ＋ Latency Tick‑Store\*" "00.1-Dataset-Cleaner-Latency-Tick-Store\" -Force
    Remove-Item "Dataset Cleaner ＋ Latency Tick‑Store" -Force
}

Write-Host "`nProject structure created successfully!" -ForegroundColor Green
Write-Host "Total modules: $($modules.Count)" -ForegroundColor Cyan
Write-Host "`nModule List:" -ForegroundColor Cyan
for ($i = 0; $i -lt $modules.Count; $i++) {
    Write-Host "  $($i+1). $($modules[$i])" -ForegroundColor White
} 