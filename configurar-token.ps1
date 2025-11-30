# Script para configurar o token do GitHub
# Execute: .\configurar-token.ps1

Write-Host "=== Configurar Token GitHub para cobranca-automatica ===" -ForegroundColor Cyan
Write-Host ""

Write-Host "Cole seu token do GitHub (ghp_...): " -NoNewline -ForegroundColor Yellow
$token = Read-Host

if ([string]::IsNullOrWhiteSpace($token)) {
    Write-Host "Token nao fornecido. Saindo..." -ForegroundColor Red
    exit
}

# Remover espacos e quebras de linha
$token = $token.Trim()

# Configurar o remote com o token
$remoteUrl = "https://$token@github.com/cauafigueredo15-oss/cobranca-automatica.git"
git remote set-url origin $remoteUrl

Write-Host ""
Write-Host "Token configurado com sucesso!" -ForegroundColor Green
Write-Host ""
Write-Host "Testando conexao..." -ForegroundColor Cyan

# Testar a conexao fazendo um fetch
$testResult = git ls-remote origin 2>&1
if ($LASTEXITCODE -eq 0) {
    Write-Host "Conexao funcionando! Voce pode fazer commits agora." -ForegroundColor Green
} else {
    Write-Host "Erro ao testar conexao: $testResult" -ForegroundColor Red
    Write-Host "Verifique se o token esta correto e tem as permissoes necessarias." -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Configuracao concluida!" -ForegroundColor Green



