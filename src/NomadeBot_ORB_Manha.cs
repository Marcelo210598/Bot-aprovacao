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
//  NomadeBot_ORB_Manha  —  Opening Range Breakout 15min (9h30-9h45 ET) p/ MNQ
// -----------------------------------------------------------------------------
//  Segundo modulo INDEPENDENTE da familia Nomade Trader — roda junto com o
//  NomadeTraderNoite (19h-21h BRT) e o BotAprovacao (diurna, niveis). Este opera
//  na ABERTURA de Nova York, sessao separada (9h30-10h30 ET), sem conflito de
//  horario com os outros dois.
//
//  ⚠️ VALIDADO POR BACKTEST REAL — NAO pelos numeros de blog/YouTube que
//  circulam pra ORB (tipo "433%/ano", "WR 65-78%"). Rodamos em
//  backtest/run_orb_15min.py sobre ~1 ano de dados 1min REAIS do NQ (12/08/2026)
//  e o resultado foi bem mais modesto que a propaganda:
//
//    ORB "cru" (sem filtro de range): PF 0.58, WR 24% — PERDE DINHEIRO.
//    A claim de "433%/ano" NAO se sustentou nos dados reais — trate qualquer
//    numero de estrategia achado na internet como achismo ate backtestar.
//
//  Config validada (a que este bot usa por padrao):
//    - Filtro de range 15-80pt no ORB — ESSENCIAL. Sem ele, ate com EMA200 o
//      resultado ainda perde (PF 0.86). Com ele, PF sobe pra 1.90.
//    - Filtro de tendencia EMA200 no grafico de 1h — o filtro que MAIS ajudou
//      isolado (PF 1.08 -> 1.34). So entra a favor da tendencia horaria.
//    - Confirmacao: exige que o candle SEGUINTE ao rompimento nao reverta
//      pra dentro do range antes de entrar (reduz falso rompimento).
//    - SL 12,5pt / TP 37,5pt (3x, mesmo SL da diurna) -> PF 1.90, OOS 1.72|2.19
//      (robusto nas duas metades do periodo testado).
//    - Reteste (esperar puxada de volta pra linha em vez de entrar no rompimento)
//      TESTADO e REJEITADO: piora o resultado (PF 0.96 vs 1.90 do breakout direto).
//    - Filtro de VWAP TESTADO e REJEITADO: no backtest ele NUNCA bloqueou um
//      unico trade no ano inteiro (rompimento do ORB ja nasce do lado certo do
//      VWAP quase sempre) — redundante, deixado como opcao mas OFF por padrao.
//    - Filtro de noticias (CPI/NFP as 8h30 ET): sem calendario de dados pra
//      backtestar de forma real. Mitigacao indireta: o filtro de range MAXIMO
//      (80pt) ja descarta a maioria dos dias com abertura violenta/distorcida.
//
//  Resultado validado (config acima, ~1 ano real, 5 MNQ): ~46 trades/ano
//  (~3-4/mes), WR 43,5%, PF 1.90, net +$2.766/ano. É uma EDGE REAL mas MODESTA —
//  NAO e "a solucao" pros dias zerados da diurna sozinha, e um COMPLEMENTO que
//  adiciona uns 3-4 dias de trade/mes que a diurna nao teria. Nao esperar mais
//  que isso sem novo backtest.
//
//  Regras Apex seguidas: Calculate=OnBarClose (sem HFT); SL/TP via bracket no
//  SERVIDOR (SetStopLoss+SetProfitTarget — protecao intrabar sem ser HFT); sem
//  overnight (flatten as 10h30 ET, muito antes do fechamento diario real);
//  max 2 trades/sessao (configuravel); kill switch diario em $ (proprio e,
//  opcionalmente, GLOBAL combinado com os outros bots via arquivo compartilhado).
// =============================================================================

namespace NinjaTrader.NinjaScript.Strategies
{
	public class NomadeBot_ORB_Manha : Strategy
	{
		// ---------- Range de abertura (ORB 9h30-9h45 ET) ----------
		private double orbHi = 0, orbLo = 0;
		private bool   orbPronto = false;

		// ---------- Estado de entrada (confirmacao / reteste) ----------
		private bool   aguardandoConfirm = false;
		private int    ladoPendente = 0;      // +1 = long pendente, -1 = short pendente, 0 = nada
		private bool   aguardandoRetest = false;

		// ---------- VWAP manual (sessao RTH, reset a cada dia) ----------
		private double vwapNum = 0, vwapDen = 0;

		// ---------- Controle diario ----------
		private string diaCorrente = "";
		private int    tradesSessao = 0;
		private double pnlInicioDia = 0;
		private bool   bloqueadoHoje = false;
		private double pnlPreRestartDia = 0;

		// ---------- Sinal / execucao ----------
		private int    tradeSeq = 0;
		private string sinalAtivo = "";

		// ---------- Fuso (mesmo padrao fuso-proof do BotAprovacao) ----------
		private TimeZoneInfo etTz = null;
		private TimeZoneInfo graficoTz = null;

		protected override void OnStateChange()
		{
			if (State == State.SetDefaults)
			{
				Description	= @"ORB 15min (9h30-9h45 ET) p/ MNQ. Modulo independente, roda junto com NomadeTraderNoite/BotAprovacao. Config validada por backtest real (ver backtest/run_orb_15min.py) -- nao pelos numeros de blog.";
				Name							= "NomadeBot_ORB_Manha";
				Calculate						= Calculate.OnBarClose;
				EntriesPerDirection				= 1;
				EntryHandling					= EntryHandling.AllEntries;
				IsExitOnSessionCloseStrategy	= true;
				ExitOnSessionCloseSeconds		= 30;
				IsFillLimitOnTouch				= false;
				MaximumBarsLookBack				= MaximumBarsLookBack.TwoHundredFiftySix;
				OrderFillResolution				= OrderFillResolution.Standard;
				Slippage						= 0;
				StartBehavior					= StartBehavior.AdoptAccountPosition;
				TimeInForce						= TimeInForce.Gtc;
				TraceOrders						= false;
				RealtimeErrorHandling			= RealtimeErrorHandling.IgnoreAllErrors;
				StopTargetHandling				= StopTargetHandling.PerEntryExecution;
				BarsRequiredToTrade				= 20;
				IsInstantiatedOnEachOptimizationIteration = true;

				Contratos			= 5;

				ORBInicioET			= 930;    // 9h30 ET -- abertura de NY
				ORBFimET			= 945;    // 9h45 ET -- range trava aqui
				FlattenET			= 1030;   // 10h30 ET -- so opera 1h apos o range fechar

				RangeMinPontos		= 15.0;   // range < 15pt = ignora (ruido, sem direcao)
				RangeMaxPontos		= 80.0;   // range > 80pt = ignora (dia distorcido/noticia) -- ESSENCIAL, ver header
				MaxTradesSessao		= 2;

				ExigeConfirmacao	= true;   // candle seguinte precisa NAO reverter -- validado, manter ON
				UsaReteste			= false;  // testado e REJEITADO (piora PF 1.90->0.96) -- deixado como opcao, default OFF

				UsaFiltroEMA200		= true;   // o filtro que mais ajudou isolado -- manter ON
				PeriodoEMA200		= 200;

				UsaFiltroVWAP		= false;  // testado e REJEITADO (redundante, 0 trades bloqueados no ano) -- default OFF

				StopPontos			= 12.5;   // mesmo SL da diurna (BotAprovacao)
				AlvoPontos			= 37.5;   // 3x o stop -- validado (PF 1.90, OOS 1.72|2.19)

				StopDiarioDolar			= 300.0;   // kill switch PROPRIO deste bot
				UsaKillSwitchGlobal		= false;   // OFF por padrao -- ligar so depois de configurar os outros bots p/ escrever no mesmo arquivo (ver docs)
				StopDiarioGlobalDolar	= 750.0;   // limite COMBINADO (manha + noite), mesmo valor do StopDiarioDolar da diurna

				DesenharNiveis		= true;
			}
			else if (State == State.Configure)
			{
				AddDataSeries(BarsPeriodType.Minute, 60);   // BarsArray[1] -- serie auxiliar p/ EMA200(1h)
			}
			else if (State == State.DataLoaded)
			{
				try { etTz = TimeZoneInfo.FindSystemTimeZoneById("Eastern Standard Time"); }
				catch { etTz = null; }
				graficoTz = ResolveFusoGrafico();

				if (graficoTz != null)
					Print(string.Format("[ORB_Manha] Fuso do grafico detectado: {0} — convertendo p/ ET automaticamente.", graficoTz.Id));
				else
					Print("[ORB_Manha] AVISO: nao consegui detectar o fuso do grafico — assumindo ET (config classica).");
			}
			else if (State == State.Realtime)
			{
				Print(string.Format("{0}  ✅ ORB_MANHA AO VIVO — entradas a partir daqui sao REAIS (ordens enviadas ao broker).", Time[0]));

				string hojeLocal = EmET(Time[0]).ToString("yyyy-MM-dd");
				pnlPreRestartDia = CarregaPnlDiario(hojeLocal);
				if (Math.Abs(pnlPreRestartDia) > 0.01)
					Print(string.Format("{0}  ⚠️ ANTI-RESET: PnL ja realizado hoje antes do restart = ${1:F2} — stop diario continua de onde parou.",
						Time[0], pnlPreRestartDia));
			}
		}

		protected override void OnBarUpdate()
		{
			// BarsInProgress==1 e a serie auxiliar de 1h (so alimenta o EMA200) -- nao processa logica aqui.
			if (BarsInProgress != 0) return;
			if (CurrentBars[0] < BarsRequiredToTrade) return;
			if (UsaFiltroEMA200 && CurrentBars[1] < PeriodoEMA200) return;   // EMA200(1h) ainda esquentando -- sem trade ate ter historico suficiente

			DateTime tEt = EmET(Time[0]);
			int agora = tEt.Hour * 100 + tEt.Minute;
			string hoje = tEt.ToString("yyyy-MM-dd");

			// ---------------- Virada de dia: reseta tudo ----------------
			if (hoje != diaCorrente)
			{
				diaCorrente			= hoje;
				bloqueadoHoje		= false;
				tradesSessao		= 0;
				orbHi = 0; orbLo = 0; orbPronto = false;
				aguardandoConfirm	= false; aguardandoRetest = false; ladoPendente = 0;
				vwapNum = 0; vwapDen = 0;
				pnlInicioDia		= RealizadoAcumulado() - pnlPreRestartDia;
				pnlPreRestartDia	= 0;
			}

			// ---------------- Formacao do range 9h30-9h45 ET ----------------
			if (agora >= ORBInicioET && agora < ORBFimET)
			{
				orbHi = orbHi == 0 ? High[0] : Math.Max(orbHi, High[0]);
				orbLo = orbLo == 0 ? Low[0]  : Math.Min(orbLo,  Low[0]);
			}
			else if (agora >= ORBFimET && !orbPronto && orbHi > 0)
			{
				orbPronto = true;
				Print(string.Format("{0}  [ORB] range formado: topo {1:F2} | fundo {2:F2} | tamanho {3:F2}pt{4}",
					Time[0], orbHi, orbLo, orbHi - orbLo,
					(orbHi - orbLo < RangeMinPontos || orbHi - orbLo > RangeMaxPontos) ? " -- FORA do filtro, dia sem operacao" : ""));
			}

			// ---------------- VWAP manual (sessao RTH, so pra quem usa o filtro) ----------------
			if (UsaFiltroVWAP && agora >= ORBInicioET)
			{
				double tp = (High[0] + Low[0] + Close[0]) / 3.0;
				vwapNum += tp * Volume[0]; vwapDen += Volume[0];
			}

			DesenhaNiveis();

			// ---------------- Kill switch diario (proprio) ----------------
			double pnlDia = RealizadoAcumulado() - pnlInicioDia + UnrealizadoPiorCaso();
			if (StopDiarioDolar > 0 && pnlDia <= -StopDiarioDolar)
			{
				if (!bloqueadoHoje)
					Print(string.Format("{0}  🛑 STOP DIARIO ORB atingido (${1:F2}) — sem novas entradas hoje.", Time[0], pnlDia));
				bloqueadoHoje = true;
				if (Position.MarketPosition != MarketPosition.Flat) FechaPosicao("StopDiario");
			}

			// ---------------- Kill switch GLOBAL (combinado com outros bots, opcional) ----------------
			if (UsaKillSwitchGlobal)
			{
				double pnlGlobalDia = CarregaPnlGlobalOutros(hoje) + (RealizadoAcumulado() - pnlInicioDia) + UnrealizadoPiorCaso();
				if (StopDiarioGlobalDolar > 0 && pnlGlobalDia <= -StopDiarioGlobalDolar)
				{
					if (!bloqueadoHoje)
						Print(string.Format("{0}  🛑 KILL SWITCH GLOBAL atingido (${1:F2} combinado com outros bots) — sem novas entradas hoje.", Time[0], pnlGlobalDia));
					bloqueadoHoje = true;
					if (Position.MarketPosition != MarketPosition.Flat) FechaPosicao("KillSwitchGlobal");
				}
			}

			// Persiste o PnL do dia (proprio bot) a cada barra ao vivo -- anti-reset e insumo p/ o kill switch global dos OUTROS bots.
			if (State == State.Realtime && !string.IsNullOrEmpty(diaCorrente))
				SalvaPnlDiario(RealizadoAcumulado() - pnlInicioDia, diaCorrente);

			// ---------------- Flatten forcado (10h30 ET -- sem overnight, sem duvida) ----------------
			if (agora >= FlattenET)
			{
				if (Position.MarketPosition != MarketPosition.Flat) FechaPosicao("FlattenORB");
				return;
			}

			// ---------------- Entrada ----------------
			if (bloqueadoHoje || Position.MarketPosition != MarketPosition.Flat) return;
			if (!orbPronto) return;
			if (MaxTradesSessao > 0 && tradesSessao >= MaxTradesSessao) return;

			double range = orbHi - orbLo;
			if (range < RangeMinPontos || range > RangeMaxPontos) return;

			int lado = 0;

			if (!UsaReteste)
			{
				// --- BREAKOUT + confirmacao opcional (candle seguinte nao pode reverter) ---
				if (aguardandoConfirm)
				{
					if (ladoPendente > 0 && Close[0] > orbHi) lado = 1;
					else if (ladoPendente < 0 && Close[0] < orbLo) lado = -1;
					aguardandoConfirm = false; ladoPendente = 0;
				}
				else if (Close[0] > orbHi)
				{
					if (ExigeConfirmacao) { aguardandoConfirm = true; ladoPendente = 1; return; }
					lado = 1;
				}
				else if (Close[0] < orbLo)
				{
					if (ExigeConfirmacao) { aguardandoConfirm = true; ladoPendente = -1; return; }
					lado = -1;
				}
			}
			else
			{
				// --- RETESTE: aguarda rompimento, depois puxada de volta a linha e rejeicao ---
				if (!aguardandoRetest)
				{
					if (Close[0] > orbHi) { aguardandoRetest = true; ladoPendente = 1; return; }
					if (Close[0] < orbLo) { aguardandoRetest = true; ladoPendente = -1; return; }
				}
				else if (ladoPendente > 0)
				{
					if (Low[0] <= orbHi && Close[0] > orbHi) lado = 1;
					else if (Close[0] < orbLo) { aguardandoRetest = false; ladoPendente = 0; }
				}
				else
				{
					if (High[0] >= orbLo && Close[0] < orbLo) lado = -1;
					else if (Close[0] > orbHi) { aguardandoRetest = false; ladoPendente = 0; }
				}
				if (lado != 0) { aguardandoRetest = false; ladoPendente = 0; }
			}

			if (lado == 0) return;

			if (UsaFiltroEMA200)
			{
				double emaVal = EMA(BarsArray[1], PeriodoEMA200)[0];
				if (lado > 0 && Close[0] <= emaVal) { Print(string.Format("{0}  rompimento LONG bloqueado — Close {1:F2} <= EMA200(1h) {2:F2}", Time[0], Close[0], emaVal)); return; }
				if (lado < 0 && Close[0] >= emaVal) { Print(string.Format("{0}  rompimento SHORT bloqueado — Close {1:F2} >= EMA200(1h) {2:F2}", Time[0], Close[0], emaVal)); return; }
			}
			if (UsaFiltroVWAP && vwapDen > 0)
			{
				double vwapVal = vwapNum / vwapDen;
				if (lado > 0 && Close[0] <= vwapVal) { Print(string.Format("{0}  rompimento LONG bloqueado — Close {1:F2} <= VWAP {2:F2}", Time[0], Close[0], vwapVal)); return; }
				if (lado < 0 && Close[0] >= vwapVal) { Print(string.Format("{0}  rompimento SHORT bloqueado — Close {1:F2} >= VWAP {2:F2}", Time[0], Close[0], vwapVal)); return; }
			}

			tradeSeq++;
			sinalAtivo = "ORB_" + tradeSeq;
			tradesSessao++;

			SetStopLoss(sinalAtivo, CalculationMode.Ticks, StopPontos / TickSize, false);
			SetProfitTarget(sinalAtivo, CalculationMode.Ticks, AlvoPontos / TickSize);

			if (lado > 0)
			{
				EnterLong(Contratos, sinalAtivo);
				Print(string.Format("{0}  >>> LONG {1} @ {2:F2} | rompeu topo ORB {3:F2} (range {4:F2}pt) | SL ~{5:F2} TP ~{6:F2}",
					Time[0], sinalAtivo, Close[0], orbHi, range, Close[0] - StopPontos, Close[0] + AlvoPontos));
			}
			else
			{
				EnterShort(Contratos, sinalAtivo);
				Print(string.Format("{0}  >>> SHORT {1} @ {2:F2} | rompeu fundo ORB {3:F2} (range {4:F2}pt) | SL ~{5:F2} TP ~{6:F2}",
					Time[0], sinalAtivo, Close[0], orbLo, range, Close[0] + StopPontos, Close[0] - AlvoPontos));
			}
		}

		// ---------------- Fecha posicao (kill switch / flatten -- SL/TP normais saem sozinhos pelo bracket) ----------------
		private void FechaPosicao(string motivo)
		{
			if (Position.MarketPosition == MarketPosition.Flat) return;
			Print(string.Format("{0}  <<< SAIDA FORCADA [{1}] | {2} {3} @ ~{4:F2}",
				Time[0], motivo, Position.MarketPosition, sinalAtivo, Close[0]));
			bool semSignal = string.IsNullOrEmpty(sinalAtivo);
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

		// ---------------- Desenho no grafico: topo verde, fundo vermelho ----------------
		private void DesenhaNiveis()
		{
			if (!DesenharNiveis || orbHi == 0) return;
			Draw.HorizontalLine(this, "ORB_Topo",  orbHi, Brushes.LimeGreen, DashStyleHelper.Solid, 2);
			Draw.HorizontalLine(this, "ORB_Fundo", orbLo, Brushes.Red,       DashStyleHelper.Solid, 2);
			Draw.TextFixed(this, "statusORB",
				string.Format("ORB 9h30-9h45 ET: topo {0:F2} | fundo {1:F2} | range {2:F2}pt | trades hoje {3}/{4}",
					orbHi, orbLo, orbHi - orbLo, tradesSessao, MaxTradesSessao),
				TextPosition.BottomRight);
		}

		// ---------------- Fuso (mesmo padrao fuso-proof do BotAprovacao) ----------------
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
			return DateTime.MinValue;
		}

		private DateTime EmET(DateTime t)
		{
			DateTime et = EmFuso(t, etTz);
			return et != DateTime.MinValue ? et : t;   // fallback: assume grafico ja em ET
		}

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
					catch { continue; }
					foreach (var t in tipos)
					{
						if (t.Name != "Globals") continue;
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

		// ---------------- PnL / performance ----------------
		private double RealizadoAcumulado()
		{
			try { return SystemPerformance?.AllTrades?.TradesPerformance?.Currency?.CumProfit ?? 0; }
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

		// ---- Persistencia do PnL diario PROPRIO (anti-reset, mesmo padrao do BotAprovacao) ----
		private string CaminhoArquivoPnl()
		{
			return Path.Combine(
				Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData),
				"NinjaTrader 8", "NomadeBot_ORB_Manha_pnl_diario.txt");
		}

		private void SalvaPnlDiario(double pnlRealizado, string data)
		{
			try { File.WriteAllText(CaminhoArquivoPnl(), data + ":" + pnlRealizado.ToString("F2", CultureInfo.InvariantCulture)); }
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
				if (s.Substring(0, sep) != hoje) return 0;
				return double.Parse(s.Substring(sep + 1), CultureInfo.InvariantCulture);
			}
			catch { return 0; }
		}

		// ---- Kill switch GLOBAL: soma o PnL do dia que OS OUTROS BOTS gravaram no proprio arquivo ----
		// (BotAprovacao_pnl_diario.txt e NomadeTraderNoite_pnl_diario.txt, mesmo formato "yyyy-MM-dd:valor").
		// Precisa que os outros bots tambem gravem PnL diario (BotAprovacao ja grava; NomadeTraderNoite
		// ver nota em docs/melhorias-sugeridas.md #11 se ainda nao gravar). Se o arquivo nao existir ou
		// for de outro dia, conta como $0 (nao trava por falta de dado).
		private double CarregaPnlGlobalOutros(string hoje)
		{
			double soma = 0;
			string pasta = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData), "NinjaTrader 8");
			string[] arquivos = { "BotAprovacao_pnl_diario.txt", "NomadeTraderNoite_pnl_diario.txt" };
			foreach (var nome in arquivos)
			{
				try
				{
					string path = Path.Combine(pasta, nome);
					if (!File.Exists(path)) continue;
					string s = File.ReadAllText(path).Trim();
					int sep = s.IndexOf(':');
					if (sep < 0) continue;
					if (s.Substring(0, sep) != hoje) continue;
					soma += double.Parse(s.Substring(sep + 1), CultureInfo.InvariantCulture);
				}
				catch { }
			}
			return soma;
		}

		#region Propriedades

		[NinjaScriptProperty]
		[Range(1, 100)]
		[Display(Name = "Contratos", Order = 1, GroupName = "1. Geral")]
		public int Contratos { get; set; }

		[NinjaScriptProperty]
		[Range(0, 2359)]
		[Display(Name = "ORB Inicio (HHmm ET)", Description = "Inicio do range de abertura (padrao 9h30 ET)", Order = 10, GroupName = "2. ORB")]
		public int ORBInicioET { get; set; }

		[NinjaScriptProperty]
		[Range(0, 2359)]
		[Display(Name = "ORB Fim (HHmm ET)", Description = "Fim da formacao do range -- trava aqui (padrao 9h45 ET)", Order = 11, GroupName = "2. ORB")]
		public int ORBFimET { get; set; }

		[NinjaScriptProperty]
		[Range(0, 2359)]
		[Display(Name = "Flatten (HHmm ET)", Description = "Fecha tudo e para de operar (padrao 10h30 ET -- so opera 1h)", Order = 12, GroupName = "2. ORB")]
		public int FlattenET { get; set; }

		[NinjaScriptProperty]
		[Range(0, 500)]
		[Display(Name = "Range minimo (pontos)", Description = "Range menor que isso = ignora o dia (sem direcao). Validado: 15pt", Order = 13, GroupName = "2. ORB")]
		public double RangeMinPontos { get; set; }

		[NinjaScriptProperty]
		[Range(0, 500)]
		[Display(Name = "Range maximo (pontos)", Description = "Range maior que isso = ignora o dia (distorcido/noticia). Validado: 80pt -- ESSENCIAL, nao desligar", Order = 14, GroupName = "2. ORB")]
		public double RangeMaxPontos { get; set; }

		[NinjaScriptProperty]
		[Range(0, 10)]
		[Display(Name = "Max trades/sessao", Description = "0 = sem limite. Regra Apex: max 2", Order = 15, GroupName = "2. ORB")]
		public int MaxTradesSessao { get; set; }

		[NinjaScriptProperty]
		[Display(Name = "Exige confirmacao", Description = "Candle seguinte ao rompimento precisa NAO reverter pra dentro do range. Validado ON.", Order = 20, GroupName = "3. Entrada")]
		public bool ExigeConfirmacao { get; set; }

		[NinjaScriptProperty]
		[Display(Name = "Usa reteste (em vez de breakout)", Description = "Espera puxada de volta a linha em vez de entrar no rompimento direto. TESTADO E REJEITADO no backtest (piora PF 1.90->0.96) -- deixar OFF.", Order = 21, GroupName = "3. Entrada")]
		public bool UsaReteste { get; set; }

		[NinjaScriptProperty]
		[Display(Name = "Filtro EMA200 (1h)", Description = "So entra a favor da tendencia horaria (long acima da EMA200 do grafico de 1h, short abaixo). Filtro que mais ajudou no backtest -- manter ON.", Order = 30, GroupName = "4. Filtros de tendencia")]
		public bool UsaFiltroEMA200 { get; set; }

		[NinjaScriptProperty]
		[Range(10, 400)]
		[Display(Name = "Periodo EMA200", Order = 31, GroupName = "4. Filtros de tendencia")]
		public int PeriodoEMA200 { get; set; }

		[NinjaScriptProperty]
		[Display(Name = "Filtro VWAP", Description = "So entra do lado certo do VWAP da sessao. TESTADO E REJEITADO no backtest (redundante, 0 trades bloqueados no ano) -- deixar OFF.", Order = 32, GroupName = "4. Filtros de tendencia")]
		public bool UsaFiltroVWAP { get; set; }

		[NinjaScriptProperty]
		[Range(1, 100)]
		[Display(Name = "Stop (pontos)", Description = "Validado: 12,5pt (mesmo da diurna)", Order = 40, GroupName = "5. Risco")]
		public double StopPontos { get; set; }

		[NinjaScriptProperty]
		[Range(1, 300)]
		[Display(Name = "Alvo (pontos)", Description = "Validado: 37,5pt (3x o stop, PF 1.90 OOS 1.72|2.19)", Order = 41, GroupName = "5. Risco")]
		public double AlvoPontos { get; set; }

		[NinjaScriptProperty]
		[Range(0, 100000)]
		[Display(Name = "Stop diario proprio ($)", Description = "Para de operar no dia ao perder esse valor NESTE bot (0 = desliga)", Order = 42, GroupName = "5. Risco")]
		public double StopDiarioDolar { get; set; }

		[NinjaScriptProperty]
		[Display(Name = "Usa kill switch GLOBAL", Description = "Soma o PnL diario dos OUTROS bots (arquivos compartilhados) e bloqueia entrada se o combinado estourar o limite global.", Order = 43, GroupName = "5. Risco")]
		public bool UsaKillSwitchGlobal { get; set; }

		[NinjaScriptProperty]
		[Range(0, 100000)]
		[Display(Name = "Stop diario GLOBAL ($)", Description = "Limite combinado (manha + noite + diurna). So vale se 'Usa kill switch GLOBAL' = true.", Order = 44, GroupName = "5. Risco")]
		public double StopDiarioGlobalDolar { get; set; }

		[NinjaScriptProperty]
		[Display(Name = "Desenhar niveis", Order = 50, GroupName = "6. Visual")]
		public bool DesenharNiveis { get; set; }

		#endregion
	}
}
