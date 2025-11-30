# Script simples para adicionar sua chave SSH
# Execute: .\adicionar-chave-ssh.ps1

Write-Host "=== Adicionar Chave SSH para cobranca-automatica ===" -ForegroundColor Cyan
Write-Host ""

$sshDir = "$env:USERPROFILE\.ssh"
if (-not (Test-Path $sshDir)) {
    New-Item -ItemType Directory -Path $sshDir -Force | Out-Null
}

Write-Host "OPCAO 1: Se voce ja tem uma chave SSH configurada no GitHub, ela sera usada automaticamente." -ForegroundColor Yellow
Write-Host ""
Write-Host "OPCAO 2: Se voce quer adicionar uma nova chave SSH:" -ForegroundColor Yellow
Write-Host "  1. Cole sua chave SSH privada abaixo" -ForegroundColor White
Write-Host "  2. Pressione Enter duas vezes apos colar" -ForegroundColor White
Write-Host "  3. Digite 'FIM' e pressione Enter" -ForegroundColor White
Write-Host ""
Write-Host "Cole sua chave SSH privada (comeca com -----BEGIN OPENSSH PRIVATE KEY----- ou -----BEGIN RSA PRIVATE KEY-----):" -ForegroundColor Cyan
Write-Host ""

$keyLines = @()
while ($true) {
    $line = Read-Host
    if ($line -eq "FIM") {
        break
    }
    if ($line) {
        $keyLines += $line
    }
}

if ($keyLines.Count -gt 0) {
    Write-Host ""
    Write-Host "Digite um nome para salvar a chave (ex: id_rsa_github) ou pressione Enter para 'id_rsa_cobranca': " -NoNewline
    $keyName = Read-Host
    if ([string]::IsNullOrWhiteSpace($keyName)) {
        $keyName = "id_rsa_cobranca"
    }
    
    $keyPath = "$sshDir\$keyName"
    $keyContent = $keyLines -join "`n"
    $keyContent | Out-File -FilePath $keyPath -Encoding ASCII -NoNewline
    
    # Definir permissoes corretas
    icacls $keyPath /inheritance:r 2>$null | Out-Null
    icacls $keyPath /grant "$env:USERNAME:(R)" 2>$null | Out-Null
    
    Write-Host ""
    Write-Host "Chave salva em: $keyPath" -ForegroundColor Green
    
    # Adicionar ao ssh-agent (se disponivel)
    Write-Host ""
    Write-Host "Adicionando chave ao ssh-agent..." -ForegroundColor Cyan
    ssh-add $keyPath 2>$null
    
    Write-Host ""
    Write-Host "=== Chave SSH adicionada com sucesso! ===" -ForegroundColor Green
} else {
    Write-Host ""
    Write-Host "Nenhuma chave foi adicionada. Usando chaves SSH existentes." -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Testando conexao com GitHub..." -ForegroundColor Cyan
$testResult = ssh -T git@github.com 2>&1
$successPattern = "successfully authenticated"
if ($testResult -match $successPattern) {
    Write-Host "Conexao SSH funcionando!" -ForegroundColor Green
} else {
    Write-Host "Resultado do teste: $testResult" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Se a conexao nao funcionou, certifique-se de que:" -ForegroundColor Yellow
    Write-Host "  1. Sua chave SSH publica esta adicionada no GitHub (Settings > SSH and GPG keys)" -ForegroundColor White
    Write-Host "  2. Voce esta usando a chave correta" -ForegroundColor White
}

Write-Host ""
Write-Host "O repositorio esta configurado para usar SSH." -ForegroundColor Green
Write-Host "Voce pode fazer commit normalmente agora!" -ForegroundColor Green
