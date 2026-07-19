$ErrorActionPreference = "Continue"
$results = @()
$failedFiles = @()
$passFiles = @()
$hangFiles = @()
$allFiles = Get-ChildItem -Path tests -Filter "test_*.py" | Sort-Object Name
$total = $allFiles.Count
$count = 0

foreach ($f in $allFiles) {
    $count++
    $name = $f.Name
    Write-Output "[$count/$total] $name ..."
    
    $start = Get-Date
    $timeoutSec = 60
    
    # Run with job to enforce timeout
    $job = Start-Job -ScriptBlock {
        param($file)
        Set-Location "C:\Users\Bonjo\source\repos\Calculator logistica"
        $output = python -m pytest $file -q --tb=line --no-header -p no:warnings 2>&1 | Out-String
        return $output
    } -ArgumentList "tests/$name"
    
    $jobResult = Wait-Job $job -Timeout $timeoutSec
    $elapsed = (Get-Date) - $start
    
    if ($jobResult -eq $null) {
        # Timeout - job still running
        Stop-Job $job
        Remove-Job $job -Force
        $hangFiles += $name
        Write-Output "  HANG ($($elapsed.TotalSeconds.ToString('0.0'))s)"
    } else {
        $output = Receive-Job $job
        Remove-Job $job -Force
        
        if ($LASTEXITCODE -eq 0 -or $output -match "passed|no tests ran") {
            $passFiles += $name
            Write-Output "  PASS ($($elapsed.TotalSeconds.ToString('0.0'))s)"
        } else {
            $failedFiles += $name
            $failInfo = $output | Select-String -Pattern "(FAILED|ERROR)" | Select-Object -First 5
            Write-Output "  FAIL ($($elapsed.TotalSeconds.ToString('0.0'))s)"
            $failInfo | ForEach-Object { Write-Output "    $_" }
        }
    }
}

Write-Output "`n=== SUMMARY ==="
Write-Output "Total: $total"
Write-Output "Pass: $($passFiles.Count)"
Write-Output "Fail: $($failedFiles.Count)"
Write-Output "Hang: $($hangFiles.Count)"

if ($failedFiles.Count -gt 0) {
    Write-Output "`n--- Failed files ---"
    $failedFiles | ForEach-Object { Write-Output "  $_" }
}
if ($hangFiles.Count -gt 0) {
    Write-Output "`n--- Hanging files ---"
    $hangFiles | ForEach-Object { Write-Output "  $_" }
}

$passFiles | Out-File -FilePath "$env:TEMP\pytest_pass.txt"
$failedFiles | Out-File -FilePath "$env:TEMP\pytest_fail.txt"
$hangFiles | Out-File -FilePath "$env:TEMP\pytest_hang.txt"
