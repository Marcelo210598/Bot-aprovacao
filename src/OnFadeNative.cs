#region Using declarations
using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.ComponentModel.DataAnnotations;
using System.Linq;
using System.Text;
using System.IO;
using System.Globalization;
using NinjaTrader.Cbi;
using NinjaTrader.Gui;
using NinjaTrader.Gui.Chart;
using NinjaTrader.Data;
using NinjaTrader.NinjaScript;
using NinjaTrader.Core.FloatingPoint;
using NinjaTrader.NinjaScript.Indicators;
using NinjaTrader.NinjaScript.DrawingTools;
#endregion

// =============================================================================
//  OnFadeNative — FASE B (execucao nativa) do experimento ONFADE
// -----------------------------------------------------------------------------
//  MESMA logica de sinal do OnFadeHarness.cs / onfade_harness.py (contrato §8
//  CONGELADO). A diferenca: aqui ENVIA ORDENS DE VERDADE (EnterLong/EnterShort +
//  stop e alvo nativos + saida nativa no flatten). O NT8 preenche. O P&L
//  economico vem do Strategy Analyzer, NAO deste codigo.
//
//  NAO OTIMIZAR. Nao mexer em: janela overnight, toque estrito, stop 12.5,
//  alvo 60, max 2 trades/dia, flatten, ausencia de filtros/BE/trailing.
//
//  COMISSAO e SLIPPAGE: este codigo NAO calcula nenhum dos dois.
//    - Slippage  -> campo "Deslizamento" do Strategy Analyzer
//    - Comissao  -> template "Modelo de comissao" do Strategy Analyzer
//  O CSV de trades daqui registra so preco de fill BRUTO (checagem de mecanica
//  contra o harness). O veredito economico = relatorio do Analyzer, conferido
//  contra OnExecutionUpdate.
//
//  PRE-REQUISITOS (Strategy Analyzer) — iguais ao harness:
//    - Instrumento   : "MNQ DEC21"  <<< NAO e' o contrato de dez/2021!
//        E' um SLOT-CONTAINER: nome de contrato JA VENCIDO usado de proposito
//        (gera_import_nt8_mnq.py) pra o NT8 nao mesclar feed Rithmic. Dentro
//        dele esta a SERIE CONTINUA front-month 2022-05-31 -> 2026-08-31
//        (1.505.364 barras 1min, Databento, convertida p/ Eastern). Precos de
//        set/2024 ~19.400-20.700 (nivel real do MNQ, nao ~16.000 de 2021).
//        Foi EXATAMENTE este slot que a Fase A reconciliou 77/77 barras +
//        38/38 trades contra o Python. B0 TEM que usar o mesmo.
//    - Fuso global NT8 : (UTC-05:00) Eastern   <<< OBRIGATORIO (Time[0] em ET)
//    - Trading Hours : CME US Index Futures ETH (COM overnight/Globex)
//    - Periodo       : buffer >= 3 dias corridos antes do 1o dia de trade
//
//  ⚠️ MEIO-DIA / EARLY CLOSE: NyseHalfDays + flatten 12:55 vem do harness, que
//     assume fecho NYSE cash 13:00 ET. O MNQ (CME Globex) fecha cedo 13:15 ET
//     nesses dias — NAO e' 13:00. Sem meio-dia na janela da Fase A (set-out/24),
//     entao nao afetou. ANTES do backtest 2022-2026: confirmar se o template
//     CME US Index Futures ETH modela o early close e ajustar HALFDAY_FLATTEN_M
//     nos DOIS lados (aqui + onfade_harness.py) pra bater com o horario real
//     dos futuros.
//
//  RODADAS:
//    B0  Deslizamento 0  | comissao 0            -> comparar com harness slip0
//    B1  Deslizamento 1t | comissao real         -> economico
//    B2  Deslizamento 2t | comissao real
//    B3  Deslizamento 3t | comissao real
//
//  Saida em <OutputDir> (default Documentos\onfade):
//    trades_native_B{Rodada}.csv
// =============================================================================

namespace NinjaTrader.NinjaScript.Strategies
{
	public class OnFadeNative : Strategy
	{
		// ---------- contrato congelado (§8) — NAO OTIMIZAR ----------
		private const double TICK                 = 0.25;   // MNQ
		private const double STOP_PTS              = 12.5;
		private const double TARGET_PTS            = 60.0;
		private const int    MAX_TRADES            = 2;
		private const int    ON_START_M            = 1080;   // 18:00
		private const int    ON_END_M              = 570;    // 09:30
		private const int    SIG_FIRST_M           = 570;    // 09:30
		private const int    SIG_LAST_M            = 900;    // 15:00
		private const int    FLATTEN_M             = 955;    // 15:55
		private const int    HALFDAY_FLATTEN_M     = 12 * 60 + 55;   // 12:55
		private const int    MIN_ON_BARS           = 300;
		private const double MAX_ON_GAP_MIN        = 15.0;
		private const double SESSION_RESET_GAP_MIN = 90.0;

		private static readonly HashSet<DateTime> NyseHalfDays = new HashSet<DateTime>
		{
			new DateTime(2022,11,25), new DateTime(2022,7,3),  new DateTime(2023,7,3),
			new DateTime(2023,11,24), new DateTime(2024,7,3),  new DateTime(2024,11,29),
			new DateTime(2024,12,24), new DateTime(2025,7,3),  new DateTime(2025,11,28),
			new DateTime(2025,12,24), new DateTime(2026,11,27),
		};

		// ---------- parametros ----------
		[NinjaScriptProperty]
		[Range(1, 20)]
		[Display(Name="Contratos", Order=1, GroupName="1. OnFade")]
		public int Contratos { get; set; }

		[NinjaScriptProperty]
		[Display(Name="Rodada (rotulo do CSV: 0/1/2/3)", Order=2, GroupName="1. OnFade")]
		public int Rodada { get; set; }

		[NinjaScriptProperty]
		[Display(Name="TradeWindowStart (yyyy-MM-dd)", Order=3, GroupName="1. OnFade")]
		public string TradeWindowStart { get; set; }

		[NinjaScriptProperty]
		[Display(Name="TradeWindowEnd (yyyy-MM-dd)", Order=4, GroupName="1. OnFade")]
		public string TradeWindowEnd { get; set; }

		[NinjaScriptProperty]
		[Display(Name="OutputDir (vazio = Documentos\\onfade)", Order=5, GroupName="1. OnFade")]
		public string OutputDir { get; set; }

		// ---------- estado do range ON ----------
		private double   accHi, accLo, accGapMax;
		private int      accCount;
		private DateTime accLast;
		private bool     accActive;
		private double   onHigh, onLow;
		private bool     onFrozen;
		private bool     dayValid;
		private DateTime curDay;
		private int      tradesToday;
		private bool     stoppedLong, stoppedShort;
		private int      flattenMToday;

		// ---------- estado da posicao / sinal ----------
		private int      pendingSide;          // 0 none, +1 long, -1 short (consumido na mesma barra)
		private DateTime pendSigStart;
		private double   pendSigClose, pendSigNivel;
		private bool     flatSent;             // flatten ja enviado nesta posicao

		// entrada corrente (preenchida em OnExecutionUpdate)
		private int      curSide;
		private double   curEntryPrice;
		private DateTime curEntryTime;
		private DateTime curSigStart;
		private double   curSigClose, curSigNivel;
		private DateTime curSigDay;
		private bool     inTrade;

		// ---------- controle ----------
		private DateTime twStart, twEnd;
		private string   outDir;
		private int      tid;
		private readonly List<string> tradeLog = new List<string>();
		private long     onBarCount, totalBars;
		private double   tickSz, pointVal;

		protected override void OnStateChange()
		{
			if (State == State.SetDefaults)
			{
				Description                  = @"FASE B do ONFADE. Execucao NATIVA do contrato §8 (mesma logica do OnFadeHarness). Comissao/slippage = Strategy Analyzer, nao o codigo. P&L economico = relatorio do Analyzer.";
				Name                         = "OnFadeNative";
				Calculate                    = Calculate.OnBarClose;
				EntriesPerDirection          = 1;
				EntryHandling                = EntryHandling.AllEntries;
				IsExitOnSessionCloseStrategy  = false;
				IsFillLimitOnTouch           = false;
				MaximumBarsLookBack          = MaximumBarsLookBack.TwoHundredFiftySix;
				OrderFillResolution          = OrderFillResolution.Standard;
				Slippage                     = 0;               // Analyzer controla ("Deslizamento")
				StartBehavior                = StartBehavior.WaitUntilFlat;
				TimeInForce                  = TimeInForce.Gtc;
				TraceOrders                  = false;
				RealtimeErrorHandling        = RealtimeErrorHandling.StopCancelClose;
				StopTargetHandling           = StopTargetHandling.PerEntryExecution;
				BarsRequiredToTrade          = 1;
				IsInstantiatedOnEachOptimizationIteration = false;

				Contratos        = 1;
				Rodada           = 0;
				TradeWindowStart = "2024-09-17";
				TradeWindowEnd   = "2024-10-31";
				OutputDir        = "";
			}
			else if (State == State.Configure)
			{
				// stop e alvo nativos, em ticks fixos, a partir do preco medio de entrada real.
				// Setados uma vez aqui (padrao NT8) -> valem p/ toda entrada. OCO automatico.
				SetStopLoss(CalculationMode.Ticks, STOP_PTS   / TICK);   // 12.5 / 0.25 = 50 ticks
				SetProfitTarget(CalculationMode.Ticks, TARGET_PTS / TICK); // 60.0 / 0.25 = 240 ticks
			}
			else if (State == State.DataLoaded)
			{
				tickSz   = TickSize;
				pointVal = Instrument.MasterInstrument.PointValue;

				outDir = string.IsNullOrWhiteSpace(OutputDir)
					? Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.MyDocuments), "onfade")
					: OutputDir;
				try { Directory.CreateDirectory(outDir); } catch (Exception e) { Print("ERRO criando OutputDir: " + e.Message); }

				if (!DateTime.TryParseExact(TradeWindowStart, "yyyy-MM-dd", CultureInfo.InvariantCulture, DateTimeStyles.None, out twStart))
					Print("  *** ERRO: TradeWindowStart invalido ('" + TradeWindowStart + "').");
				if (!DateTime.TryParseExact(TradeWindowEnd, "yyyy-MM-dd", CultureInfo.InvariantCulture, DateTimeStyles.None, out twEnd))
					Print("  *** ERRO: TradeWindowEnd invalido ('" + TradeWindowEnd + "').");

				Print("==================================================================");
				Print("  OnFadeNative — FASE B (execucao nativa). Contrato §8 congelado.");
				Print("  Instrumento : " + Instrument.FullName
				      + "   TickSize : " + tickSz.ToString(CultureInfo.InvariantCulture)
				      + "   PointValue : " + pointVal.ToString(CultureInfo.InvariantCulture));
				Print("  Trading Hours : " + (Bars != null && Bars.TradingHours != null ? Bars.TradingHours.Name : "(desconhecido)"));
				Print("  TimeZone da maquina : " + TimeZoneInfo.Local.Id + "  (Time[0] tem que estar em ET — fuso global NT8 = Eastern)");
				Print("  Contratos : " + Contratos + "   Rodada : B" + Rodada);
				Print("  Janela de trade : " + TradeWindowStart + " -> " + TradeWindowEnd);
				Print("  Slippage(codigo) : " + Slippage + "  (as rodadas B1-B3 setam o Deslizamento no Analyzer)");
				Print("  Comissao : definida pelo template do Analyzer (NAO pelo codigo)");
				Print("  OutputDir : " + outDir);
				if (Math.Abs(tickSz - 0.25) > 1e-9 || Math.Abs(pointVal - 2.0) > 1e-9)
					Print("  *** AVISO: TickSize/PointValue != MNQ (0.25 / 2.0). Conferir instrumento.");
				Print("==================================================================");

				tradeLog.Add("trade_id,contract,data_pregao,bar_sinal_ts_et,sinal_preco_close,sinal_nivel,direcao,"
					+ "bar_entrada_ts_et,entrada_preco_fill,bar_saida_ts_et,saida_motivo,saida_preco_fill,"
					+ "contratos,pnl_bruto_pts,pnl_bruto_cash");

				ResetDayState();
				pendingSide = 0; tid = 0; inTrade = false; flatSent = false;
			}
			else if (State == State.Terminated)
			{
				FlushFiles();
			}
		}

		private void ResetDayState()
		{
			accActive = false; accHi = accLo = accGapMax = 0; accCount = 0;
			onFrozen = false; dayValid = false;
			tradesToday = 0; stoppedLong = stoppedShort = false;
			flattenMToday = FLATTEN_M;
		}

		private static string Iso(DateTime t)
		{
			return t.ToString("yyyy-MM-dd'T'HH:mm:ss", CultureInfo.InvariantCulture);
		}
		private static string Num(double v)
		{
			return Math.Round(v, 4).ToString(CultureInfo.InvariantCulture);
		}

		protected override void OnBarUpdate()
		{
			if (CurrentBar < 1) return;
			totalBars++;

			DateTime label  = Time[0];                                  // rotulo NT8 (fim de barra)
			DateTime tStart = label.AddMinutes(-1);                     // inicio do intervalo (§8) — import = fim de barra
			int      m      = tStart.Hour * 60 + tStart.Minute;
			DateTime d      = tStart.Date;
			double   gapMin = (Time[0] - Time[1]).TotalMinutes;

			bool inOn = (m >= ON_START_M) || (m < ON_END_M);
			if (inOn) onBarCount++;

			// ---------------- 1. manutencao do range ON (verbatim do harness) ----------------
			if (inOn)
			{
				if (!accActive || gapMin > SESSION_RESET_GAP_MIN)
				{
					accHi = High[0]; accLo = Low[0]; accCount = 1; accGapMax = 0.0;
					accLast = tStart; accActive = true;
				}
				else
				{
					accHi = Math.Max(accHi, High[0]);
					accLo = Math.Min(accLo, Low[0]);
					accCount++;
					accGapMax = Math.Max(accGapMax, (tStart - accLast).TotalMinutes);
					accLast = tStart;
				}
			}
			else
			{
				if (accActive)   // 1a barra nao-ON depois da sessao overnight => congela
				{
					onHigh = accHi; onLow = accLo;
					dayValid = (accCount >= MIN_ON_BARS) && (accGapMax <= MAX_ON_GAP_MIN);
					accActive = false; onFrozen = true;
					curDay = d;
					tradesToday = 0; stoppedLong = stoppedShort = false;
					flattenMToday = NyseHalfDays.Contains(d) ? HALFDAY_FLATTEN_M : FLATTEN_M;
				}
			}

			// ---------------- 2. flatten nativo ----------------
			if (Position.MarketPosition != MarketPosition.Flat && !flatSent && m >= flattenMToday)
			{
				if (Position.MarketPosition == MarketPosition.Long)  ExitLong ("OnFadeFlat", "OnFadeLong");
				else                                                 ExitShort("OnFadeFlat", "OnFadeShort");
				flatSent = true;
			}

			// ---------------- 3. deteccao de sinal (FLAT, sem ordem pendente) ----------------
			bool flat = Position.MarketPosition == MarketPosition.Flat;
			if (flat && !inTrade && pendingSide == 0 && dayValid && onFrozen
				&& d == curDay
				&& m >= SIG_FIRST_M && m <= SIG_LAST_M
				&& tradesToday < MAX_TRADES)
			{
				bool tocaTopo  = (High[0] >= onHigh) && (Close[0] < onHigh) && !stoppedShort;
				bool tocaFundo = (Low[0]  <= onLow ) && (Close[0] > onLow ) && !stoppedLong;
				if (tocaTopo && tocaFundo) { /* ambigua: nao opera */ }
				else if (tocaTopo)
				{
					pendingSide = -1; pendSigStart = tStart; pendSigClose = Close[0]; pendSigNivel = onHigh;
				}
				else if (tocaFundo)
				{
					pendingSide = +1; pendSigStart = tStart; pendSigClose = Close[0]; pendSigNivel = onLow;
				}
			}

			// ---------------- 4. entrada nativa (mercado no fecho -> fill no open de B+1) ----------------
			if (pendingSide != 0 && flat && !inTrade)
			{
				curSigStart = pendSigStart; curSigClose = pendSigClose;
				curSigNivel = pendSigNivel; curSigDay = curDay;
				curSide     = pendingSide;
				tradesToday++;
				flatSent = false;
				if (pendingSide > 0) EnterLong (Contratos, "OnFadeLong");
				else                 EnterShort(Contratos, "OnFadeShort");
				pendingSide = 0;
			}
		}

		protected override void OnExecutionUpdate(Execution execution, string executionId, double price,
			int quantity, MarketPosition marketPosition, string orderId, DateTime time)
		{
			if (execution.Order == null) return;
			string on = execution.Order.Name;

			// ----- ENTRADA -----
			if (on == "OnFadeLong" || on == "OnFadeShort")
			{
				if (!inTrade)
				{
					inTrade       = true;
					curEntryPrice = price;
					curEntryTime  = time;
				}
				return;
			}

			// ----- SAIDA (stop / alvo / flatten) -----
			bool isExit = on == "Stop loss" || on == "Profit target" || on == "OnFadeFlat"
			              || on == "Exit on session close";
			if (isExit && inTrade && Position.MarketPosition == MarketPosition.Flat)
			{
				string motivo = on == "Stop loss"      ? "STOP"
				              : on == "Profit target"   ? "ALVO"
				              : "FLATTEN";

				double pnlPts  = (price - curEntryPrice) * curSide;
				double pnlCash = pnlPts * pointVal * quantity;

				if (curSigDay >= twStart && curSigDay <= twEnd)
				{
					tradeLog.Add(string.Join(",", new[] {
						tid.ToString(CultureInfo.InvariantCulture),
						Instrument.MasterInstrument.Name,
						curSigDay.ToString("yyyy-MM-dd"),
						Iso(curSigStart), Num(curSigClose), Num(curSigNivel),
						curSide > 0 ? "LONG" : "SHORT",
						Iso(curEntryTime), Num(curEntryPrice),
						Iso(time), motivo, Num(price),
						quantity.ToString(CultureInfo.InvariantCulture),
						Num(pnlPts), Num(pnlCash)
					}));
				}
				tid++;
				if (motivo == "STOP") { if (curSide > 0) stoppedLong = true; else stoppedShort = true; }
				inTrade  = false;
				flatSent = false;
			}
		}

		private void FlushFiles()
		{
			try
			{
				if (totalBars == 0)
				{
					Print("  *** ERRO GRAVE: 0 BARRAS. Instrumento (" + Instrument.FullName
					      + ") sem historico importado, ou fuso/instrumento errado. Nada escrito.");
					return;
				}
				string path = Path.Combine(outDir, "trades_native_B" + Rodada + ".csv");
				File.WriteAllLines(path, tradeLog);

				double somaPts = 0, somaCash = 0; int nt = tradeLog.Count - 1;
				for (int i = 1; i < tradeLog.Count; i++)
				{
					var p = tradeLog[i].Split(',');
					somaPts  += double.Parse(p[p.Length - 2], CultureInfo.InvariantCulture);
					somaCash += double.Parse(p[p.Length - 1], CultureInfo.InvariantCulture);
				}
				Print("------------------------------------------------------------------");
				Print("  [FLUSH] " + path);
				Print("  barras totais : " + totalBars + "   overnight : " + onBarCount);
				Print("  trades registrados : " + nt
				      + "   soma pts(bruto) : " + Math.Round(somaPts, 2)
				      + "   soma cash(bruto, s/ comissao) : " + Math.Round(somaCash, 2));
				Print("  [NOTA] P&L economico = relatorio do Strategy Analyzer (com comissao/deslizamento).");
				Print("         Este CSV so serve p/ conferir MECANICA contra o harness (B0).");
				Print("------------------------------------------------------------------");
			}
			catch (Exception e)
			{
				Print("ERRO no FlushFiles: " + e.Message);
			}
		}
	}
}
