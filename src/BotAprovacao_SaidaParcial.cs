#region Using declarations
using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.ComponentModel.DataAnnotations;
using System.Linq;
using System.Text;
using NinjaTrader.Cbi;
using NinjaTrader.Gui;
using NinjaTrader.Gui.Chart;
using NinjaTrader.Data;
using NinjaTrader.NinjaScript;
using NinjaTrader.Core.FloatingPoint;
using NinjaTrader.NinjaScript.Indicators;
using NinjaTrader.NinjaScript.DrawingTools;
using System.Windows.Media;
using System.IO;
using System.Globalization;
#endregion

// =============================================================================
//  BotAprovacao_SaidaParcial — EXPERIMENTO Market Replay (18-19/08/2026)
// -----------------------------------------------------------------------------
//  DERIVADO de src/BotAprovacao.cs (baseline de producao). NAO E' O BOT REAL.
//  Backup identico do baseline em src/BotAprovacao_BASELINE_BACKUP.cs.
//
//  DUAS diferencas funcionais, testadas JUNTAS neste mesmo arquivo:
//
//  1) [18/08] Saida parcial E(4+1) — 4 dos 5 MNQ saem num alvo de +20pt, 1
//     continua com a MESMA gestao de sempre (BE/trailing/alvo 60pt) ate o
//     fim do trade. Busque "EXPERIMENTO 18/08" no arquivo.
//     Status (19/08, 4 dias de Replay/26 trades): AINDA NAO DISPAROU NENHUMA
//     VEZ — maior MFE real visto foi 9,10pt, longe dos 20pt do gatilho. Deixado
//     LIGADO (nao atrapalha o teste abaixo, so nao produz dado novo por ora).
//
//  2) [19/08] Breakeven-lock PROPORCIONAL ao MFE — Prioridade 2 da auditoria
//     de 18/08 (docs/auditoria-profunda-18-08.md). Hipotese causal: 24,2% de
//     TODOS os ganhos reais (84 trades do forward test) saem EXATAMENTE no
//     lock fixo de +2,50pt — um piso artificial que domina a distribuicao de
//     saidas. Testa lock = fracao * (fav-entry) no momento em que o BE aciona
//     e a cada tick depois, em vez de um valor fixo. Busque "EXPERIMENTO
//     19/08" no arquivo.
//
//  Entrada, stop inicial, sizing, horarios, tolerancia, filtro anti-chase:
//  TUDO IDENTICO ao baseline nos dois experimentos. Cada um tem um toggle ON/
//  OFF independente (UsarSaidaParcial / UsarBELockProporcional) — pode
//  desligar qualquer um pra isolar o efeito do outro se precisar.
// -----------------------------------------------------------------------------
//  BotAprovacao  —  Bot de APROVACAO de conta Apex (config "94 em 15 dias")
// -----------------------------------------------------------------------------
//  Estrategia: reversao na maxima/minima do dia anterior ("Niveis 94").
//  Config 5 MNQ: TP 60 | SL 12,5 | BE +3,75->+2,5 | trail 1,75 | tol 20 ticks | maxDist 15pt.
//
//  GESTAO DE SAIDA — MODELO HIBRIDO:
//    - Stop inicial (12,5pt) = ordem no SERVIDOR (protege intrabar, sem OCO
//      pois nao usamos SetProfitTarget -> nao ha par OCO para conflitar).
//    - Quando breakeven aciona: atualiza stop servidor para nivel de lock (+2,5pt).
//      A partir dai, intrabar o servidor garante no minimo o lucro travado.
//    - Alvo (60pt), trailing (1,75pt) = SINTETICOS (fecha a mercado no bar close).
//    - Trailing nao atualiza o servidor (1,75pt e muito apertado; risco de
//      "stop abaixo do mercado" em barras rapidas). Servidor fica no breakeven.
//    - Stop sintetico existe como BACKUP do servidor (se ordem falhar).
//
//  Resultado: protecao real intrabar + sem erros de OCO em reentradas.
//  Calculate = OnBarClose. MNQ: $2/ponto; 5 contratos = $10/ponto.
//  Horarios (ET): entradas 9h30-16h00, flatten 16h55. Niveis = RTH do dia anterior.
//  SEGUNDA (15/06): usa o range do DOMINGO A NOITE (Globex 18h -> seg 9h30) como
//  nivel de rejeicao, em vez da linha de sexta. Toggle: SegUsaDomingo (default ON).
//  Backtest: +3 aprovacoes/ano (19->22), aprova mais rapido (15->13d), OOS 100%/100%.
//
//  ESTRATEGIA NOTURNA — "Nomads Trade da Noite" (16/06, toggle OperarNoite):
//    Reversao nas LINHAS do canal formado entre 19h-21h BR (extremos, NAO Fib centrais):
//      - VENDA: vela A TOCA/PASSA a LINHA de ALTA (topo do canal) dentro da tolerancia;
//      - COMPRA: vela A TOCA/PASSA a LINHA de BAIXA (fundo do canal) dentro da tolerancia;
//      - gatilho = a PROXIMA vela (B) rompe o CORPO da que tocou (j2: ate 2 barras), tick a tick;
//      - filtro CANAL >= 40pt (evita canal raso/ruido — cravou 100% no combinado);
//      - MESMA gestao da diurna (SL 12,5 + BE 3,75/2,5 + trailing tick a tick).
//    Backtest combinado (diurna + noturna, mesma conta 25K): 100% aprovacao,
//    aprova em ~8 dias (vs 14 da diurna so), +33% PnL/ano, OOS 100%/100%.
//    Horario 19h-21h convertido de BR p/ o fuso do grafico (imune ao DST dos EUA).
//    A NOTURNA e ACELERADOR da diurna — sozinha e fraca (~89%). Forward test antes do real.
// =============================================================================

namespace NinjaTrader.NinjaScript.Strategies
{
	public class BotAprovacao_SaidaParcial : Strategy
	{
		// ---------- Niveis do dia anterior (gatilho de entrada) ----------
		private double pdHigh = 0, pdLow = 0;
		private double curHigh = 0, curLow = 0;
		private string diaNiveis = "";

		// ---------- Range do domingo a noite (Globex) p/ usar na SEGUNDA ----------
		private double onHigh = 0, onLow = 0;   // high/low do overnight (dom 18h -> seg 9h30)
		private string onKey   = "";            // data da segunda a que esse range pertence

		// ---------- Gestao da posicao aberta ----------
		private double entryPrice = 0;
		private double stopPrice  = 0;    // stop sintetico: inicial -> trailing apos breakeven
		private double alvoPrice  = 0;    // alvo sintetico (substitui SetProfitTarget)
		private double favPrice   = 0;
		private bool   beFeito    = false;
		private bool   gerenciando = false;
		private string sinalAtivo = "";
		private int    tradeSeq   = 0;    // contador p/ nome de sinal unico por trade
		private bool   stopIntrabarEnviado = false;  // trava: evita reenviar a saida intrabar antes do fill

		// ---------- EXPERIMENTO 18/08 — saida parcial E(4+1) ----------
		private bool   parcialFeita  = false;  // trava: a saida parcial so pode disparar 1x por trade
		private double pnlParcialUsd = 0;      // PnL($, estimado p/ log) da parcela que ja saiu neste trade

		// ---------- Kill switch / controle diario ----------
		private string diaCorrente = "";
		private double pnlInicioDia = 0;
		private bool   bloqueadoHoje = false;
		private double pnlPreRestartDia = 0;   // PnL já realizado hoje ANTES de um restart (lido do arquivo)

		// ---------- Controle de meta (opcional) ----------
		private HashSet<string> diasOperados = new HashSet<string>();
		private bool aprovado = false;

		// ---------- Origem da posicao aberta ("D"=diurna | "N"=noturna) ----------
		private string origemAtual = "";

		// ---------- ESTRATEGIA NOTURNA (canal Fibonacci 19h-21h BR) ----------
		private TimeZoneInfo etTz = null;       // fuso Eastern (diurna opera em ET)
		private TimeZoneInfo brTz = null;       // fuso Brasilia (noturna opera em BR)
		private TimeZoneInfo graficoTz = null;  // fuso que o NinjaTrader usa p/ exibir Time[0] (auto-detectado)
		private double noiteHigh = 0, noiteLow = 0;   // canal acumulado na sessao noturna
		private string noiteDia  = "";                // data BR da sessao noturna corrente
		private int    notTradesDia = 0;              // trades noturnos na sessao (reservado p/ limite futuro)
		private int    pendLado = 0;                  // setup pendente: -1 short, +1 long, 0 nenhum
		private double pendNivel = 0;                 // nivel do corpo a romper (min/max de open,close)
		private int    pendRestantes = 0;             // barras restantes p/ o rompimento acontecer
		private bool   podeArmaVenda  = true;         // toque fresco: preco saiu da zona de venda -> pode armar
		private bool   podeArmaCompra = true;         // toque fresco: preco saiu da zona de compra -> pode armar


		protected override void OnStateChange()
		{
			if (State == State.SetDefaults)
			{
				Description					= @"EXPERIMENTO 18-19/08 — BotAprovacao com saida parcial E(4+1)@20pt + breakeven-lock proporcional ao MFE, p/ validar em Market Replay. Entrada/stop/sizing IDENTICOS ao BotAprovacao original.";
				Name						= "BotAprovacao_SaidaParcial";
				Calculate					= Calculate.OnBarClose;
				EntriesPerDirection			= 1;
				EntryHandling				= EntryHandling.AllEntries;
				IsExitOnSessionCloseStrategy = true;
				ExitOnSessionCloseSeconds	= 30;
				IsFillLimitOnTouch			= false;
				MaximumBarsLookBack			= MaximumBarsLookBack.TwoHundredFiftySix;
				OrderFillResolution			= OrderFillResolution.Standard;
				Slippage					= 0;
				StartBehavior				= StartBehavior.AdoptAccountPosition;
				TimeInForce					= TimeInForce.Gtc;
				TraceOrders					= false;
				RealtimeErrorHandling		= RealtimeErrorHandling.IgnoreAllErrors;  // rede de seguranca: erro de ordem nao desabilita a estrategia
				StopTargetHandling			= StopTargetHandling.PerEntryExecution;
				BarsRequiredToTrade			= 20;
				IsInstantiatedOnEachOptimizationIteration = true;

				Contratos			= 5;

				AlvoPontos			= 60.0;
				StopPontos			= 12.5;
				BreakevenTrigPontos	= 3.75;
				BreakevenLockPontos	= 2.5;
				TrailingPontos		= 1.75;
				TolToqueTicks		= 20;     // 20 ticks = 5pt (otimizado 13/06)
				MaxDistPontos		= 15.0;   // 15pt = sweet spot (otimizado 14/06): 100% taxa, PF 1.60, OOS 100%/100%
				BufferStopServidorPontos = 5.0;   // stop servidor 5pt mais largo que o gerenciado -> a saida a mercado dispara primeiro (anti-fantasma, 18/06)

				StopDiarioDolar		= 750.0;
				MaxTradesDia		= 12;   // limite anti-overtrading (otimizado 23/06): sobe aprovacao 57%->70% no backtest (DD real $1000, slippage 2t), validado OOS. Corta dias de reentrada em sequencia.

				// ----- EXPERIMENTO 18/08: saida parcial E(4+1) -----
				UsarSaidaParcial	= true;   // OFF = comportamento 100% identico ao BotAprovacao original
				ParcialContratos	= 4;      // quantos dos 5 MNQ saem no alvo parcial
				ParcialAlvoPontos	= 20.0;   // alvo da saida parcial, em pontos desde a entrada

				// ----- EXPERIMENTO 19/08: breakeven-lock proporcional ao MFE (Prioridade 2 da auditoria) -----
				UsarBELockProporcional	= true;   // OFF = comportamento 100% identico ao baseline (lock fixo BreakevenLockPontos)
				BELockFracaoMFE			= 0.75;   // lock = fracao * (fav-entry) desde que o BE aciona, ao inves de fixo +2,5pt
				// [CORRIGIDO 19/08 apos 4 dias de replay com 0,5 = zero efeito] Pra fracao*MFE bater o
				// trailing (1,75pt) precisa fracao > 1 - TrailingPontos/BreakevenTrigPontos (~0,53 aqui).
				// Com 0,5 a trava proporcional NUNCA vencia o trailing -> era codigo morto matematicamente,
				// nao so nos 4 dias testados. Com 0,75, domina o trailing p/ MFE entre 3,75 e 7,0pt.

				SessaoInicio		= 930;
				EntradaFim			= 1600;
				FlattenHora			= 1655;

				SegUsaDomingo		= true;   // segunda usa range do Globex (otimizado 15/06: +3 aprov/ano, aprova +rapido, OOS 100%)
				DomNoiteInicio		= 1800;   // abertura do Globex (ET)

				PararAoAprovar		= true;
				MetaLucroDolar		= 1500.0;
				MinDiasOperados		= 7;

				DesenharNiveis		= true;

				// ----- Estrategia noturna (Nomads Trade da Noite) -----
				// DESLIGADA em 23/06/2026: o backtest de slippage (run_slippage_test.py) mostrou que a
				// noturna desaba sob atrito realista (40% aprov a 2 ticks, PREJUIZO a 3 ticks) — os wins
				// curtos nao absorvem slippage. A DIURNA e robusta (100% ate 2 ticks). Foco so na diurna.
				// Codigo da noturna mantido dormente (nunca executa com OperarNoite=false). Ver
				// docs/melhorias-sugeridas.md.
				OperarNoite			= false;   // OFF: foco exclusivo na diurna (robusta a slippage)
				NoiteInicioBR		= 1900;    // 19h00 Brasilia
				NoiteFimBR			= 2100;    // 21h00 Brasilia (nao abre depois)
				NoiteWarmupBR		= 1915;    // so opera apos 19h15 (canal precisa formar)
				NoiteFlattenBR		= 2200;    // flatten de seguranca 22h BR (nao carrega overnight)
				CanalMinPontos		= 40.0;    // canal minimo: cravou 100% + OOS 100%/100% no combinado
				GatilhoBarras		= 2;       // janela (barras) p/ a proxima romper o CORPO da vela que tocou (j2)
				PularDomingoNoite	= true;    // domingo a noite = abertura do Globex (spikes), nao opera
				LinhaToleranciaPontos = 5.0;   // distancia max do EXTREMO (alta/baixa) p/ contar como "tocar a linha"
				ToqueFresco			= false;   // OFF: a linha-extremo ja restringe; ON = 1 entrada por toque (ainda + restrito)
			}
			else if (State == State.Configure)
			{
			}
			else if (State == State.DataLoaded)
			{
				// FUSO-PROOF: o bot NAO depende do fuso configurado no grafico. Ele detecta sozinho
				// qual fuso o NinjaTrader usa p/ exibir Time[0] e converte: diurna -> ET, noturna -> BR.
				// Se nao conseguir detectar, cai no comportamento antigo (assume grafico em ET).
				try { etTz = TimeZoneInfo.FindSystemTimeZoneById("Eastern Standard Time"); }
				catch { etTz = null; }
				try { brTz = TimeZoneInfo.FindSystemTimeZoneById("E. South America Standard Time"); }
				catch { brTz = null; }
				graficoTz = ResolveFusoGrafico();

				if (graficoTz != null)
					Print(string.Format("[BotAprovacao] Fuso do grafico detectado: {0} (UTC{1:+0;-0}h padrao) — convertendo diurna->ET e noturna->BR automaticamente.",
						graficoTz.Id, graficoTz.BaseUtcOffset.TotalHours));
				else
					Print("[BotAprovacao] AVISO: nao consegui detectar o fuso do grafico — assumindo ET (config classica). Tudo segue funcionando.");
			}
			else if (State == State.Realtime)
			{
				// A partir daqui as ordens vao DE VERDADE pro broker. Antes disso (State.Historical) o NT
				// so recalcula/imprime os sinais SEM enviar ordem (ex.: ao (re)habilitar a estrategia no
				// meio do dia). Deixa explicito no log p/ nunca confundir entrada real com recalculo.
				Print(string.Format("{0}  ✅ BOT AO VIVO — entradas a partir daqui sao REAIS (ordens enviadas ao broker).", Time[0]));

				// ANTI-RESET DO STOP DIARIO: se a estrategia reiniciou durante o dia (queda de internet,
				// crash do NT8), restaura o PnL ja realizado antes do restart para que o stop diario
				// continue de onde parou — sem "zerar" a protecao. O PnL e persistido em arquivo a cada
				// barra no modo Realtime.
				string hojeLocal = DateTime.Now.ToString("yyyy-MM-dd");
				pnlPreRestartDia = CarregaPnlDiario(hojeLocal);
				if (Math.Abs(pnlPreRestartDia) > 0.01)
					Print(string.Format("{0}  ⚠️ ANTI-RESET: PnL ja realizado hoje antes do restart = ${1:F2} — stop diario continua de onde parou.",
						Time[0], pnlPreRestartDia));

				// RECOVERY: estrategia reiniciou (crash/rede) com posicao aberta.
				// AdoptAccountPosition ja entrega a posicao; aqui so inicializamos o estado
				// para o trailing assumir no proximo tick via OnMarketData.
				if (Position.MarketPosition != MarketPosition.Flat)
				{
					sinalAtivo  = "RECOVERY";
					origemAtual = "D";   // flatten EOD vai fechar se necessario
					gerenciando = false; // OnMarketData reinicializa na entrada do 1o tick
					Print(string.Format("[BotAprovacao] RECOVERY: reiniciou com posicao {0} @ {1:F2} — trailing assume no proximo tick",
						Position.MarketPosition, Position.AveragePrice));
				}
			}
		}

		protected override void OnBarUpdate()
		{
			if (CurrentBars[0] < BarsRequiredToTrade)
				return;

			// FUSO-PROOF: converte a hora da barra p/ ET (a diurna opera em horario Eastern),
			// independente do fuso configurado no grafico.
			DateTime tEt = EmET(Time[0]);
			int agora = ToTime(tEt) / 100;
			string hoje = tEt.ToString("yyyy-MM-dd");

			if (hoje != diaCorrente)
			{
				diaCorrente   = hoje;
				bloqueadoHoje = false;
				// pnlPreRestartDia: PnL ja realizado hoje antes de um restart (vem do arquivo).
				// Subtraimos para que o stop diario "lembre" as perdas da sessao anterior.
				// Ex: perdeu $78 antes do crash -> pnlInicioDia = 0 - (-78) = +78
				//     -> pnlDia = RealizadoAcumulado - 78 = 0 - 78 = -78 (correto!)
				pnlInicioDia     = RealizadoAcumulado() - pnlPreRestartDia;
				pnlPreRestartDia = 0;   // consumido: proxima mudanca de dia comeca zerado
			}

			bool emSessao = agora >= SessaoInicio && agora < 1600;
			if (hoje != diaNiveis)
			{
				if (curHigh > 0) { pdHigh = curHigh; pdLow = curLow; }
				diaNiveis = hoje;
				curHigh = emSessao ? High[0] : 0;
				curLow  = emSessao ? Low[0]  : 0;
			}
			else if (emSessao)
			{
				curHigh = curHigh == 0 ? High[0] : Math.Max(curHigh, High[0]);
				curLow  = curLow  == 0 ? Low[0]  : Math.Min(curLow,  Low[0]);
			}

			// ----- Range do domingo a noite (Globex): dom >= DomNoiteInicio  ate  seg < SessaoInicio -----
			// Acumula o high/low do overnight p/ servir de nivel de rejeicao na SEGUNDA.
			if (SegUsaDomingo)
			{
				DayOfWeek dow = tEt.DayOfWeek;
				string chaveSeg = null;
				if (dow == DayOfWeek.Sunday && agora >= DomNoiteInicio)
					chaveSeg = tEt.AddDays(1).ToString("yyyy-MM-dd");   // segunda seguinte
				else if (dow == DayOfWeek.Monday && agora < SessaoInicio)
					chaveSeg = hoje;
				if (chaveSeg != null)
				{
					if (chaveSeg != onKey) { onKey = chaveSeg; onHigh = High[0]; onLow = Low[0]; }
					else { onHigh = Math.Max(onHigh, High[0]); onLow = Math.Min(onLow, Low[0]); }
				}
			}

			DesenhaNiveis(hoje);

			// ---------------- Gestao da posicao aberta ----------------
			if (Position.MarketPosition != MarketPosition.Flat)
			{
				diasOperados.Add(hoje);
				GerenciaPosicao();
				if (Position.MarketPosition == MarketPosition.Flat) return;   // saiu pelo trailing nesta barra
			}
			else if (gerenciando)
			{
				gerenciando = false;
				sinalAtivo  = "";
				stopIntrabarEnviado = false;
				origemAtual = "";
			}

			// ---------------- Kill switch diario ----------------
			double pnlDia = RealizadoAcumulado() - pnlInicioDia + UnrealizadoPiorCaso();
			if (StopDiarioDolar > 0 && pnlDia <= -StopDiarioDolar)
			{
				bloqueadoHoje = true;
				if (Position.MarketPosition != MarketPosition.Flat)
					FechaPosicao("StopDiario");
			}

			// Persiste o PnL realizado do dia a cada barra (ao vivo).
			// Se a estrategia cair/reiniciar, o proximo startup le esse valor e o stop
			// diario continua de onde parou — sem "zerar" a protecao.
			if (State == State.Realtime && !string.IsNullOrEmpty(diaCorrente))
				SalvaPnlDiario(RealizadoAcumulado() - pnlInicioDia, diaCorrente);

			// ---------------- Meta de aprovacao ----------------
			if (PararAoAprovar && !aprovado)
			{
				if (RealizadoAcumulado() >= MetaLucroDolar && diasOperados.Count >= MinDiasOperados)
				{
					aprovado = true;
					if (Position.MarketPosition != MarketPosition.Flat)
						FechaPosicao("MetaAtingida");
					Print(string.Format("[BotAprovacao] META ATINGIDA em {0} | realizado ${1:N2} | {2} dias operados — PARANDO de operar.",
						hoje, RealizadoAcumulado(), diasOperados.Count));
				}
			}

			// ---------------- Flatten do pregao diurno (16h55 ET) ----------------
			// Fecha SO a posicao diurna e encerra entradas diurnas. NAO retorna aqui:
			// a janela noturna (apos o pregao) e tratada por ProcessaNoturna() abaixo.
			if (agora >= FlattenHora && Position.MarketPosition != MarketPosition.Flat && origemAtual == "D")
				FechaPosicao("FlattenEOD");

			// ---------------- Entrada DIURNA ----------------
			// EntradaNiveis so dispara dentro de 9h30-16h (checado internamente).
			if (!aprovado && !bloqueadoHoje && Position.MarketPosition == MarketPosition.Flat
				&& !(MaxTradesDia > 0 && TradesHoje() >= MaxTradesDia))
			{
				EntradaNiveis(agora);
			}

			// ---------------- Estrategia NOTURNA (canal Fib 19h-21h BR) ----------------
			if (OperarNoite)
				ProcessaNoturna();
		}

		// ---------------- Gestao INTRABAR (TICK A TICK) — trailing real desde a entrada ----------------
		// Pedido do Marcelo (16/06): o SL tem que SUBIR junto com o lucro a cada tick, pra qualquer
		// reversao apos lucro travar o ganho — nao so no fechamento da barra. Aqui replicamos a logica
		// sintetica (fav -> breakeven -> trailing -> stop/alvo) a CADA TICK, desde o 1o tick apos o fill,
		// fechando A MERCADO sem depender de ordem no servidor (imune ao "stop abaixo do mercado").
		// Roda so ao vivo/replay: OnMarketData NAO dispara no backtest historico -> backtest 100% inalterado.
		// (GerenciaPosicao no OnBarClose continua valendo p/ o backtest e como rede no fechamento da barra.)
		protected override void OnMarketData(MarketDataEventArgs e)
		{
			if (State != State.Realtime) return;
			if (e.MarketDataType != MarketDataType.Last) return;
			if (CurrentBar < 0) return;

			MarketPosition mp = Position.MarketPosition;
			if (mp == MarketPosition.Flat)
			{
				stopIntrabarEnviado = false;
				// ENTRADA NOTURNA TICK A TICK: se ha setup armado (vela A tocou a zona), entra no
				// instante que o preco cruza o CORPO de A — sem esperar a vela B fechar.
				if (OperarNoite && pendLado != 0)
					TentaEntradaNoturnaTick(e.Price);
				return;
			}
			if (stopIntrabarEnviado) return;

			bool isLong = mp == MarketPosition.Long;

			// Inicializa o gerenciamento ja no 1o tick apos o fill (antes mesmo da barra fechar)
			if (!gerenciando)
			{
				entryPrice = Position.AveragePrice;
				favPrice   = entryPrice;
				beFeito    = false;
				stopPrice  = isLong ? entryPrice - StopPontos : entryPrice + StopPontos;
				alvoPrice  = isLong ? entryPrice + AlvoPontos : entryPrice - AlvoPontos;
				gerenciando = true;

				// EXPERIMENTO 18/08: reseta o estado da saida parcial p/ o trade que esta comecando agora.
				parcialFeita  = false;
				pnlParcialUsd = 0;
				if (UsarSaidaParcial)
					Print(string.Format("{0}  [PLANO SAIDA — EXPERIMENTO] {1} contratos total | entrada {2:F2} | stop {3:F2} | "
						+ "{4} saem em {5:F2} (+{6:F1}pt) | {7} continua(m) ate BE/trailing/alvo {8:F2} (+{9:F1}pt)",
						Time[0], Contratos, entryPrice, stopPrice, ParcialContratos,
						isLong ? entryPrice + ParcialAlvoPontos : entryPrice - ParcialAlvoPontos, ParcialAlvoPontos,
						Contratos - ParcialContratos, alvoPrice, AlvoPontos));
			}

			double preco = e.Price;

			// ---------------- EXPERIMENTO 18/08: SAIDA PARCIAL E(4+1) ----------------
			// So dispara 1x por trade. NAO mexe no stop nem no alvo do(s) contrato(s) que
			// continuam -- eles seguem EXATAMENTE a mesma gestao BE/trailing/alvo de sempre,
			// so que agora protegendo/perseguindo uma quantidade menor (o proprio NinjaTrader
			// ajusta a quantidade do ExitLong/ExitShort e do stop no servidor vinculado ao
			// mesmo sinal -- CONFERIR ISSO NO REPLAY, ver aviso no relatorio).
			if (UsarSaidaParcial && !parcialFeita && Position.Quantity > ParcialContratos)
			{
				double alvoParcialPrice = isLong ? entryPrice + ParcialAlvoPontos : entryPrice - ParcialAlvoPontos;
				if ((isLong && preco >= alvoParcialPrice) || (!isLong && preco <= alvoParcialPrice))
				{
					parcialFeita = true;
					double ptsParcial = isLong ? (preco - entryPrice) : (entryPrice - preco);
					pnlParcialUsd = ptsParcial * 2.0 * ParcialContratos;   // MNQ = $2/ponto (estimativa p/ log)
					string sinalParcial = "X_Parcial_" + sinalAtivo;
					try
					{
						if (isLong) ExitLong(ParcialContratos, sinalParcial, sinalAtivo);
						else        ExitShort(ParcialContratos, sinalParcial, sinalAtivo);
					}
					catch (Exception ex)
					{
						Print(string.Format("{0}  ⚠️ ERRO na saida parcial: {1}", Time[0], ex.Message));
					}
					Print(string.Format("{0}  <<< SAIDA PARCIAL [{1}] | {2} {3} contratos @ {4:F2} (alvo parcial {5:F2}) | "
						+ "PnL parcela ~${6:F2} | restam {7} contrato(s) sob {8}",
						Time[0], sinalParcial, isLong ? "LONG" : "SHORT", ParcialContratos, preco, alvoParcialPrice,
						pnlParcialUsd, Contratos - ParcialContratos, sinalAtivo));
				}
			}

			// 1) Pico a favor + SOBE o stop (breakeven -> trailing) a cada tick. Sempre monotonico
			//    (so aperta, nunca afrouxa) — garante lucro travado numa reversao.
			if (isLong)
			{
				favPrice = Math.Max(favPrice, preco);
				if (!beFeito && (favPrice - entryPrice) >= BreakevenTrigPontos)
				{
					beFeito = true;
					// EXPERIMENTO 19/08: lock proporcional ao MFE ja alcancado, em vez de fixo.
					double lockPts0 = UsarBELockProporcional ? (favPrice - entryPrice) * BELockFracaoMFE : BreakevenLockPontos;
					stopPrice = Math.Max(stopPrice, entryPrice + lockPts0);
				}
				if (beFeito)
				{
					double lockPts = UsarBELockProporcional ? (favPrice - entryPrice) * BELockFracaoMFE : BreakevenLockPontos;
					stopPrice = Math.Max(stopPrice, Math.Max(entryPrice + lockPts, favPrice - TrailingPontos));
				}
			}
			else
			{
				favPrice = Math.Min(favPrice, preco);
				if (!beFeito && (entryPrice - favPrice) >= BreakevenTrigPontos)
				{
					beFeito = true;
					double lockPts0 = UsarBELockProporcional ? (entryPrice - favPrice) * BELockFracaoMFE : BreakevenLockPontos;
					stopPrice = Math.Min(stopPrice, entryPrice - lockPts0);
				}
				if (beFeito)
				{
					double lockPts = UsarBELockProporcional ? (entryPrice - favPrice) * BELockFracaoMFE : BreakevenLockPontos;
					stopPrice = Math.Min(stopPrice, Math.Min(entryPrice - lockPts, favPrice + TrailingPontos));
				}
			}

			// 2) Alvo: fecha a mercado se cruzou o alvo neste tick
			if ((isLong && preco >= alvoPrice) || (!isLong && preco <= alvoPrice))
			{
				stopIntrabarEnviado = true;
				Print(string.Format("{0}  [ALVO INTRABAR] {1} @ {2:F2} (alvo {3:F2})",
					Time[0], isLong ? "LONG" : "SHORT", preco, alvoPrice));
				// Neutraliza o server stop antes de fechar: move para nivel impossivel (5000 ticks)
				// para evitar que o stop no servidor crie posicao fantasma (SHORT x5) caso o
				// ExitLong ainda nao tenha sido processado pelo broker quando o preco continua.
				try {
					if (!string.IsNullOrEmpty(sinalAtivo) && sinalAtivo != "RECOVERY")
						SetStopLoss(sinalAtivo, CalculationMode.Ticks, 5000, false);
				} catch { }
				FechaPosicao("AlvoTick");
				return;
			}

			// 3) Stop/trailing: fecha a mercado no 1o tick que cruza o stop ATUAL (ja trilhado)
			if ((!isLong && preco >= stopPrice) || (isLong && preco <= stopPrice))
			{
				stopIntrabarEnviado = true;
				Print(string.Format("{0}  [STOP INTRABAR] {1} @ {2:F2} (stop {3:F2}, fav {4:F2}, BE={5}) — trava tick a tick",
					Time[0], isLong ? "LONG" : "SHORT", preco, stopPrice, favPrice, beFeito ? "sim" : "nao"));
				// Neutraliza o server stop antes de fechar: move para nivel impossivel (5000 ticks)
				// para evitar que o stop no servidor crie posicao fantasma (SHORT x5) caso o
				// ExitLong/ExitShort ainda nao tenha sido processado pelo broker quando o preco
				// continua caindo/subindo e toca o nivel do breakeven no servidor.
				try {
					if (!string.IsNullOrEmpty(sinalAtivo) && sinalAtivo != "RECOVERY")
						SetStopLoss(sinalAtivo, CalculationMode.Ticks, 5000, false);
				} catch { }
				FechaPosicao(beFeito ? "TrailingTick" : "StopTick");
				return;
			}
		}

		// Nivel de rejeicao ativo: na SEGUNDA usa o range do domingo a noite (Globex);
		// nos demais dias usa o RTH do dia anterior. Retorna false se nao ha nivel valido.
		private bool NivelAtivo(out double nHi, out double nLo, out bool usouDomingo)
		{
			usouDomingo = false;
			DateTime tEt = EmET(Time[0]);   // ET: 'segunda' e a chave onKey sao em horario Eastern
			if (SegUsaDomingo && tEt.DayOfWeek == DayOfWeek.Monday
				&& onKey == tEt.ToString("yyyy-MM-dd") && onHigh > 0)
			{
				nHi = onHigh; nLo = onLow; usouDomingo = true;
				return true;
			}
			nHi = pdHigh; nLo = pdLow;
			return (nHi > 0 && nLo > 0);
		}

		private void EntradaNiveis(int agora)
		{
			if (agora < SessaoInicio || agora >= EntradaFim) return;

			double nHi, nLo; bool dom;
			if (!NivelAtivo(out nHi, out nLo, out dom)) return;
			string src = dom ? "(domingo)" : "";

			double tol = TolToqueTicks * TickSize;
			double h = High[0], l = Low[0], c = Close[0];

			// ----- tocou a zona da MAXIMA de referencia? (setup de SHORT) -----
			if (h >= nHi - tol)
			{
				if (c < nHi)
				{
					double distPontos = nHi - c;
					if (MaxDistPontos > 0 && distPontos > MaxDistPontos)
					{
						Print(string.Format("{0}  toque no Max {1:F2} {6} CHASE ignorado (close {2:F2}pt abaixo da linha, max permitido {3:F2}pt)",
							Time[0], nHi, distPontos, MaxDistPontos, h, c, src));
						return;
					}
					// GUARD DE CONEXAO (ao vivo): nao tenta enviar ordem com a conta desconectada.
					if (State == State.Realtime && !ContaConectada())
					{
						Print(string.Format("{0}  ⚠️ SETUP PERDIDO — SHORT na Max {1:F2} {2} NAO ENVIADO: conta DESCONECTADA. (Perdido por CONEXAO, nao pela estrategia.)",
							Time[0], nHi, src));
						return;
					}
					tradeSeq++;
					sinalAtivo = "NIV_S" + tradeSeq;
					origemAtual = "D";
					// Stop no servidor (protege intrabar) — sem SetProfitTarget = sem OCO
					SetStopLoss(sinalAtivo, CalculationMode.Ticks, (StopPontos + BufferStopServidorPontos) / TickSize, false);
					EnterShort(Contratos, sinalAtivo);
					Print(string.Format("{0}  >>> SHORT {7} @ {1:F2}  | tocou Max {2:F2} {6} (H={3:F2}, dist {4:F2}pt) e FECHOU ABAIXO (C={5:F2})",
						Time[0], c, nHi, h, distPontos, c, src, TagEstado()));
				}
				else if (h <= nHi + tol * 2)  // silencia spam quando mercado opera longe acima da linha
				{
					Print(string.Format("{0}  toque no Max {1:F2} {4} SEM rejeicao (H={2:F2}, C={3:F2} >= linha) -> nao entrou",
						Time[0], nHi, h, c, src));
				}
				return;
			}

			// ----- tocou a zona da MINIMA de referencia? (setup de LONG) -----
			if (l <= nLo + tol)
			{
				if (c > nLo)
				{
					double distPontos = c - nLo;
					if (MaxDistPontos > 0 && distPontos > MaxDistPontos)
					{
						Print(string.Format("{0}  toque no Min {1:F2} {4} CHASE ignorado (close {2:F2}pt acima da linha, max permitido {3:F2}pt)",
							Time[0], nLo, distPontos, MaxDistPontos, src));
						return;
					}
					// GUARD DE CONEXAO (ao vivo): nao tenta enviar ordem com a conta desconectada.
					if (State == State.Realtime && !ContaConectada())
					{
						Print(string.Format("{0}  ⚠️ SETUP PERDIDO — LONG na Min {1:F2} {2} NAO ENVIADO: conta DESCONECTADA. (Perdido por CONEXAO, nao pela estrategia.)",
							Time[0], nLo, src));
						return;
					}
					tradeSeq++;
					sinalAtivo = "NIV_L" + tradeSeq;
					origemAtual = "D";
					// Stop no servidor (protege intrabar) — sem SetProfitTarget = sem OCO
					SetStopLoss(sinalAtivo, CalculationMode.Ticks, (StopPontos + BufferStopServidorPontos) / TickSize, false);
					EnterLong(Contratos, sinalAtivo);
					Print(string.Format("{0}  >>> LONG {7} @ {1:F2}  | tocou Min {2:F2} {6} (L={3:F2}, dist {4:F2}pt) e FECHOU ACIMA (C={5:F2})",
						Time[0], c, nLo, l, distPontos, c, src, TagEstado()));
				}
				else if (l >= nLo - tol * 2)  // silencia spam quando mercado opera longe abaixo da linha
				{
					Print(string.Format("{0}  toque no Min {1:F2} {4} SEM reacao (L={2:F2}, C={3:F2} <= linha) -> nao entrou",
						Time[0], nLo, l, c, src));
				}
			}
		}

		// ===================== CONVERSAO DE FUSO (FUSO-PROOF) =====================
		// O bot nao depende do fuso do grafico: detecta o fuso de exibicao (graficoTz) e converte
		// a hora da barra p/ o fuso alvo (ET na diurna, BR na noturna). Se nao detectou o fuso do
		// grafico, cai no fallback (assume grafico em ET).
		private DateTime EmFuso(DateTime t, TimeZoneInfo destino)
		{
			if (graficoTz != null && destino != null)
			{
				try
				{
					DateTime utc = TimeZoneInfo.ConvertTimeToUtc(DateTime.SpecifyKind(t, DateTimeKind.Unspecified), graficoTz);
					return TimeZoneInfo.ConvertTimeFromUtc(utc, destino);
				}
				catch { }
			}
			return DateTime.MinValue;   // sinaliza "usar fallback"
		}

		// Hora da barra em horario de Brasilia (noturna).
		private DateTime EmBR(DateTime t)
		{
			DateTime br = EmFuso(t, brTz);
			if (br != DateTime.MinValue) return br;
			// fallback: assume grafico em ET. BR e fixo (UTC-3); EUA tem DST -> offset +1h (verao) / +2h (inverno).
			int off = 1;
			if (etTz != null)
			{
				try { off = etTz.IsDaylightSavingTime(DateTime.SpecifyKind(t, DateTimeKind.Unspecified)) ? 1 : 2; }
				catch { off = 1; }
			}
			return t.AddHours(off);
		}

		// Hora da barra em horario Eastern (diurna). Fallback: assume que o grafico ja esta em ET.
		private DateTime EmET(DateTime t)
		{
			DateTime et = EmFuso(t, etTz);
			return et != DateTime.MinValue ? et : t;
		}

		private int HoraBR(DateTime t) { DateTime b = EmBR(t); return b.Hour * 100 + b.Minute; }

		// Le, por reflection, o fuso que o NinjaTrader usa p/ exibir as barras (Tools > Options >
		// General > Time zone). Reflection p/ ser robusto entre versoes e NUNCA quebrar a compilacao:
		// se o membro nao existir, retorna null e o bot usa o fallback (assume ET).
		private TimeZoneInfo ResolveFusoGrafico()
		{
			const System.Reflection.BindingFlags PS =
				System.Reflection.BindingFlags.Public | System.Reflection.BindingFlags.Static;
			try
			{
				foreach (var asm in AppDomain.CurrentDomain.GetAssemblies())
				{
					if (asm.FullName == null || asm.FullName.IndexOf("NinjaTrader", StringComparison.OrdinalIgnoreCase) < 0)
						continue;
					Type[] tipos;
					try { tipos = asm.GetTypes(); }
					catch { continue; }   // assembly com tipos nao carregaveis -> pula
					foreach (var t in tipos)
					{
						if (t.Name != "Globals") continue;
						// GeneralOptions pode ser propriedade ou campo estatico
						object go = t.GetProperty("GeneralOptions", PS)?.GetValue(null)
								 ?? t.GetField("GeneralOptions", PS)?.GetValue(null);
						if (go == null) continue;
						var ty = go.GetType();
						var tz = (ty.GetProperty("TimeZoneInfo")?.GetValue(go)
							   ?? ty.GetField("TimeZoneInfo")?.GetValue(go)) as TimeZoneInfo;
						if (tz != null) return tz;
					}
				}
			}
			catch { }
			return null;
		}

		// NOTURNA EM 1 MINUTO (canal 19h-21h BR). A barra A toca/passa a LINHA do canal (extremo de
		// alta/baixa, dentro de LinhaToleranciaPontos) -> ARMA o setup no CORPO de A (min/max open,close). A ENTRADA
		// acontece TICK A TICK no OnMarketData: entra no instante que o preco cruza o corpo de A, sem
		// esperar a vela B fechar (j2 = vale na vela B ou C). Aqui so atualizamos canal, armamos e
		// expiramos o setup. Backtest run_noturna_1min_rev.py (corpo+tick, j2): combinado 100% (27/27),
		// PF 1.63, ~$60,9k/ano, OOS 100%/100%.
		private void ProcessaNoturna()
		{
			int brAgora    = HoraBR(Time[0]);
			DateTime emBr  = EmBR(Time[0]);
			string brDia   = emBr.ToString("yyyy-MM-dd");
			bool naJanela  = brAgora >= NoiteInicioBR && brAgora < NoiteFimBR;

			// Domingo a noite = ABERTURA do Globex (spikes/baixa liquidez). Nao operamos. (PularDomingoNoite)
			if (PularDomingoNoite && emBr.DayOfWeek == DayOfWeek.Sunday) { pendLado = 0; return; }

			// 1) Atualiza o canal da sessao noturna (high/low acumulado desde 19h BR), a cada barra de 1min
			if (naJanela)
			{
				if (brDia != noiteDia)
				{
					noiteDia = brDia; noiteHigh = High[0]; noiteLow = Low[0];
					pendLado = 0; notTradesDia = 0;
					podeArmaVenda = true; podeArmaCompra = true;   // toque fresco: libera no inicio da sessao
					Print(string.Format("{0}  [NOITE 1min] janela {1:D4}-{2:D4} BR aberta | grafico {3:HH:mm} = BR {4:HH:mm}",
						Time[0], NoiteInicioBR, NoiteFimBR, Time[0], EmBR(Time[0])));
				}
				else
				{
					noiteHigh = Math.Max(noiteHigh, High[0]);
					noiteLow  = Math.Min(noiteLow,  Low[0]);
				}
			}

			if (naJanela && noiteHigh > 0)
				DesenhaCanalNoturno(noiteHigh - noiteLow);

			// 2) Flatten de seguranca pos-sessao (so fecha posicao NOTURNA)
			if (brAgora >= NoiteFlattenBR && Position.MarketPosition != MarketPosition.Flat && origemAtual == "N")
			{
				FechaPosicao("FlattenNoite");
				return;
			}

			// 3) So opera dentro da janela, apos warm-up e com canal valido
			if (!naJanela) { pendLado = 0; return; }
			if (brAgora < NoiteWarmupBR || noiteHigh <= 0) return;
			double canal = noiteHigh - noiteLow;
			if (canal < CanalMinPontos) return;
			if (aprovado || bloqueadoHoje) return;
			if (Position.MarketPosition != MarketPosition.Flat) return;

			// A LINHA = o EXTREMO do canal (0% = fundo/Min, 100% = topo/Max), NAO as Fib centrais
			// (23,6%/76,4%). A vela A toca/passa a linha (dentro de LinhaToleranciaPontos) -> arma no
			// CORPO de A; a vela B passa o corpo -> entra (tick a tick). Backtest run_noturna_linha.py
			// (linha +/-5pt): combinado 100% (26/26), OOS 100%/100%, ~$48k/ano.
			double zVenda  = noiteHigh - LinhaToleranciaPontos;   // tocar/passar a LINHA de ALTA (topo do canal)
			double zCompra = noiteLow  + LinhaToleranciaPontos;   // tocar/passar a LINHA de BAIXA (fundo do canal)
			double h = High[0], l = Low[0], c = Close[0], o = Open[0];

			// 4) Setup pendente: a ENTRADA real e tick a tick (OnMarketData -> TentaEntradaNoturnaTick).
			//    Aqui so contamos a expiracao (B e C = j2). REDE p/ backtest historico (sem OnMarketData):
			//    se nao for tempo real, dispara no fechamento da barra que cruzou o corpo de A.
			if (pendLado != 0)
			{
				if (State != State.Realtime)
				{
					if (pendLado == -1 && l <= pendNivel) { EntraNoturna(-1, canal); return; }
					if (pendLado ==  1 && h >= pendNivel) { EntraNoturna( 1, canal); return; }
				}
				pendRestantes--;
				if (pendRestantes <= 0) pendLado = 0;
				return;   // enquanto ha setup pendente, nao arma outro
			}

			// 5) TOQUE FRESCO: so libera um novo arme depois que o preco SAIU da zona (vela inteira
			//    fora da linha) e VOLTOU a tocar. Evita re-entrar enquanto o preco ronda a linha do
			//    mesmo movimento. 1 entrada por toque. Backtest run_noturna_retouch.py: 100% / PF 1.58
			//    (mesma qualidade do baseline) / ~$44k/ano / OOS 100%-100%.
			if (Low[0]  > zCompra) podeArmaCompra = true;   // vela toda ACIMA da linha de compra -> saiu da zona
			if (High[0] < zVenda)  podeArmaVenda  = true;   // vela toda ABAIXO da linha de venda -> saiu da zona

			// Vela A TOCA a zona (sem exigir rejeicao, pode ter passado) -> arma no CORPO de A.
			// A entrada dispara tick a tick quando o preco cruzar este nivel na vela B (ou C).
			if (h >= zVenda && (!ToqueFresco || podeArmaVenda))
			{
				pendLado = -1; pendNivel = Math.Min(o, c); pendRestantes = GatilhoBarras;   // venda: cruza corpo inferior de A
				podeArmaVenda = false;                                                       // consome o toque
			}
			else if (l <= zCompra && (!ToqueFresco || podeArmaCompra))
			{
				pendLado = 1; pendNivel = Math.Max(o, c); pendRestantes = GatilhoBarras;    // compra: cruza corpo superior de A
				podeArmaCompra = false;                                                      // consome o toque
			}
		}

		// Entrada noturna TICK A TICK: chamada pelo OnMarketData a cada tick enquanto ha setup armado.
		// Entra no INSTANTE que o preco cruza o corpo de A (vela B/C), sem esperar a vela fechar.
		private void TentaEntradaNoturnaTick(double preco)
		{
			if (aprovado || bloqueadoHoje) return;
			int brAgora = HoraBR(Time[0]);
			if (brAgora < NoiteWarmupBR || brAgora >= NoiteFimBR) return;   // so dentro da janela
			double canal = noiteHigh - noiteLow;
			if (canal < CanalMinPontos) return;

			if (pendLado == -1 && preco <= pendNivel)      EntraNoturna(-1, canal);
			else if (pendLado == 1 && preco >= pendNivel)  EntraNoturna( 1, canal);
		}

		// Entrada noturna a mercado no fechamento da barra que rompeu o corpo.
		// Reusa a mesma gestao da diurna: stop no servidor + trailing tick a tick (OnMarketData).
		private void EntraNoturna(int lado, double canal)
		{
			// GUARD DE CONEXAO (ao vivo): nao tenta enviar ordem com a conta desconectada.
			if (State == State.Realtime && !ContaConectada())
			{
				pendLado = 0;   // consome o setup (evita spam tick a tick)
				Print(string.Format("{0}  ⚠️ SETUP PERDIDO — NOITE {1} NAO ENVIADO: conta DESCONECTADA. (Perdido por CONEXAO, nao pela estrategia.)",
					Time[0], lado == -1 ? "SHORT" : "LONG"));
				return;
			}
			tradeSeq++;
			sinalAtivo  = (lado == -1 ? "NOT_S" : "NOT_L") + tradeSeq;
			origemAtual = "N";
			notTradesDia++;
			pendLado = 0;
			SetStopLoss(sinalAtivo, CalculationMode.Ticks, (StopPontos + BufferStopServidorPontos) / TickSize, false);
			if (lado == -1) EnterShort(Contratos, sinalAtivo);
			else            EnterLong(Contratos, sinalAtivo);
			Print(string.Format("{0}  >>> NOITE {1} {7} @ {2:F2} | canal {3:F1}pt [{4:F2}-{5:F2}] | rompeu corpo {6:F2}",
				Time[0], lado == -1 ? "SHORT" : "LONG", Close[0], canal, noiteLow, noiteHigh, pendNivel, TagEstado()));
		}

		// ---------------- Gestao de stop/alvo/breakeven/trailing — 100% SINTETICO ----------------
		// Tudo gerenciado no codigo (igual ao backtest Python): fecha a mercado quando a barra
		// fecha alem do nivel. Sem SetStopLoss/SetProfitTarget -> sem OCO -> sem conflito em reentradas.
		private void GerenciaPosicao()
		{
			bool isLong = Position.MarketPosition == MarketPosition.Long;

			// 1a barra na posicao (barra do fill): inicializa stop/alvo sinteticos.
			// NAO retorna -> ja gerencia stop/alvo/breakeven/trailing NESTA barra, igual ao backtest
			// (la o 1o bar gerenciado e o seguinte ao sinal e ja rastreia fav/breakeven). Antes o
			// 'return' pulava o fill -> movimento a favor na 1a barra nao travava o breakeven (B.O. 15/06).
			if (!gerenciando)
			{
				entryPrice = Position.AveragePrice;
				favPrice   = entryPrice;
				beFeito    = false;
				stopPrice  = isLong ? entryPrice - StopPontos : entryPrice + StopPontos;
				alvoPrice  = isLong ? entryPrice + AlvoPontos : entryPrice - AlvoPontos;
				gerenciando = true;
			}

			// Alvo sintetico
			if (isLong  && High[0] >= alvoPrice) { FechaPosicao("Alvo"); return; }
			if (!isLong && Low[0]  <= alvoPrice) { FechaPosicao("Alvo"); return; }

			// Stop sintetico (inicial antes do breakeven, trailing depois)
			if (isLong  && Low[0]  <= stopPrice) { FechaPosicao(beFeito ? "Trailing" : "StopInicial"); return; }
			if (!isLong && High[0] >= stopPrice) { FechaPosicao(beFeito ? "Trailing" : "StopInicial"); return; }

			// Atualiza o nivel de trailing (vale a partir da proxima barra)
			if (isLong)
			{
				favPrice = Math.Max(favPrice, High[0]);
				if (!beFeito && (favPrice - entryPrice) >= BreakevenTrigPontos)
				{
					beFeito = true;
					// EXPERIMENTO 19/08: lock proporcional ao MFE ja alcancado, em vez de fixo.
					double lockPts0 = UsarBELockProporcional ? (favPrice - entryPrice) * BELockFracaoMFE : BreakevenLockPontos;
					// Move stop servidor para nivel de breakeven — garante lucro minimo intrabar.
					// Em recovery (sem signal original), atualiza todos os stops da estrategia.
					if (!string.IsNullOrEmpty(sinalAtivo) && sinalAtivo != "RECOVERY")
						SetStopLoss(sinalAtivo, CalculationMode.Price, entryPrice + lockPts0 - BufferStopServidorPontos, false);
					// em recovery: server stop anterior ainda protege; trailing sintetico gerencia a saida
				}
				if (beFeito)
				{
					double lockPts = UsarBELockProporcional ? (favPrice - entryPrice) * BELockFracaoMFE : BreakevenLockPontos;
					stopPrice = Math.Max(stopPrice, Math.Max(entryPrice + lockPts, favPrice - TrailingPontos));
				}
			}
			else
			{
				favPrice = Math.Min(favPrice, Low[0]);
				if (!beFeito && (entryPrice - favPrice) >= BreakevenTrigPontos)
				{
					beFeito = true;
					double lockPts0 = UsarBELockProporcional ? (entryPrice - favPrice) * BELockFracaoMFE : BreakevenLockPontos;
					// Move stop servidor para nivel de breakeven — garante lucro minimo intrabar.
					if (!string.IsNullOrEmpty(sinalAtivo) && sinalAtivo != "RECOVERY")
						SetStopLoss(sinalAtivo, CalculationMode.Price, entryPrice - lockPts0 + BufferStopServidorPontos, false);
					// em recovery: server stop anterior ainda protege; trailing sintetico gerencia a saida
				}
				if (beFeito)
				{
					double lockPts = UsarBELockProporcional ? (entryPrice - favPrice) * BELockFracaoMFE : BreakevenLockPontos;
					stopPrice = Math.Min(stopPrice, Math.Min(entryPrice - lockPts, favPrice + TrailingPontos));
				}
			}
		}

		// ---------------- Desenho das linhas de max/min do dia anterior ----------------
		private void DesenhaNiveis(string hoje)
		{
			if (!DesenharNiveis) return;

			double nHi, nLo; bool dom;
			NivelAtivo(out nHi, out nLo, out dom);
			string titulo = dom ? "Niveis DOMINGO a noite (Globex):" : "Niveis dia anterior:";

			Draw.TextFixed(this, "statusNiveis",
				titulo + "\n" +
				"  Max (short): " + (nHi > 0 ? nHi.ToString("F2") : "(aguardando 1o dia)") + "\n" +
				"  Min (long):  " + (nLo > 0 ? nLo.ToString("F2") : "(aguardando 1o dia)"),
				TextPosition.TopRight);

			if (nHi <= 0 || nLo <= 0) return;

			Draw.HorizontalLine(this, "PDH", nHi, Brushes.Red,       DashStyleHelper.Dash, 2);
			Draw.HorizontalLine(this, "PDL", nLo, Brushes.LimeGreen, DashStyleHelper.Dash, 2);
		}

		// ---------------- Desenho do canal noturno + zonas de Fibonacci (19h-21h BR) ----------------
		private void DesenhaCanalNoturno(double canal)
		{
			if (!DesenharNiveis || canal <= 0) return;

			// As LINHAS que contam: o EXTREMO de alta (topo) e de baixa (fundo). O gatilho arma
			// quando o preco entra na BANDA de tolerancia (dentro de LinhaToleranciaPontos da linha).
			double topo  = noiteHigh;                            // linha de ALTA (vende aqui)
			double fundo = noiteLow;                             // linha de BAIXA (compra aqui)
			double bandaVenda  = topo  - LinhaToleranciaPontos;  // toca a linha de alta dentro daqui -> arma venda
			double bandaCompra = fundo + LinhaToleranciaPontos;  // toca a linha de baixa dentro daqui -> arma compra

			bool valido = canal >= CanalMinPontos;          // laranja forte = opera; cinza = canal raso (so observa)
			Brush corCanal = valido ? Brushes.DarkOrange : Brushes.Gray;

			Draw.HorizontalLine(this, "NoiteTopo",  topo,        corCanal,     DashStyleHelper.Solid, 2);
			Draw.HorizontalLine(this, "NoiteFundo", fundo,       corCanal,     DashStyleHelper.Solid, 2);
			Draw.HorizontalLine(this, "NoiteBandaV", bandaVenda,  Brushes.Gold, DashStyleHelper.Dot,   1);
			Draw.HorizontalLine(this, "NoiteBandaC", bandaCompra, Brushes.Gold, DashStyleHelper.Dot,   1);

			Draw.TextFixed(this, "statusNoite",
				"Canal NOITE (19h-21h BR): " + canal.ToString("F1") + "pt " + (valido ? "(operando)" : "(< minimo, so observa)") + "\n" +
				"  LINHA de ALTA (vende):  " + topo.ToString("F2")  + "  (toca ate " + bandaVenda.ToString("F2") + ")\n" +
				"  LINHA de BAIXA (compra): " + fundo.ToString("F2") + "  (toca ate " + bandaCompra.ToString("F2") + ")",
				TextPosition.BottomRight);
		}

		private void FechaPosicao(string motivo)
		{
			if (Position.MarketPosition == MarketPosition.Flat) return;
			// ~saida aproximada: stop/trailing saem ~no stopPrice trilhado; alvo ~no alvoPrice; demais (flatten diario/EOD) ~no close.
			double saidaAprox = Close[0];
			if (motivo == "StopTick" || motivo == "TrailingTick" || motivo == "StopInicial" || motivo == "Trailing")
				saidaAprox = stopPrice;
			else if (motivo == "Alvo" || motivo == "AlvoTick")
				saidaAprox = alvoPrice;
			Print(string.Format("{0}  <<< SAIDA [{1}] | {2} {3} | entrada {4:F2} ~saida {5:F2} | fav {6:F2} | BE={7}",
				Time[0], motivo, Position.MarketPosition, sinalAtivo, entryPrice, saidaAprox, favPrice, beFeito ? "sim" : "nao"));
			// EXPERIMENTO 18/08: se houve saida parcial neste trade, loga o PnL TOTAL combinado
			// (parcela que ja saiu + o que esta saindo agora) -- pra facilitar auditoria no Replay.
			if (UsarSaidaParcial && parcialFeita)
			{
				bool isLongFinal = Position.MarketPosition == MarketPosition.Long;
				double ptsFinal = isLongFinal ? (saidaAprox - entryPrice) : (entryPrice - saidaAprox);
				int contratosRestantes = Contratos - ParcialContratos;
				double pnlFinalUsd = ptsFinal * 2.0 * contratosRestantes;   // MNQ = $2/ponto (estimativa p/ log)
				Print(string.Format("{0}  <<< PnL TOTAL DO TRADE (parcial + final) ~${1:F2}  "
					+ "(parcial {2} contr. ~${3:F2}  +  final {4} contr. ~${5:F2})",
					Time[0], pnlParcialUsd + pnlFinalUsd, ParcialContratos, pnlParcialUsd, contratosRestantes, pnlFinalUsd));
			}
			// Em recovery (signal perdido no restart) fecha sem especificar o signal, para nao errar
			bool semSignal = string.IsNullOrEmpty(sinalAtivo) || sinalAtivo == "RECOVERY";
			if (Position.MarketPosition == MarketPosition.Long)
			{
				if (semSignal) ExitLong("X_" + motivo);
				else           ExitLong("X_" + motivo, sinalAtivo);
			}
			else if (Position.MarketPosition == MarketPosition.Short)
			{
				if (semSignal) ExitShort("X_" + motivo);
				else           ExitShort("X_" + motivo, sinalAtivo);
			}
		}

		// ---- Persistencia do PnL diario (anti-reset de stop apos restart/queda de internet) ----
		// Salva/restaura o PnL realizado do dia num arquivo simples. Se a estrategia reiniciar
		// no meio do dia, o proximo startup le o valor salvo e o stop diario continua de onde parou.
		private string CaminhoArquivoPnl()
		{
			return Path.Combine(
				Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData),
				"NinjaTrader 8", "BotAprovacao_pnl_diario.txt");
		}

		private void SalvaPnlDiario(double pnlRealizado, string data)
		{
			try
			{
				File.WriteAllText(CaminhoArquivoPnl(),
					data + ":" + pnlRealizado.ToString("F2", CultureInfo.InvariantCulture));
			}
			catch { }
		}

		private double CarregaPnlDiario(string hoje)
		{
			try
			{
				string path = CaminhoArquivoPnl();
				if (!File.Exists(path)) return 0;
				string s = File.ReadAllText(path).Trim();
				int sep = s.IndexOf(':');
				if (sep < 0) return 0;
				if (s.Substring(0, sep) != hoje) return 0;   // outro dia -> ignora
				return double.Parse(s.Substring(sep + 1), CultureInfo.InvariantCulture);
			}
			catch { return 0; }
		}

		private double RealizadoAcumulado()
		{
			try
			{
				return SystemPerformance?.AllTrades?.TradesPerformance?.Currency?.CumProfit ?? 0;
			}
			catch { return 0; }
		}

		private double UnrealizadoPiorCaso()
		{
			if (Position.MarketPosition == MarketPosition.Long)
				return Position.GetUnrealizedProfitLoss(PerformanceUnit.Currency, Low[0]);
			if (Position.MarketPosition == MarketPosition.Short)
				return Position.GetUnrealizedProfitLoss(PerformanceUnit.Currency, High[0]);
			return 0;
		}

		private int TradesHoje()
		{
			int n = 0;
			try
			{
				string hoje = Time[0].ToString("yyyy-MM-dd");
				var trades = SystemPerformance?.AllTrades;
				if (trades != null)
				{
					for (int i = trades.Count - 1; i >= 0; i--)
					{
						var exit = trades[i]?.Exit;
						if (exit == null) continue;  // trade aberto ainda nao tem Exit
						if (exit.Time.ToString("yyyy-MM-dd") == hoje) n++;
						else break;
					}
				}
			}
			catch { }
			if (Position.MarketPosition != MarketPosition.Flat) n++;
			return n;
		}

		// ---------------- GUARD DE CONEXAO (anti "ordem nao enviada: conta desconectada") ----------------
		// Antes de enviar qualquer entrada AO VIVO, confirma que a conta esta conectada ao broker. Se a
		// conexao caiu (queda de internet/feed), NAO tenta enviar: evita o popup de erro modal que trava
		// a tela e loga o setup perdido com clareza. FAIL-OPEN: se nao conseguir determinar o status,
		// retorna true (deixa o NT tentar) — nunca bloqueia uma entrada valida por duvida. So vale ao
		// vivo (a chamada e protegida por State==Realtime); backtest/historico ficam 100% inalterados.
		private bool ContaConectada()
		{
			try
			{
				if (Account != null && Account.Connection != null)
					return Account.Connection.Status == ConnectionStatus.Connected;
			}
			catch { }
			return true;   // fail-open: na duvida, deixa tentar (nao perde entrada valida)
		}

		// Marcador de origem do log de entrada: [REAL] = ao vivo (ordem enviada ao broker);
		// [HIST] = recalculo historico (NAO envia ordem — ex.: ao (re)habilitar a estrategia no meio do dia).
		private string TagEstado() { return State == State.Realtime ? "[REAL]" : "[HIST]"; }

		#region Properties
		[NinjaScriptProperty]
		[Range(1, 50)]
		[Display(Name="Contratos", Description="Qtd de contratos (5 = config MNQ vencedora)", Order=1, GroupName="1. Geral")]
		public int Contratos { get; set; }

		[NinjaScriptProperty]
		[Range(1, 500)]
		[Display(Name="Alvo (pontos)", Description="Take profit em pontos (60 = config vencedora)", Order=10, GroupName="2. Saida")]
		public double AlvoPontos { get; set; }

		[NinjaScriptProperty]
		[Range(0.25, 100)]
		[Display(Name="Stop (pontos)", Description="Stop loss em pontos (12,5 = $125/trade com 5 MNQ)", Order=11, GroupName="2. Saida")]
		public double StopPontos { get; set; }

		[NinjaScriptProperty]
		[Range(0.25, 50)]
		[Display(Name="Breakeven gatilho (pontos)", Description="Ganho que aciona o breakeven", Order=12, GroupName="2. Saida")]
		public double BreakevenTrigPontos { get; set; }

		[NinjaScriptProperty]
		[Range(0, 50)]
		[Display(Name="Breakeven trava (pontos)", Description="Lucro travado ao acionar o breakeven", Order=13, GroupName="2. Saida")]
		public double BreakevenLockPontos { get; set; }

		[NinjaScriptProperty]
		[Range(0.25, 50)]
		[Display(Name="Trailing (pontos)", Description="Distancia do trailing a partir do breakeven", Order=14, GroupName="2. Saida")]
		public double TrailingPontos { get; set; }

		[NinjaScriptProperty]
		[Range(0, 50)]
		[Display(Name="Tolerancia toque (ticks)", Description="Distancia max da linha p/ contar como toque (20 ticks=5pt, otimizado)", Order=15, GroupName="2. Saida")]
		public int TolToqueTicks { get; set; }

		[NinjaScriptProperty]
		[Range(0, 200)]
		[Display(Name="Max dist. entrada (pontos)", Description="Close deve estar a no max X pontos da linha (0=sem filtro, 15=recomendado). Filtra entradas chase.", Order=16, GroupName="2. Saida")]
		public double MaxDistPontos { get; set; }

		[NinjaScriptProperty]
		[Range(0, 50)]
		[Display(Name="Buffer stop servidor (pontos)", Description="O stop NO SERVIDOR fica este tanto MAIS LARGO que o stop gerenciado (tick a tick). Garante que a saida a mercado dispare ANTES do stop do servidor — evita duplo-fill / posicao fantasma. 5pt recomendado. 0 = comportamento antigo (risco de fantasma).", Order=17, GroupName="2. Saida")]
		public double BufferStopServidorPontos { get; set; }

		[NinjaScriptProperty]
		[Range(0, 100000)]
		[Display(Name="Stop diario ($)", Description="Para de operar no dia ao perder esse valor (0 = desliga)", Order=20, GroupName="3. Risco")]
		public double StopDiarioDolar { get; set; }

		// ----- EXPERIMENTO 18/08: saida parcial E(4+1) -----
		[NinjaScriptProperty]
		[Display(Name="[EXP] Usar saida parcial", Description="ON = saida parcial E(4+1) ativa. OFF = comportamento 100% identico ao BotAprovacao original (use isso pra comparar A/B no mesmo arquivo se precisar).", Order=80, GroupName="9. Experimento Saida Parcial")]
		public bool UsarSaidaParcial { get; set; }

		[NinjaScriptProperty]
		[Range(1, 4)]
		[Display(Name="[EXP] Contratos na saida parcial", Description="Quantos dos 5 MNQ saem no alvo parcial (padrao 4, deixando 1 pra capturar a cauda)", Order=81, GroupName="9. Experimento Saida Parcial")]
		public int ParcialContratos { get; set; }

		[NinjaScriptProperty]
		[Range(1, 200)]
		[Display(Name="[EXP] Alvo parcial (pontos)", Description="Distancia em pontos, desde a entrada, do alvo da saida parcial (padrao 20 = a hipotese testada no backtest)", Order=82, GroupName="9. Experimento Saida Parcial")]
		public double ParcialAlvoPontos { get; set; }

		// ----- EXPERIMENTO 19/08: breakeven-lock proporcional ao MFE -----
		[NinjaScriptProperty]
		[Display(Name="[EXP2] Usar BE-lock proporcional", Description="ON = lock do breakeven vira fracao do MFE ja alcancado (em vez de fixo). OFF = comportamento 100% identico ao baseline (BreakevenLockPontos fixo).", Order=90, GroupName="10. Experimento BE-Lock Proporcional")]
		public bool UsarBELockProporcional { get; set; }

		[NinjaScriptProperty]
		[Range(0.05, 1.0)]
		[Display(Name="[EXP2] Fracao do MFE p/ lock", Description="Quando UsarBELockProporcional=ON: lock = fracao * (favoravel - entrada) no momento em que o BE aciona (e a cada tick depois). PRECISA ser > 1-(TrailingPontos/BreakevenTrigPontos) [~0,53 na config padrao] p/ ter QUALQUER efeito -- abaixo disso o trailing sempre vence e a trava vira codigo morto (testado e confirmado 19/08 com 0,5). 0,75 = testa a hipotese da auditoria 18/08 de verdade.", Order=91, GroupName="10. Experimento BE-Lock Proporcional")]
		public double BELockFracaoMFE { get; set; }

		[NinjaScriptProperty]
		[Range(0, 100)]
		[Display(Name="Max trades/dia", Description="0 = sem limite (config principal); 12 = variante amarrada", Order=21, GroupName="3. Risco")]
		public int MaxTradesDia { get; set; }

		[NinjaScriptProperty]
		[Range(0, 2359)]
		[Display(Name="Sessao Inicio (HHmm ET)", Order=30, GroupName="4. Horarios")]
		public int SessaoInicio { get; set; }

		[NinjaScriptProperty]
		[Range(0, 2359)]
		[Display(Name="Entrada Fim (HHmm ET)", Order=31, GroupName="4. Horarios")]
		public int EntradaFim { get; set; }

		[NinjaScriptProperty]
		[Range(0, 2359)]
		[Display(Name="Flatten Hora (HHmm ET)", Order=32, GroupName="4. Horarios")]
		public int FlattenHora { get; set; }

		[NinjaScriptProperty]
		[Display(Name="Segunda usa range domingo-noite", Description="Na SEGUNDA usa o high/low do Globex (dom 18h -> seg 9h30) em vez da linha de sexta. Otimizado 15/06: +3 aprov/ano, aprova +rapido, OOS 100%.", Order=33, GroupName="4. Horarios")]
		public bool SegUsaDomingo { get; set; }

		[NinjaScriptProperty]
		[Range(0, 2359)]
		[Display(Name="Domingo noite inicio (HHmm ET)", Description="Inicio do range do domingo a noite (1800 = abertura do Globex)", Order=34, GroupName="4. Horarios")]
		public int DomNoiteInicio { get; set; }

		[NinjaScriptProperty]
		[Display(Name="Parar ao aprovar", Description="Para de operar ao bater a meta + min dias", Order=40, GroupName="5. Meta")]
		public bool PararAoAprovar { get; set; }

		[NinjaScriptProperty]
		[Range(0, 1000000)]
		[Display(Name="Meta lucro ($)", Description="Meta de aprovacao da conta (25K = $1.500)", Order=41, GroupName="5. Meta")]
		public double MetaLucroDolar { get; set; }

		[NinjaScriptProperty]
		[Range(0, 60)]
		[Display(Name="Min dias operados", Description="Minimo de dias p/ aprovar (Apex = 7)", Order=42, GroupName="5. Meta")]
		public int MinDiasOperados { get; set; }

		[NinjaScriptProperty]
		[Display(Name="Desenhar niveis", Description="Mostra as linhas de max/min do dia anterior no grafico", Order=50, GroupName="6. Visual")]
		public bool DesenharNiveis { get; set; }

		// ----- Estrategia noturna (Nomads Trade da Noite) -----
		[NinjaScriptProperty]
		[Display(Name="Operar noite", Description="Liga a estrategia noturna (canal Fib 19h-21h BR) junto da diurna. Acelerador: combinado 100% em ~8 dias no backtest.", Order=60, GroupName="7. Noturna")]
		public bool OperarNoite { get; set; }

		[NinjaScriptProperty]
		[Range(0, 2359)]
		[Display(Name="Noite inicio (HHmm BR)", Description="Inicio da janela noturna em horario de Brasilia (convertido p/ o fuso do grafico)", Order=61, GroupName="7. Noturna")]
		public int NoiteInicioBR { get; set; }

		[NinjaScriptProperty]
		[Range(0, 2359)]
		[Display(Name="Noite fim (HHmm BR)", Description="Nao abre novas operacoes apos esse horario de Brasilia", Order=62, GroupName="7. Noturna")]
		public int NoiteFimBR { get; set; }

		[NinjaScriptProperty]
		[Range(0, 2359)]
		[Display(Name="Noite warm-up (HHmm BR)", Description="So comeca a operar apos esse horario (canal precisa se formar)", Order=63, GroupName="7. Noturna")]
		public int NoiteWarmupBR { get; set; }

		[NinjaScriptProperty]
		[Range(0, 2359)]
		[Display(Name="Noite flatten (HHmm BR)", Description="Fecha posicao noturna remanescente nesse horario (nao carrega overnight)", Order=64, GroupName="7. Noturna")]
		public int NoiteFlattenBR { get; set; }

		[NinjaScriptProperty]
		[Range(0, 500)]
		[Display(Name="Canal minimo (pontos)", Description="So opera se o canal 19h-21h tiver pelo menos X pontos (40 = cravou 100% no backtest combinado). Evita canal raso/ruido.", Order=65, GroupName="7. Noturna")]
		public double CanalMinPontos { get; set; }

		[NinjaScriptProperty]
		[Range(0.25, 50)]
		[Display(Name="Tolerancia da linha (pontos)", Description="Distancia max do EXTREMO do canal (alta/baixa = 0%/100%) p/ a vela A contar como 'tocou a linha'. NAO usa as Fib centrais. 5pt = otimizado (100%/OOS 100%). Maior = mais trades/mais PnL.", Order=65, GroupName="7. Noturna")]
		public double LinhaToleranciaPontos { get; set; }

		[NinjaScriptProperty]
		[Range(1, 20)]
		[Display(Name="Gatilho (barras)", Description="Quantas barras (min) o bot espera a proxima romper o CORPO da vela que tocou antes de cancelar o setup (2 = j2, otimizado 17/06)", Order=66, GroupName="7. Noturna")]
		public int GatilhoBarras { get; set; }

		[NinjaScriptProperty]
		[Display(Name="Pular domingo a noite", Description="Nao opera domingo a noite (abertura do Globex = spikes/baixa liquidez). Recomendado ON: o backtest 1min superestima esses trades.", Order=67, GroupName="7. Noturna")]
		public bool PularDomingoNoite { get; set; }

		[NinjaScriptProperty]
		[Display(Name="Toque fresco", Description="So re-arma a entrada depois que o preco SAIR da zona (vela inteira fora da linha) e VOLTAR a tocar. 1 entrada por toque (menos trades, mesma qualidade). OFF = re-arma em qualquer toque (mais trades/mais PnL).", Order=68, GroupName="7. Noturna")]
		public bool ToqueFresco { get; set; }
		#endregion
	}
}
