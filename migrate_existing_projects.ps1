# Migration Script for Existing Projects
# Handles moving existing Schema Registry and Dataset Cleaner to new numbered structure

Write-Host "=== Quantitative Trading Project Migration ===" -ForegroundColor Green
Write-Host "This script will migrate existing projects to the new numbered structure" -ForegroundColor Yellow

# Check current directory
$currentDir = Get-Location
Write-Host "Current directory: $currentDir" -ForegroundColor Cyan

# Define source and destination mappings
$migrations = @{
    "Schema Registry" = "00.2-Schema-Registry"
    "Dataset Cleaner ＋ Latency Tick‑Store" = "00.1-Dataset-Cleaner-Latency-Tick-Store"
}

foreach ($source in $migrations.Keys) {
    $destination = $migrations[$source]
    
    Write-Host "`n--- Processing: $source -> $destination ---" -ForegroundColor Yellow
    
    # Check if source exists
    if (-not (Test-Path $source)) {
        Write-Host "Source '$source' not found, skipping..." -ForegroundColor Red
        continue
    }
    
    # Check if destination exists
    if (-not (Test-Path $destination)) {
        Write-Host "Destination '$destination' not found, creating..." -ForegroundColor Yellow
        New-Item -ItemType Directory -Path $destination -Force | Out-Null
    }
    
    # Check if source has Git repository
    $hasGit = Test-Path "$source\.git"
    Write-Host "Source has Git repository: $hasGit" -ForegroundColor Cyan
    
    if ($hasGit) {
        Write-Host "Git repository detected! Using Git migration approach..." -ForegroundColor Green
        
        # Option 1: Move the entire directory (preserves Git history)
        Write-Host "Moving entire directory to preserve Git history..." -ForegroundColor Yellow
        
        # First, backup the destination if it has content
        if ((Get-ChildItem $destination -Force | Measure-Object).Count -gt 0) {
            $backupName = "$destination-backup-$(Get-Date -Format 'yyyyMMdd-HHmmss')"
            Write-Host "Backing up existing destination to: $backupName" -ForegroundColor Yellow
            Move-Item $destination $backupName
        }
        
        # Move the source to destination
        Write-Host "Moving '$source' to '$destination'..." -ForegroundColor Yellow
        Move-Item $source $destination
        
        Write-Host "Git repository moved successfully!" -ForegroundColor Green
        Write-Host "Remote origin should still be intact." -ForegroundColor Green
        
    } else {
        Write-Host "No Git repository found. Using content migration approach..." -ForegroundColor Yellow
        
        # Option 2: Copy content and initialize new Git repository
        Write-Host "Copying content from '$source' to '$destination'..." -ForegroundColor Yellow
        
        # Copy all content except .git folder
        Get-ChildItem $source -Exclude ".git" | Copy-Item -Destination $destination -Recurse -Force
        
        Write-Host "Content copied successfully!" -ForegroundColor Green
        
        # Check if we should initialize a new Git repository
        $initGit = Read-Host "Initialize new Git repository in '$destination'? (y/n)"
        if ($initGit -eq 'y' -or $initGit -eq 'Y') {
            Write-Host "Initializing new Git repository..." -ForegroundColor Yellow
            Set-Location $destination
            git init
            git add .
            git commit -m "Initial commit - migrated from $source"
            Write-Host "New Git repository initialized!" -ForegroundColor Green
            Set-Location $currentDir
        }
    }
    
    # Create standard subdirectories if they don't exist
    $subDirs = @("src", "tests", "docs", "config", "scripts")
    foreach ($subDir in $subDirs) {
        $subDirPath = Join-Path $destination $subDir
        if (-not (Test-Path $subDirPath)) {
            New-Item -ItemType Directory -Path $subDirPath -Force | Out-Null
            Write-Host "Created subdirectory: $subDir" -ForegroundColor Gray
        }
    }
}

Write-Host "`n=== Migration Complete ===" -ForegroundColor Green
Write-Host "`nNext steps:" -ForegroundColor Yellow
Write-Host "1. Verify that Git repositories are working correctly" -ForegroundColor White
Write-Host "2. Update remote URLs if needed: git remote set-url origin <new-url>" -ForegroundColor White
Write-Host "3. Test that all functionality is preserved" -ForegroundColor White
Write-Host "4. Remove old directories if migration was successful" -ForegroundColor White

Write-Host "`nChecking Git status for migrated repositories..." -ForegroundColor Cyan

foreach ($destination in $migrations.Values) {
    if (Test-Path "$destination\.git") {
        Write-Host "`n--- $destination ---" -ForegroundColor Yellow
        Set-Location $destination
        git status --porcelain
        git remote -v
        Set-Location $currentDir
    }
} 