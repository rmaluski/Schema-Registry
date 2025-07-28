# Migration Guide: Moving Existing Projects to New Structure

## Overview

This guide helps you migrate your existing Schema Registry and Dataset Cleaner projects to the new numbered structure while preserving Git history and GitHub links.

## Current Situation

You have:

- **Existing folders**: `Schema Registry` and `Dataset Cleaner ＋ Latency Tick‑Store`
- **New numbered folders**: `00.2-Schema-Registry` and `00.1-Dataset-Cleaner-Latency-Tick-Store`
- **Goal**: Move content to numbered folders while preserving Git history

## Migration Options

### Option 1: Preserve Git History (Recommended)

If your existing folders have Git repositories with GitHub links:

#### Step 1: Backup New Folders

```powershell
# Navigate to the main directory
cd "C:\Users\Ryan\Desktop\Quantitative Projects"

# Backup the new numbered folders (they're currently empty)
Rename-Item "00.2-Schema-Registry" "00.2-Schema-Registry-backup"
Rename-Item "00.1-Dataset-Cleaner-Latency-Tick-Store" "00.1-Dataset-Cleaner-Latency-Tick-Store-backup"
```

#### Step 2: Move Existing Folders

```powershell
# Move existing folders to new names
Move-Item "Schema Registry" "00.2-Schema-Registry"
Move-Item "Dataset Cleaner ＋ Latency Tick‑Store" "00.1-Dataset-Cleaner-Latency-Tick-Store"
```

#### Step 3: Verify Git Status

```powershell
# Check Schema Registry
cd "00.2-Schema-Registry"
git status
git remote -v
cd ..

# Check Dataset Cleaner
cd "00.1-Dataset-Cleaner-Latency-Tick-Store"
git status
git remote -v
cd ..
```

#### Step 4: Update Remote URLs (if needed)

If the GitHub URLs need to be updated:

```powershell
# For Schema Registry
cd "00.2-Schema-Registry"
git remote set-url origin https://github.com/rmaluski/Schema-Registry.git
git remote -v
cd ..

# For Dataset Cleaner (update with your actual URL)
cd "00.1-Dataset-Cleaner-Latency-Tick-Store"
git remote set-url origin https://github.com/rmaluski/Dataset-Cleaner.git
git remote -v
cd ..
```

### Option 2: Content Migration (If No Git History)

If your existing folders don't have Git repositories:

#### Step 1: Copy Content

```powershell
# Copy Schema Registry content
Copy-Item "Schema Registry\*" "00.2-Schema-Registry\" -Recurse -Force

# Copy Dataset Cleaner content
Copy-Item "Dataset Cleaner ＋ Latency Tick‑Store\*" "00.1-Dataset-Cleaner-Latency-Tick-Store\" -Recurse -Force
```

#### Step 2: Initialize New Git Repositories

```powershell
# For Schema Registry
cd "00.2-Schema-Registry"
git init
git add .
git commit -m "Initial commit - migrated from Schema Registry"
git remote add origin https://github.com/rmaluski/Schema-Registry.git
git push -u origin main
cd ..

# For Dataset Cleaner
cd "00.1-Dataset-Cleaner-Latency-Tick-Store"
git init
git add .
git commit -m "Initial commit - migrated from Dataset Cleaner"
git remote add origin https://github.com/rmaluski/Dataset-Cleaner.git
git push -u origin main
cd ..
```

## Verification Steps

### 1. Check Directory Structure

```powershell
# Verify the new structure
Get-ChildItem | Where-Object { $_.Name -like "00.*" }
```

### 2. Test Git Functionality

```powershell
# Test Schema Registry
cd "00.2-Schema-Registry"
git log --oneline -5
git remote -v
cd ..

# Test Dataset Cleaner
cd "00.1-Dataset-Cleaner-Latency-Tick-Store"
git log --oneline -5
git remote -v
cd ..
```

### 3. Test Application Functionality

```powershell
# Test Schema Registry
cd "00.2-Schema-Registry"
# Run your tests or start the application
cd ..

# Test Dataset Cleaner
cd "00.1-Dataset-Cleaner-Latency-Tick-Store"
# Run your tests or start the application
cd ..
```

## Cleanup

After successful migration:

### 1. Remove Backup Folders

```powershell
# Remove backup folders if migration was successful
Remove-Item "00.2-Schema-Registry-backup" -Recurse -Force
Remove-Item "00.1-Dataset-Cleaner-Latency-Tick-Store-backup" -Recurse -Force
```

### 2. Update Documentation

- Update any documentation that references the old folder names
- Update CI/CD pipelines if they reference old paths
- Update any scripts that use the old folder names

## Troubleshooting

### Issue: Git History Lost

**Solution**: If you accidentally used Option 2 instead of Option 1:

```powershell
# Restore from backup and try Option 1 again
Move-Item "00.2-Schema-Registry-backup" "00.2-Schema-Registry"
Move-Item "00.1-Dataset-Cleaner-Latency-Tick-Store-backup" "00.1-Dataset-Cleaner-Latency-Tick-Store"
```

### Issue: Remote URL Not Working

**Solution**: Check and update the remote URL:

```powershell
cd "00.2-Schema-Registry"
git remote -v
git remote set-url origin https://github.com/rmaluski/Schema-Registry.git
git push -u origin main
cd ..
```

### Issue: Permission Denied

**Solution**: Run PowerShell as Administrator or check file permissions:

```powershell
# Check if you have write permissions
Test-Path "00.2-Schema-Registry" -PathType Container
```

## Final Structure

After migration, your structure should look like:

```
Quantitative Projects/
├── 00.1-Dataset-Cleaner-Latency-Tick-Store/     # Your existing Dataset Cleaner
├── 00.2-Schema-Registry/                        # Your existing Schema Registry
├── 01-Back-Testing-Framework/                   # New (empty)
├── 02-Data-Quality-Monitor/                     # New (empty)
├── ... (other numbered modules)
├── docs/                                        # Project documentation
├── deployment/                                  # Deployment configurations
└── scripts/                                     # Build scripts
```

## Next Steps

1. **Verify Migration**: Ensure both projects work correctly in their new locations
2. **Update References**: Update any scripts, documentation, or CI/CD that reference old paths
3. **Test Integration**: Test that the Schema Registry integration with Dataset Cleaner still works
4. **Continue Development**: Start implementing the next modules in the roadmap

## Support

If you encounter issues during migration:

1. Check the troubleshooting section above
2. Verify Git status and remote URLs
3. Test application functionality
4. Restore from backups if needed

This migration preserves your existing work while organizing it into the new numbered structure for your quantitative trading roadmap.
