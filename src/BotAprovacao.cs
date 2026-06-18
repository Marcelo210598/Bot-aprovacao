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
#endregion

// =============================================================================
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
//    Reversao nas extremidades do canal formado entre 19h-21h BR (Fibonacci):
//      - VENDA na zona 76,4%-100% (topo): vela TOCA a zona (sem exigir rejeicao);
//      - COMPRA na zona 0%-23,6% (fundo): idem na base;
//      - gatilho = a PROXIMA vela rompe o CORPO da que tocou (j2: ate 2 barras);
//      - filtro CANAL >= 40pt (evita canal raso/ruido — cravou 100% no combinado);
//      - MESMA gestao da diurna (SL 12,5 + BE 3,75/2,5 + trailing tick a tick).
//    Backtest combinado (diurna + noturna, mesma conta 25K): 100% aprovacao,
//    aprova em ~8 dias (vs 14 da diurna so), +33% PnL/ano, OOS 100%/100%.
//    Horario 19h-21h convertido de BR p/ o fuso do grafico (imune ao DST dos EUA).
//    A NOTURNA e ACELERADOR da diurna — sozinha e fraca (~89%). Forward test antes do real.
// =============================================================================

namespace NinjaTrader.NinjaScript.Strategies
{
	public class BotAprovacao : Strategy
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

		// ---------- Kill switch / controle diario ----------
		private string diaCorrente = "";
		private double pnlInicioDia = 0;
		private bool   bloqueadoHoje = false;

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

		// Vela de 5min SINTETICA (a noturna opera em 5min, agregando as barras de 1min do grafico)
		private double n5o = 0, n5h = 0, n5l = 0, n5c = 0;
		private bool   n5Ativo = false;               // ha bucket de 5min em formacao?

		private const double FIB_VENDA  = 0.764; // zona de venda: 76,4%-100%
		private const double FIB_COMPRA = 0.236; // zona de compra: 0%-23,6%

		protected override void OnStateChange()
		{
			if (State == State.SetDefaults)
			{
				Description					= @"Bot de aprovacao Apex (Niveis 94): reversao na max/min do dia anterior. 5 MNQ, tol 20 ticks. Trailing gerenciado no codigo.";
				Name						= "BotAprovacao";
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

				StopDiarioDolar		= 750.0;
				MaxTradesDia		= 0;

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
				OperarNoite			= true;    // toggle: liga a noturna junto da diurna
				NoiteInicioBR		= 1900;    // 19h00 Brasilia
				NoiteFimBR			= 2100;    // 21h00 Brasilia (nao abre depois)
				NoiteWarmupBR		= 1915;    // so opera apos 19h15 (canal precisa formar)
				NoiteFlattenBR		= 2200;    // flatten de seguranca 22h BR (nao carrega overnight)
				CanalMinPontos		= 40.0;    // canal minimo: cravou 100% + OOS 100%/100% no combinado
				GatilhoBarras		= 2;       // janela (barras) p/ a proxima romper o CORPO da vela que tocou (j2)
				PularDomingoNoite	= true;    // domingo a noite = abertura do Globex (spikes), nao opera
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
				pnlInicioDia  = RealizadoAcumulado();
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
			if (mp == MarketPosition.Flat) { stopIntrabarEnviado = false; return; }
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
			}

			double preco = e.Price;

			// 1) Pico a favor + SOBE o stop (breakeven -> trailing) a cada tick. Sempre monotonico
			//    (so aperta, nunca afrouxa) — garante lucro travado numa reversao.
			if (isLong)
			{
				favPrice = Math.Max(favPrice, preco);
				if (!beFeito && (favPrice - entryPrice) >= BreakevenTrigPontos)
				{
					beFeito = true;
					stopPrice = Math.Max(stopPrice, entryPrice + BreakevenLockPontos);
				}
				if (beFeito)
					stopPrice = Math.Max(stopPrice, Math.Max(entryPrice + BreakevenLockPontos, favPrice - TrailingPontos));
			}
			else
			{
				favPrice = Math.Min(favPrice, preco);
				if (!beFeito && (entryPrice - favPrice) >= BreakevenTrigPontos)
				{
					beFeito = true;
					stopPrice = Math.Min(stopPrice, entryPrice - BreakevenLockPontos);
				}
				if (beFeito)
					stopPrice = Math.Min(stopPrice, Math.Min(entryPrice - BreakevenLockPontos, favPrice + TrailingPontos));
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
					tradeSeq++;
					sinalAtivo = "NIV_S" + tradeSeq;
					origemAtual = "D";
					// Stop no servidor (protege intrabar) — sem SetProfitTarget = sem OCO
					SetStopLoss(sinalAtivo, CalculationMode.Ticks, StopPontos / TickSize, false);
					EnterShort(Contratos, sinalAtivo);
					Print(string.Format("{0}  >>> SHORT @ {1:F2}  | tocou Max {2:F2} {6} (H={3:F2}, dist {4:F2}pt) e FECHOU ABAIXO (C={5:F2})",
						Time[0], c, nHi, h, distPontos, c, src));
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
					tradeSeq++;
					sinalAtivo = "NIV_L" + tradeSeq;
					origemAtual = "D";
					// Stop no servidor (protege intrabar) — sem SetProfitTarget = sem OCO
					SetStopLoss(sinalAtivo, CalculationMode.Ticks, StopPontos / TickSize, false);
					EnterLong(Contratos, sinalAtivo);
					Print(string.Format("{0}  >>> LONG @ {1:F2}  | tocou Min {2:F2} {6} (L={3:F2}, dist {4:F2}pt) e FECHOU ACIMA (C={5:F2})",
						Time[0], c, nLo, l, distPontos, c, src));
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

		// A NOTURNA OPERA EM 5 MINUTOS (a diurna fica em 1min). Em vez de adicionar uma 2a serie
		// (multi-serie do NT = roteamento de ordem chato), agregamos as barras de 1min do grafico
		// em velas de 5min SINTETICAS e so avaliamos o canal/gatilho quando a vela de 5min FECHA.
		// Fiel ao backtest 'misto' (run_noturna_5min.py): combinado 100% (23/23), OOS 100%/100%.
		// Gatilho = a proxima vela de 5min rompe o CORPO da que tocou a zona (j2, sem exigir rejeicao).
		private void ProcessaNoturna()
		{
			int brAgora    = HoraBR(Time[0]);
			DateTime emBr  = EmBR(Time[0]);
			string brDia   = emBr.ToString("yyyy-MM-dd");
			bool naJanela  = brAgora >= NoiteInicioBR && brAgora < NoiteFimBR;

			// Domingo a noite = ABERTURA do Globex (spikes/baixa liquidez). Nao operamos. (PularDomingoNoite)
			if (PularDomingoNoite && emBr.DayOfWeek == DayOfWeek.Sunday) { pendLado = 0; n5Ativo = false; return; }

			// Flatten de seguranca pos-sessao (so fecha posicao NOTURNA) — checado a cada barra de 1min
			if (brAgora >= NoiteFlattenBR && Position.MarketPosition != MarketPosition.Flat && origemAtual == "N")
			{
				FechaPosicao("FlattenNoite");
				return;
			}

			if (!naJanela) { pendLado = 0; n5Ativo = false; return; }

			// ----- Agrega 1min -> vela de 5min sintetica (alinhada :00/:05/:10...) -----
			// minuto do relogio: offset de fuso e sempre hora cheia, entao Minute % 5 independe do fuso.
			if (!n5Ativo) { n5o = Open[0]; n5h = High[0]; n5l = Low[0]; n5Ativo = true; }
			else { n5h = Math.Max(n5h, High[0]); n5l = Math.Min(n5l, Low[0]); }
			n5c = Close[0];
			if (Time[0].Minute % 5 != 0) return;   // vela de 5min ainda nao fechou
			n5Ativo = false;                        // proxima barra inicia bucket novo

			// ===== vela de 5min recem-fechada: n5o/n5h/n5l/n5c =====
			// 1) Atualiza o canal da sessao noturna com a vela de 5min
			if (brDia != noiteDia)
			{
				noiteDia = brDia; noiteHigh = n5h; noiteLow = n5l;
				pendLado = 0; notTradesDia = 0;
				Print(string.Format("{0}  [NOITE 5min] janela {1:D4}-{2:D4} BR aberta | grafico {3:HH:mm} = BR {4:HH:mm}",
					Time[0], NoiteInicioBR, NoiteFimBR, Time[0], EmBR(Time[0])));
			}
			else
			{
				noiteHigh = Math.Max(noiteHigh, n5h);
				noiteLow  = Math.Min(noiteLow,  n5l);
			}

			if (noiteHigh > 0)
				DesenhaCanalNoturno(noiteHigh - noiteLow);

			// 2) So opera apos warm-up, com canal valido e sem posicao aberta
			if (brAgora < NoiteWarmupBR || noiteHigh <= 0) return;
			double canal = noiteHigh - noiteLow;
			if (canal < CanalMinPontos) return;
			if (aprovado || bloqueadoHoje) return;
			if (Position.MarketPosition != MarketPosition.Flat) return;

			double zVenda  = noiteLow + FIB_VENDA  * canal;   // 76,4% (topo da zona de venda)
			double zCompra = noiteLow + FIB_COMPRA * canal;   // 23,6% (topo da zona de compra)
			double h = n5h, l = n5l, c = n5c, o = n5o;

			// 3) Aciona setup pendente: a proxima vela de 5min rompeu o CORPO da que tocou (ate GatilhoBarras)?
			if (pendLado != 0)
			{
				if (pendLado == -1 && l <= pendNivel) { EntraNoturna(-1, canal); return; }
				if (pendLado ==  1 && h >= pendNivel) { EntraNoturna( 1, canal); return; }
				pendRestantes--;
				if (pendRestantes <= 0) pendLado = 0;
				return;   // enquanto ha setup pendente, nao arma outro
			}

			// 4) Vela de 5min TOCA a zona (sem exigir rejeicao) -> arma; gatilho = rompimento do CORPO.
			//    O corpo (min/max de open,close) fica ACIMA do pavio -> venda entra mais cedo/mais alto.
			if (h >= zVenda)
			{
				pendLado = -1; pendNivel = Math.Min(o, c); pendRestantes = GatilhoBarras;   // venda: rompe corpo inferior
			}
			else if (l <= zCompra)
			{
				pendLado = 1; pendNivel = Math.Max(o, c); pendRestantes = GatilhoBarras;    // compra: rompe corpo superior
			}
		}

		// Entrada noturna a mercado no fechamento da barra que rompeu o corpo.
		// Reusa a mesma gestao da diurna: stop no servidor + trailing tick a tick (OnMarketData).
		private void EntraNoturna(int lado, double canal)
		{
			tradeSeq++;
			sinalAtivo  = (lado == -1 ? "NOT_S" : "NOT_L") + tradeSeq;
			origemAtual = "N";
			notTradesDia++;
			pendLado = 0;
			SetStopLoss(sinalAtivo, CalculationMode.Ticks, StopPontos / TickSize, false);
			if (lado == -1) EnterShort(Contratos, sinalAtivo);
			else            EnterLong(Contratos, sinalAtivo);
			Print(string.Format("{0}  >>> NOITE {1} @ {2:F2} | canal {3:F1}pt [{4:F2}-{5:F2}] | rompeu corpo {6:F2}",
				Time[0], lado == -1 ? "SHORT" : "LONG", Close[0], canal, noiteLow, noiteHigh, pendNivel));
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
					// Move stop servidor para nivel de breakeven — garante lucro minimo intrabar.
					// Em recovery (sem signal original), atualiza todos os stops da estrategia.
					if (!string.IsNullOrEmpty(sinalAtivo) && sinalAtivo != "RECOVERY")
						SetStopLoss(sinalAtivo, CalculationMode.Price, entryPrice + BreakevenLockPontos, false);
					// em recovery: server stop anterior ainda protege; trailing sintetico gerencia a saida
				}
				if (beFeito)
					stopPrice = Math.Max(stopPrice, Math.Max(entryPrice + BreakevenLockPontos, favPrice - TrailingPontos));
			}
			else
			{
				favPrice = Math.Min(favPrice, Low[0]);
				if (!beFeito && (entryPrice - favPrice) >= BreakevenTrigPontos)
				{
					beFeito = true;
					// Move stop servidor para nivel de breakeven — garante lucro minimo intrabar.
					if (!string.IsNullOrEmpty(sinalAtivo) && sinalAtivo != "RECOVERY")
						SetStopLoss(sinalAtivo, CalculationMode.Price, entryPrice - BreakevenLockPontos, false);
					// em recovery: server stop anterior ainda protege; trailing sintetico gerencia a saida
				}
				if (beFeito)
					stopPrice = Math.Min(stopPrice, Math.Min(entryPrice - BreakevenLockPontos, favPrice + TrailingPontos));
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

			double topo  = noiteHigh;                       // 100% (zona de venda)
			double fundo = noiteLow;                        // 0%   (zona de compra)
			double z764  = fundo + FIB_VENDA  * canal;      // 76,4%
			double z236  = fundo + FIB_COMPRA * canal;      // 23,6%

			bool valido = canal >= CanalMinPontos;          // laranja forte = opera; cinza = canal raso (so observa)
			Brush corCanal = valido ? Brushes.DarkOrange : Brushes.Gray;

			Draw.HorizontalLine(this, "NoiteTopo",  topo,  corCanal,     DashStyleHelper.Solid, 2);
			Draw.HorizontalLine(this, "NoiteFundo", fundo, corCanal,     DashStyleHelper.Solid, 2);
			Draw.HorizontalLine(this, "NoiteZ764",  z764,  Brushes.Gold, DashStyleHelper.Dot,   1);
			Draw.HorizontalLine(this, "NoiteZ236",  z236,  Brushes.Gold, DashStyleHelper.Dot,   1);

			Draw.TextFixed(this, "statusNoite",
				"Canal NOITE (19h-21h BR): " + canal.ToString("F1") + "pt " + (valido ? "(operando)" : "(< minimo, so observa)") + "\n" +
				"  Topo (venda 76,4-100%):  " + topo.ToString("F2") + " / " + z764.ToString("F2") + "\n" +
				"  Fundo (compra 0-23,6%):  " + fundo.ToString("F2") + " / " + z236.ToString("F2"),
				TextPosition.BottomRight);
		}

		private void FechaPosicao(string motivo)
		{
			if (Position.MarketPosition == MarketPosition.Flat) return;
			Print(string.Format("{0}  <<< SAIDA [{1}] | {2} {3} | entrada {4:F2} ~saida {5:F2} | fav {6:F2} | BE={7}",
				Time[0], motivo, Position.MarketPosition, sinalAtivo, entryPrice, Close[0], favPrice, beFeito ? "sim" : "nao"));
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
		[Range(0, 100000)]
		[Display(Name="Stop diario ($)", Description="Para de operar no dia ao perder esse valor (0 = desliga)", Order=20, GroupName="3. Risco")]
		public double StopDiarioDolar { get; set; }

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
		[Range(1, 20)]
		[Display(Name="Gatilho (barras)", Description="Quantas barras (min) o bot espera a proxima romper o CORPO da vela que tocou antes de cancelar o setup (2 = j2, otimizado 17/06)", Order=66, GroupName="7. Noturna")]
		public int GatilhoBarras { get; set; }

		[NinjaScriptProperty]
		[Display(Name="Pular domingo a noite", Description="Nao opera domingo a noite (abertura do Globex = spikes/baixa liquidez). Recomendado ON: o backtest 1min superestima esses trades.", Order=67, GroupName="7. Noturna")]
		public bool PularDomingoNoite { get; set; }
		#endregion
	}
}
