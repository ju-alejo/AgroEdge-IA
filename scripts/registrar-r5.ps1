[CmdletBinding(SupportsShouldProcess)]
param(
    [string]$Python = (Get-Command python.exe -ErrorAction Stop).Source,
    [ValidatePattern('^([01]\d|2[0-3]):[0-5]\d$')][string]$Hora,
    [ValidateSet('NOAA','Toca')][string]$Fuente = 'NOAA',
    [switch]$Actualizar
)
$ErrorActionPreference = 'Stop'
$project = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$exe = (Get-Item -LiteralPath $Python).FullName
if ($Fuente -eq 'Toca') {
    $taskName = 'AgroEdge IA - Pronostico Toca R5'
    $launcher = (Get-Item -LiteralPath (Join-Path $project 'scripts\ejecutar_toca_r5.py')).FullName
    $exe = (Get-Item -LiteralPath (Join-Path (Split-Path -Parent $exe) 'pythonw.exe')).FullName
    $arguments = ('"{0}" --dir "{1}"' -f $launcher, (Join-Path $project 'data'))
    $description = 'Consulta diaria conservadora del pronóstico horario de Toca.'
    if (!$Hora) { $Hora = '09:00' }
} else {
    $taskName = 'AgroEdge IA - Boletin R5'
    $script = (Get-Item -LiteralPath (Join-Path $project 'scraper\agroclima.py')).FullName
    $arguments = '"' + $script + '" fetch'
    $description = 'Consulta diaria del boletín estacional del CPC.'
    if (!$Hora) { $Hora = '07:17' }
}
if ($Actualizar -and $Fuente -ne 'Toca') { throw 'La actualización de una tarea existente solo está habilitada para Toca.' }
if ($PSCmdlet.ShouldProcess($taskName, "Registrar consulta diaria a las $Hora (hora de Windows)")) {
    $existing = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
    $firstRun = [DateTime]::ParseExact($Hora,'HH:mm',$null)
    if ($Fuente -eq 'Toca' -and $firstRun -le (Get-Date)) { $firstRun = $firstRun.AddDays(1) }
    $trigger = New-ScheduledTaskTrigger -Daily -At $firstRun
    $action = New-ScheduledTaskAction -Execute $exe -Argument $arguments -WorkingDirectory $project
    if ($existing) {
        if (!$Actualizar) { throw "La tarea ya existe. Puedes modificar su hora en el Programador de tareas." }
        Set-ScheduledTask -TaskName $existing.TaskName -TaskPath $existing.TaskPath -Action $action -Trigger $trigger
        return
    }
    $settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Minutes 5)
    Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Settings $settings -Description $description
}
