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
//  OnFadeHarness — FASE A (lado NinjaScript) do experimento ONFADE
// -----------------------------------------------------------------------------
//  Implementa o CONTRATO MATEMATICO CONGELADO (§8 do protocolo), replicando
//  backtest/onfade_harness.py BIT A BIT. NAO ENVIA NENHUMA ORDEM. So calcula e
//  escreve: (1) um log por trade; (2) um dump de barras p/ reconciliacao.
//
//  Proposito: provar EQUIVALENCIA LOGICA com o harness Python.
//  NAO e' medida de rentabilidade real (isso e' a Fase B / OnFadeNative.cs).
//
//  PRE-REQUISITOS (Strategy Analyzer):
//    - Instrumento : MNQ 12-25 (serie continua importada do Databento)
//    - Fuso global do NT8 : (UTC-05:00) Eastern  <<< OBRIGATORIO (confirmado)
//    - Trading Hours : template ETH de indices (COM barras overnight/Globex)
//    - Periodo : 2024-09-13 -> 2024-11-01 (buffer p/ o 1o range ON)
//
//  ORDEM DE USO:
//    1a rodada: ReconDumpOnly = true. So o dump. Comparar timestamps_dump_nt8.csv
//               contra timestamps_dump.csv do Python. Confirmar a convencao de
//               barra (fim de barra => BarLabelOffsetMin = -1) ANTES de trades.
//    2a rodada: ReconDumpOnly = false, BarLabelOffsetMin conforme confirmado.
//               Comparar trades_ninjascript_slip{N}.csv contra
//               trades_python_slip{N}.csv. Equivalencia tem que ser EXATA.
//
//  Saidas em <OutputDir> (default: Documentos\onfade):
//    timestamps_dump_nt8.csv
//    trades_ninjascript_slip{SlipTicks}.csv
// =============================================================================

namespace NinjaTrader.NinjaScript.Strategies
{
	public class OnFadeHarness : Strategy
	{
		// ---------- contrato congelado (§8) — NAO OTIMIZAR ----------
		private const double STOP_PTS            = 12.5;
		private const double TARGET_PTS          = 60.0;
		private const int    MAX_TRADES          = 2;
		private const int    N_CONTR             = 1;
		private const int    ON_START_M          = 1080;   // 18:00 (inicio do intervalo)
		private const int    ON_END_M            = 570;    // 09:30
		private const int    SIG_FIRST_M         = 570;    // 09:30
		private const int    SIG_LAST_M          = 900;    // 15:00
		private const int    FLATTEN_M           = 955;    // 15:55
		private const int    HALFDAY_FLATTEN_M   = 12 * 60 + 55;   // 12:55
		private const int    MIN_ON_BARS         = 300;
		private const double MAX_ON_GAP_MIN      = 15.0;
		private const double SESSION_RESET_GAP_MIN = 90.0;

		private static readonly HashSet<DateTime> NyseHalfDays = new HashSet<DateTime>
		{
			new DateTime(2022,11,25), new DateTime(2022,7,3),  new DateTime(2023,7,3),
			new DateTime(2023,11,24), new DateTime(2024,7,3),  new DateTime(2024,11,29),
			new DateTime(2024,12,24), new DateTime(2025,7,3),  new DateTime(2025,11,28),
			new DateTime(2025,12,24), new DateTime(2026,11,27),
		};
		private static readonly HashSet<DateTime> DstDays = new HashSet<DateTime>
		{
			new DateTime(2022,3,13), new DateTime(2022,11,6), new DateTime(2023,3,12),
			new DateTime(2023,11,5), new DateTime(2024,3,10), new DateTime(2024,11,3),
			new DateTime(2025,3,9),  new DateTime(2025,11,2), new DateTime(2026,3,8),
			new DateTime(2026,11,1),
		};
		// mesmos 10 dias-amostra do dump Python (comparacao 1:1)
		private static readonly HashSet<DateTime> DumpDays = new HashSet<DateTime>
		{
			new DateTime(2024,9,13),  new DateTime(2024,9,18),  new DateTime(2024,9,24),
			new DateTime(2024,9,27),  new DateTime(2024,10,3),  new DateTime(2024,10,9),
			new DateTime(2024,10,14), new DateTime(2024,10,18), new DateTime(2024,10,23),
			new DateTime(2024,10,29),
		};

		// ---------- parametros ----------
		[NinjaScriptProperty]
		[Display(Name="ReconDumpOnly (1a rodada = true)", Order=1, GroupName="1. Harness")]
		public bool ReconDumpOnly { get; set; }

		[NinjaScriptProperty]
		[Range(-5, 5)]
		[Display(Name="BarLabelOffsetMin (Time[0] -> inicio do intervalo; -1 = fim de barra)", Order=2, GroupName="1. Harness")]
		public int BarLabelOffsetMin { get; set; }

		[NinjaScriptProperty]
		[Range(0, 10)]
		[Display(Name="SlipTicks (0 e 1 na Fase A)", Order=3, GroupName="1. Harness")]
		public int SlipTicks { get; set; }

		[NinjaScriptProperty]
		[Display(Name="CommissionRT (PROVISORIO 1.44 - CONFIRMAR)", Order=4, GroupName="1. Harness")]
		public double CommissionRT { get; set; }

		[NinjaScriptProperty]
		[Display(Name="TradeWindowStart (yyyy-MM-dd)", Order=5, GroupName="1. Harness")]
		public string TradeWindowStart { get; set; }

		[NinjaScriptProperty]
		[Display(Name="TradeWindowEnd (yyyy-MM-dd)", Order=6, GroupName="1. Harness")]
		public string TradeWindowEnd { get; set; }

		[NinjaScriptProperty]
		[Display(Name="OutputDir (vazio = Documentos\\onfade)", Order=7, GroupName="1. Harness")]
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

		// ---------- estado da posicao ----------
		private int      pos;              // 0 flat, +1 long, -1 short
		private double   eExec, stopTheo, targetTheo;
		private int      pendingSide;      // 0 none, +1 long, -1 short
		private DateTime pendSigStart;
		private double   pendSigClose, pendSigNivel;
		private int      tid;
		private string   curEntryPart;

		// ---------- controle ----------
		private DateTime twStart, twEnd;
		private string   outDir;
		private readonly List<string> tradeLog = new List<string>();
		private readonly List<string> dumpLog  = new List<string>();
		private readonly Dictionary<string, string[]> dayFirst = new Dictionary<string, string[]>();
		private readonly Dictionary<string, string[]> dayLast  = new Dictionary<string, string[]>();
		private long     onBarCount, rthBarCount, totalBars;
		private double   tickSz, pointVal;

		protected override void OnStateChange()
		{
			if (State == State.SetDefaults)
			{
				Description                 = @"FASE A do ONFADE. Replica o contrato §8 (= onfade_harness.py). NAO envia ordens. So log + dump p/ reconciliacao. Nao e' rentabilidade real.";
				Name                        = "OnFadeHarness";
				Calculate                   = Calculate.OnBarClose;
				EntriesPerDirection         = 1;
				EntryHandling               = EntryHandling.AllEntries;
				IsExitOnSessionCloseStrategy = false;
				IsFillLimitOnTouch          = false;
				MaximumBarsLookBack         = MaximumBarsLookBack.TwoHundredFiftySix;
				OrderFillResolution         = OrderFillResolution.Standard;
				Slippage                    = 0;
				StartBehavior               = StartBehavior.WaitUntilFlat;
				TimeInForce                 = TimeInForce.Gtc;
				TraceOrders                 = false;
				RealtimeErrorHandling       = RealtimeErrorHandling.StopCancelClose;
				StopTargetHandling          = StopTargetHandling.PerEntryExecution;
				BarsRequiredToTrade         = 1;
				IsInstantiatedOnEachOptimizationIteration = false;

				ReconDumpOnly       = true;
				BarLabelOffsetMin   = -1;      // NT8 import = fim de barra
				SlipTicks           = 0;
				CommissionRT        = 1.44;    // <<< PROVISORIO
				TradeWindowStart    = "2024-09-17";
				TradeWindowEnd      = "2024-10-31";
				OutputDir           = "";
			}
			else if (State == State.Configure)
			{
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
					Print("  *** ERRO: TradeWindowStart invalido ('" + TradeWindowStart + "'). Use yyyy-MM-dd. Nenhum trade sera escrito.");
				if (!DateTime.TryParseExact(TradeWindowEnd, "yyyy-MM-dd", CultureInfo.InvariantCulture, DateTimeStyles.None, out twEnd))
					Print("  *** ERRO: TradeWindowEnd invalido ('" + TradeWindowEnd + "'). Use yyyy-MM-dd. Nenhum trade sera escrito.");

				Print("==================================================================");
				Print("  OnFadeHarness — FASE A (lado NinjaScript). NAO envia ordens.");
				Print("  Instrumento : " + Instrument.FullName);
				Print("  TickSize    : " + tickSz.ToString(CultureInfo.InvariantCulture)
				      + "   PointValue : " + pointVal.ToString(CultureInfo.InvariantCulture));
				Print("  Trading Hours (template) : " + (Bars != null && Bars.TradingHours != null ? Bars.TradingHours.Name : "(desconhecido)"));
				Print("  TimeZone da maquina : " + TimeZoneInfo.Local.Id
				      + "  (o que importa e' o que Time[0] mostra — verificado pelo dump)");
				Print("  BarLabelOffsetMin : " + BarLabelOffsetMin + "   ReconDumpOnly : " + ReconDumpOnly);
				Print("  SlipTicks : " + SlipTicks + "   CommissionRT : " + CommissionRT.ToString(CultureInfo.InvariantCulture) + "  [PROVISORIO]");
				Print("  Janela de trade : " + TradeWindowStart + " -> " + TradeWindowEnd);
				Print("  OutputDir : " + outDir);
				if (Math.Abs(tickSz - 0.25) > 1e-9 || Math.Abs(pointVal - 2.0) > 1e-9)
					Print("  *** AVISO: TickSize/PointValue diferentes do esperado p/ MNQ (0.25 / 2.0). Conferir instrumento.");
				Print("==================================================================");

				dumpLog.Add("data,tipo,ts_nt8_label,ts_interval_start,open,high,low,close,volume");
				tradeLog.Add("trade_id,contract,data_pregao,bar_sinal_ts_et,sinal_preco_close,sinal_nivel,direcao,"
					+ "bar_entrada_ts_et,entrada_preco_teorico,entrada_slippage_ticks,entrada_preco_efetivo,"
					+ "stop_teorico,alvo_teorico,bar_saida_ts_et,saida_motivo,saida_preco_teorico,"
					+ "saida_slippage_ticks,saida_preco_efetivo,comissao_rt,pnl_bruto,pnl_liquido");

				ResetDayState();
				pos = 0; pendingSide = 0; tid = 0;
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

			DateTime label   = Time[0];                              // rotulo NT8 (fim de barra)
			DateTime tStart  = label.AddMinutes(BarLabelOffsetMin);  // inicio do intervalo (contrato §8)
			int      m       = tStart.Hour * 60 + tStart.Minute;
			DateTime d       = tStart.Date;
			double   gapMin  = (Time[0] - Time[1]).TotalMinutes;

			bool inOn = (m >= ON_START_M) || (m < ON_END_M);
			if (inOn) onBarCount++; else rthBarCount++;

			// -------- DUMP (roda sempre; e' o unico produto quando ReconDumpOnly) --------
			string dk  = d.ToString("yyyy-MM-dd");
			string vol = ((long)Math.Round(Volume[0])).ToString(CultureInfo.InvariantCulture);
			if (DumpDays.Contains(d))
			{
				string[] row = { dk, "?", Iso(label), Iso(tStart),
					Num(Open[0]), Num(High[0]), Num(Low[0]), Num(Close[0]), vol };
				if (!dayFirst.ContainsKey(dk)) dayFirst[dk] = row;
				dayLast[dk] = row;
				// barras nas horas-chave (09,15,16,17,18) do rotulo NT8
				int hh = label.Hour;
				if (hh == 9 || hh == 15 || hh == 16 || hh == 17 || hh == 18)
					dumpLog.Add(string.Join(",", new[] { dk, "bar_h" + hh.ToString("00"),
						Iso(label), Iso(tStart), Num(Open[0]), Num(High[0]), Num(Low[0]), Num(Close[0]), vol }));
			}

			// ---------------- 1. manutencao do range ON ----------------
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
					// day_valid = SO validade do range ON (sem look-ahead na RTH) — igual ao Python
					dayValid = (accCount >= MIN_ON_BARS) && (accGapMax <= MAX_ON_GAP_MIN);
					accActive = false; onFrozen = true;
					curDay = d;
					tradesToday = 0; stoppedLong = stoppedShort = false;
					flattenMToday = NyseHalfDays.Contains(d) ? HALFDAY_FLATTEN_M : FLATTEN_M;
				}
			}

			if (ReconDumpOnly) return;

			// ---------------- 2. fill de entrada pendente ----------------
			if (pendingSide != 0)
			{
				int side = pendingSide;
				double eTheo = Open[0];
				eExec = eTheo + SlipTicks * tickSz * side;
				stopTheo   = eExec - STOP_PTS   * side;
				targetTheo = eExec + TARGET_PTS * side;
				pos = pendingSide;
				tradesToday++;

				curEntryPart = string.Join(",", new[] {
					tid.ToString(CultureInfo.InvariantCulture),
					Instrument.MasterInstrument.Name,     // nome curto do instrumento (contrato resolvido no dump)
					d.ToString("yyyy-MM-dd"),
					Iso(pendSigStart), Num(pendSigClose), Num(pendSigNivel),
					side > 0 ? "LONG" : "SHORT",
					Iso(tStart), Num(eTheo), SlipTicks.ToString(CultureInfo.InvariantCulture), Num(eExec),
					Num(stopTheo), Num(targetTheo)
				});
				pendingSide = 0;
			}

			// ---------------- 3. checagem de saida (inclui a barra de entrada) ----------------
			if (pos != 0)
			{
				int side = pos;
				string reason = null; double xTheo = 0;
				if (side > 0)
				{
					if (Low[0] <= stopTheo)        { reason = "STOP"; xTheo = stopTheo; }
					else if (High[0] >= targetTheo){ reason = "ALVO"; xTheo = targetTheo; }
				}
				else
				{
					if (High[0] >= stopTheo)       { reason = "STOP"; xTheo = stopTheo; }
					else if (Low[0] <= targetTheo) { reason = "ALVO"; xTheo = targetTheo; }
				}
				if (reason == null && m >= flattenMToday) { reason = "FLATTEN"; xTheo = Close[0]; }

				if (reason != null)
				{
					double xExec = xTheo - SlipTicks * tickSz * side;
					double pnlBruto = (xExec - eExec) * side * pointVal * N_CONTR;
					double pnlLiq   = pnlBruto - CommissionRT * N_CONTR;
					if (curDay >= twStart && curDay <= twEnd)
						tradeLog.Add(curEntryPart + "," + string.Join(",", new[] {
							Iso(tStart), reason, Num(xTheo),
							SlipTicks.ToString(CultureInfo.InvariantCulture), Num(xExec),
							CommissionRT.ToString(CultureInfo.InvariantCulture),
							Num(pnlBruto), Num(pnlLiq)
						}));
					tid++;
					if (reason == "STOP") { if (side > 0) stoppedLong = true; else stoppedShort = true; }
					pos = 0;
				}
			}

			// ---------------- 4. deteccao de sinal (posicao FLAT) ----------------
			if (pos == 0 && pendingSide == 0 && dayValid && onFrozen
				&& d == curDay                       // barra pertence ao dia congelado
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
		}

		private void FlushFiles()
		{
			try
			{
				if (totalBars == 0 || dumpLog.Count == 0)
				{
					Print("==================================================================");
					Print("  *** ERRO GRAVE: 0 BARRAS PROCESSADAS. O backtest nao achou dado.");
					Print("  Causas provaveis:");
					Print("   1. O instrumento do Analyzer (" + Instrument.FullName + ") nao tem o");
					Print("      historico importado. Confira em Ferramentas > Historico de dados.");
					Print("   2. TickSize=" + tickSz.ToString(CultureInfo.InvariantCulture)
					      + " / PointValue=" + pointVal.ToString(CultureInfo.InvariantCulture)
					      + " (esperado MNQ 0.25 / 2.0) => NT8 nao reconhece esse contrato,");
					Print("      criou um instrumento generico. Corrija os specs ou use outro slot.");
					Print("   3. Fuso global do NT8 != Eastern (atual: " + TimeZoneInfo.Local.Id + ").");
					Print("  Nenhum arquivo de dump escrito.");
					Print("==================================================================");
					return;
				}
				// completa o dump com primeira/ultima barra de cada dia-amostra
				var extra = new List<string>();
				foreach (var kv in dayFirst)
				{
					var r = (string[])kv.Value.Clone(); r[1] = "primeira_barra_do_dia";
					extra.Add(string.Join(",", r));
				}
				foreach (var kv in dayLast)
				{
					var r = (string[])kv.Value.Clone(); r[1] = "ultima_barra_do_dia";
					extra.Add(string.Join(",", r));
				}
				var full = new List<string> { dumpLog[0] };
				full.AddRange(extra.OrderBy(x => x));
				full.AddRange(dumpLog.Skip(1));

				File.WriteAllLines(Path.Combine(outDir, "timestamps_dump_nt8.csv"), full);
				File.WriteAllLines(Path.Combine(outDir, "trades_ninjascript_slip" + SlipTicks + ".csv"), tradeLog);

				Print("------------------------------------------------------------------");
				Print("  [FLUSH] " + Path.Combine(outDir, "timestamps_dump_nt8.csv"));
				Print("  [FLUSH] " + Path.Combine(outDir, "trades_ninjascript_slip" + SlipTicks + ".csv"));
				Print("  barras totais : " + totalBars + "   overnight : " + onBarCount + "   RTH/pos-RTH : " + rthBarCount);
				if (onBarCount < totalBars * 0.20)
					Print("  *** AVISO GRAVE: poucas barras overnight (" + onBarCount + "/" + totalBars
					      + "). Template de sessao provavelmente RTH-only. NAO CONFIAR NO RESULTADO.");
				if (!ReconDumpOnly)
				{
					int nt = tradeLog.Count - 1;
					Print("  trades registrados : " + nt + "  (SlipTicks=" + SlipTicks + ", C_RT=" + CommissionRT + " [PROVISORIO])");
				}
				Print("  [NOTA] FASE A. Equivalencia com o Python tem que ser EXATA. Nada aqui e' rentabilidade real.");
				Print("------------------------------------------------------------------");
			}
			catch (Exception e)
			{
				Print("ERRO no FlushFiles: " + e.Message);
			}
		}
	}
}
