# Manter o Bot NT8 Ativo 24/7 sem VPS

> Setup: Mac → UTM (Windows 11) → NinjaTrader 8 → estratégia `BotAprovacao`
> Status na data: rodando em **SIM101** (simulado), sem ordens reais ainda.
> Última atualização: 2026-06-25

## ⚠️ Aviso (válido só quando for pra conta REAL)
Quando o bot estiver **AO VIVO** (`BOT AO VIVO — entradas a partir daqui são REAIS`), ordens reais vão pro broker. Se o Mac/VM dormir ou a internet cair **com posição aberta**, o stop não é gerenciado → risco de estourar o drawdown da conta Apex. Em SIM101 esse risco não existe (só perde trade simulado). VPS bom pra trading é especializado/pago — VPS genérico (GCP/AWS/Azure) é **bloqueado/flagado** por NT8 e prop firms (IP de datacenter). Por isso o caminho aqui é **blindar o setup local**.

---

## 3 Camadas básicas (power settings)

### 1. Mac
- **Amphetamine**: sessão infinita + "Allow display sleep" (tela apaga, sistema não dorme).
- Notebook de tampa fechada: ativar "Allow when display is closed" (senão clamshell dorme).
- Ajustes → Economia de Energia: impedir sleep automático no cabo + "Colocar discos para dormir" **desligado**.

### 2. Windows (dentro da VM)
- Opções de Energia → **Alto Desempenho**.
- Suspensão = **Nunca**, Desligar disco = **Nunca**, Desligar vídeo = Nunca.
- Desabilitar hibernação (cmd admin): `powercfg /h off`
- UTM: garantir que a VM não tenha "suspend on inactivity".

### 3. NT8 (mais importante)
- A conexão (Rithmic/CQG/etc) **cai sozinha** em janelas de manutenção diária.
- `Tools → Options → General → "Restart every"` configurado.
- Na conexão: marcar **auto-reconnect**.
- Na estratégia: garantir que **religa após perda de conexão** (senão fica "ligado mas surdo" — provável causa do Andersson não pegar o movimento mesmo com bot ligado).

---

## 🔥 Camadas escondidas (as que normalmente faltam)
Power setting NÃO cobre nenhuma destas. Testar **#1 e #2 primeiro**.

### 1. App Nap do macOS (vilão invisível)
O macOS afoga a CPU de apps em segundo plano — inclui a UTM. Mesmo "acordada", a VM fica lenta/travada quando a janela não está em foco. Desligar no Terminal do Mac:
```bash
defaults write NSGlobalDomain NSAppSleepDisabled -bool YES
```
Depois fechar e abrir a UTM (ou deslogar/logar).

### 2. Caffeine / PowerToys Awake DENTRO do Windows
Amphetamine acorda o Mac, mas o **Windows** ainda se acha ocioso (sem input) e pode dar throttle/lock. Instalar na VM:
- **PowerToys Awake** (oficial Microsoft) — "Keep awake indefinitely" + mantém tela ligada.
- ou **Caffeine** (zhornsoftware) — finge um F15 a cada 59s.

### 3. Power Nap + Wi-Fi ocioso (Mac)
```bash
sudo pmset -a powernap 0 disksleep 0 sleep 0
```
- Usar **cabo de rede** se possível — Wi-Fi de Mac cai sozinho quando ocioso → NT8 desconecta.
- Se Wi-Fi obrigatório: deixar NT8 com auto-reconnect (camada 3).

### 4. Não minimizar a janela da UTM
App minimizado leva throttle mais agressivo. Deixar a UTM **visível num Space separado** (não minimizada). Combinado com App Nap desligado, faz diferença.

### 5. caffeinate como reserva do Amphetamine
Cinto + suspensório. Rodar num terminal e esquecer:
```bash
caffeinate -dimsu
```

---

## Prioridade prática
1. **App Nap desligado** (#1 escondida) — comando único no Mac.
2. **Caffeine/PowerToys Awake** no Windows (#2 escondida).
3. NT8 auto-reconnect (camada básica 3).
4. Resto como reforço.

## Referência do trade não pego (25/06/2026)
Sinal SHORT MNQ, 5 contratos: entrada `29906,00` → alvo `29846,75` ≈ 60 pontos.
MNQ = $2/ponto/contrato → 5 contratos = $10/ponto → **≈ $600** de lucro.
Não foi pego porque o bot só virou AO VIVO às 12:35 (o sinal foi 10:42). O bot **acertou** o sinal — faltou só estar ativo/online.
