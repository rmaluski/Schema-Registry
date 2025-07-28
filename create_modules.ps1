# Create all 18 module directories
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

foreach ($module in $modules) {
    New-Item -ItemType Directory -Path $module -Force
    Write-Host "Created: $module"
} 