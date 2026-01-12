$csvPath = "results\summary.csv"
$targetCount = 1 # Header + 400 matches (50 states * 4 strats * 2 opps)

while ($true) {
    if (Test-Path $csvPath) {
        $lines = (Get-Content $csvPath).Count
        Write-Host "Current count: $lines" -NoNewline -ForegroundColor Gray
        Write-Host "`r" -NoNewline
        
        if ($lines -ge $targetCount) {
            Write-Host "`nTarget reached ($lines). Stopping experiment..." -ForegroundColor Yellow
            
            # Find and kill the python process running run_experiment.py
            $procs = Get-WmiObject Win32_Process | Where-Object { $_.CommandLine -like "*run_experiment.py*" }
            
            if ($procs) {
                foreach ($p in $procs) {
                    Write-Host "Killing Process ID: $($p.ProcessId)" -ForegroundColor Red
                    Stop-Process -Id $p.ProcessId -Force
                }
                Write-Host "Experiment stopped." -ForegroundColor Green
            } else {
                Write-Host "No running experiment process found." -ForegroundColor Yellow
            }
            break
        }
    }
    Start-Sleep -Seconds 5
}
