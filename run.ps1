[CmdletBinding()]
param(
    [ValidateSet('setup','start','doctor','check','demo','console','home','ai-check','report','logs','stop')]
    [string]$Mode = 'setup',
    [string]$Image = 'airobotbook/ros2-desktop-ai-robot-book-humble:latest'
)
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)
$OutputEncoding = [Console]::OutputEncoding
$Root = (Resolve-Path -LiteralPath $PSScriptRoot).Path
$Name = 'pai-guide-lite'
$Label = 'pai.guide-lite'
$Port = 6088
Set-Location -LiteralPath $Root

function Invoke-Docker {
    param([string[]]$DockerArgs)
    & docker @DockerArgs
    if ($LASTEXITCODE -ne 0) { throw "Docker command failed with exit code $LASTEXITCODE. Read the error above." }
}
function Assert-OwnedContainer {
    $raw = & docker inspect $Name 2>$null
    if ($LASTEXITCODE -ne 0) { throw 'Run 00_SETUP.cmd first. The dedicated container does not exist.' }
    $d = ($raw | ConvertFrom-Json)[0]
    if ($d.Config.Labels.'pai.guide-lite' -ne 'v3') { throw 'Container name collision. Nothing was changed.' }
    $mount = @($d.Mounts | Where-Object { $_.Destination -eq '/workspace/guide' })
    if ($mount.Count -ne 1) { throw 'Unexpected mount. Stop here and review docker inspect.' }
    # Docker Desktop may expose the source as a Linux-translated Windows path.
    if ($d.Config.Labels.'pai.guide-lite.source' -ne $Root) {
        throw 'This container belongs to another extraction folder. Reopen the original folder; do not delete it.'
    }
    return $d
}
try {
    if (-not (Get-Command docker -ErrorAction SilentlyContinue)) { throw 'Docker CLI not found. Start/install Docker Desktop.' }
    & docker info --format '{{.OSType}}' | Out-Null
    if ($LASTEXITCODE -ne 0) { throw 'Docker Engine is not ready. Start Docker Desktop and wait.' }
    New-Item -ItemType Directory -Force -Path (Join-Path $Root 'artifacts') | Out-Null
    if ($Mode -eq 'setup') {
        # Reuse an installed lecture image. Never stop/delete other containers.
        $existing = & docker ps -a --format '{{.Names}}'
        if ($existing -contains $Name) {
            $d = Assert-OwnedContainer
            if (-not $d.State.Running) { Invoke-Docker -DockerArgs @('start',$Name) }
        } else {
            $installedImages = & docker image ls --format '{{.Repository}}:{{.Tag}}'
            if ($installedImages -notcontains $Image) {
                Write-Host 'Lecture image is not installed. Downloading it can take time and disk space.'
                Invoke-Docker -DockerArgs @('pull',$Image)
            }
            $mount = "type=bind,source=$Root,target=/workspace/guide"
            Invoke-Docker -DockerArgs @('run','-d','--name',$Name,
                '--label',"$Label=v3",'--label',"pai.guide-lite.source=$Root",
                '-p',"127.0.0.1:${Port}:80",'--shm-size=512m',
                '-e','RESOLUTION=1280x800','-e','ROS_DOMAIN_ID=73','-e','ROS_LOCALHOST_ONLY=1',
                '-e','LIBGL_ALWAYS_SOFTWARE=1','--mount',$mount,$Image)
        }
        # Record immutable image ID/digests actually used; latest is not treated as a fixed version.
        $d = Assert-OwnedContainer
        $imageInfo = & docker image inspect $d.Image --format '{{json .RepoDigests}}'
        [pscustomobject]@{image_id=$d.Image;repo_digests=$imageInfo;checked_utc=[DateTime]::UtcNow.ToString('o')} |
            ConvertTo-Json | Set-Content -Encoding UTF8 (Join-Path (Join-Path $Root 'artifacts') 'teaching_image.json')
        Start-Sleep -Seconds 4
        Invoke-Docker -DockerArgs @('exec','--user','ubuntu','-e','HOME=/home/ubuntu','-w','/workspace/guide',$Name,
            'bash','/workspace/guide/scripts/in_container.sh','setup')
        Write-Host 'Setup complete. Next: 01_START_GAZEBO.cmd'
        exit 0
    }
    $d = Assert-OwnedContainer
    if ($Mode -eq 'stop') {
        if ($d.State.Running) { Invoke-Docker -DockerArgs @('stop',$Name) }
        Write-Host 'Stopped only pai-guide-lite. Your files, image and other containers were not deleted.'
        exit 0
    }
    if (-not $d.State.Running) { Invoke-Docker -DockerArgs @('start',$Name); Start-Sleep -Seconds 4 }
    switch ($Mode) {
        'start' {
            Invoke-Docker -DockerArgs @('exec','--user','ubuntu','-e','HOME=/home/ubuntu',$Name,
                'bash','/workspace/guide/scripts/start_sim.sh')
            Start-Process "http://localhost:${Port}/"
            Write-Host 'Wait for the Gazebo arm. Next: 02_CHECK.cmd'
        }
        'logs' {
            Invoke-Docker -DockerArgs @('exec',$Name,'bash','-c','tail -n 100 /workspace/guide/artifacts/gazebo_launch.log')
        }
        'report' {
            Invoke-Docker -DockerArgs @('exec','--user','ubuntu',$Name,'bash','/workspace/guide/scripts/in_container.sh','report')
            Start-Process (Join-Path (Join-Path $Root 'artifacts') 'report_draft.html')
        }
        default {
            $argsList = @('exec')
            if ($Mode -eq 'console') { $argsList += '-it' }
            $argsList += @('--user','ubuntu','-e','HOME=/home/ubuntu','-w','/workspace/guide',$Name,
                'bash','/workspace/guide/scripts/in_container.sh',$Mode)
            Invoke-Docker -DockerArgs $argsList
        }
    }
} catch {
    Write-Host "ERROR: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host 'No automatic reinstallation/reset is performed. Keep the output and ask for help.'
    exit 1
}
