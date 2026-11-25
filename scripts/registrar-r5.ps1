[CmdletBinding(SupportsShouldProcess)]
param(
    [string]$Python = (Get-Command python.exe -ErrorAction Stop).Source,
    [ValidatePattern('^([01]\d|2[0-3]):[0-5]\d$')][string]$Hora,
    [ValidateSet('NOAA','Toca')][string]$Fuente = 'NOAA'
)
$ErrorActionPreference = 'Stop'
$project = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$exe = (Get-Item -LiteralPath $Python).FullName
if ($Fuente -eq 'Toca') {
    $taskName = 'AgroEdge IA - Pronostico Toca R5'
    $collector = 'scraper\toca_forecast.py'
    $description = 'Consulta diaria conservadora del pronóstico horario de Toca.'
    if (!$Hora) { $Hora = '20:45' }
} else {
    $taskName = 'AgroEdge IA - Boletin R5'
    $collector = 'scraper\agroclima.py'
    $description = 'Consulta diaria del boletín estacional del CPC.'
    if (!$Hora) { $Hora = '07:17' }
}
$script = (Get-Item -LiteralPath (Join-Path $project $collector)).FullName
if ($PSCmdlet.ShouldProcess($taskName, "Registrar consulta diaria a las $Hora (hora de Windows)")) {
    $existing = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
    if ($existing) { throw "La tarea ya existe. Puedes modificar su hora en el Programador de tareas." }
    $action = New-ScheduledTaskAction -Execute $exe -Argument ('"' + $script + '" fetch') -WorkingDirectory $project
    $trigger = New-ScheduledTaskTrigger -Daily -At ([DateTime]::ParseExact($Hora,'HH:mm',$null))
    $settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Minutes 5)
    Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Settings $settings -Description $description
}
