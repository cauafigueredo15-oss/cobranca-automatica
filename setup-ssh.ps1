# Script para configurar SSH para o repositório cobranca-automatica
# Execute este script e cole sua chave SSH quando solicitado

Write-Host "=== Configuração SSH para cobranca-automatica ===" -ForegroundColor Cyan
Write-Host ""

# Verificar se o diretório .ssh existe
$sshDir = "$env:USERPROFILE\.ssh"
if (-not (Test-Path $sshDir)) {
    New-Item -ItemType Directory -Path $sshDir -Force | Out-Null
    Write-Host "Diretório .ssh criado." -ForegroundColor Green
}

# Verificar se já existe uma chave SSH
$defaultKey = "$sshDir\id_rsa"
if (Test-Path $defaultKey) {
    Write-Host "ATENÇÃO: Já existe uma chave SSH em $defaultKey" -ForegroundColor Yellow
    Write-Host "Deseja usar a chave existente ou adicionar uma nova? (s/n): " -NoNewline
    $response = Read-Host
    if ($response -eq "n" -or $response -eq "N") {
        Write-Host "Digite o nome do arquivo da nova chave (sem extensão, ex: id_rsa_github): " -NoNewline
        $keyName = Read-Host
        $keyPath = "$sshDir\$keyName"
    } else {
        $keyPath = $defaultKey
    }
} else {
    Write-Host "Cole sua chave SSH privada abaixo (pressione Enter após colar, depois digite 'FIM' em uma nova linha):" -ForegroundColor Yellow
    Write-Host ""
    $keyContent = @()
    $line = ""
    while ($line -ne "FIM") {
        $line = Read-Host
        if ($line -ne "FIM") {
            $keyContent += $line
        }
    }
    
    Write-Host ""
    Write-Host "Digite um nome para salvar a chave (ex: id_rsa_github, ou pressione Enter para usar 'id_rsa'): " -NoNewline
    $keyName = Read-Host
    if ([string]::IsNullOrWhiteSpace($keyName)) {
        $keyName = "id_rsa"
    }
    
    $keyPath = "$sshDir\$keyName"
    $keyContent -join "`n" | Out-File -FilePath $keyPath -Encoding ASCII -NoNewline
    Write-Host "Chave salva em: $keyPath" -ForegroundColor Green
    
    # Definir permissões corretas (Windows)
    icacls $keyPath /inheritance:r | Out-Null
    icacls $keyPath /grant "$env:USERNAME:(R)" | Out-Null
}

# Configurar SSH config para este repositório específico
$sshConfigPath = "$sshDir\config"
$configContent = @"

# Configuração para cobranca-automatica
Host github.com-cobranca
    HostName github.com
    User git
    IdentityFile $keyPath
    IdentitiesOnly yes

"@

if (Test-Path $sshConfigPath) {
    $existingConfig = Get-Content $sshConfigPath -Raw
    if ($existingConfig -notmatch "github.com-cobranca") {
        Add-Content -Path $sshConfigPath -Value $configContent
        Write-Host "Configuração SSH adicionada ao arquivo config." -ForegroundColor Green
    } else {
        Write-Host "Configuração SSH já existe no arquivo config." -ForegroundColor Yellow
    }
} else {
    Set-Content -Path $sshConfigPath -Value $configContent
    Write-Host "Arquivo SSH config criado." -ForegroundColor Green
}

# Atualizar o remote para usar o host específico
Write-Host ""
Write-Host "Atualizando remote do repositório..." -ForegroundColor Cyan
git remote set-url origin git@github.com-cobranca:cauafigueredo15-oss/cobranca-automatica.git

Write-Host ""
Write-Host "=== Configuração concluída! ===" -ForegroundColor Green
Write-Host ""
Write-Host "Para testar a conexão, execute:" -ForegroundColor Yellow
Write-Host "  ssh -T git@github.com-cobranca" -ForegroundColor White
Write-Host ""
Write-Host "Se funcionar, você verá uma mensagem de sucesso do GitHub." -ForegroundColor Cyan



