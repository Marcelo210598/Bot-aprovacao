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
//  AberturaNYSpecAndersson — igual ao pedido do Andersson de 11/09/2026, motor
//  reaproveitado do AberturaExplosao.cs (OnMarketData tick-a-tick, fuso-proof,
//  CSV, flatten) do Marcelo.
// -----------------------------------------------------------------------------
//  LOGICA (pedido do Andersson, ponto a ponto):
//   1) Horario: abertura de NY (09:30 ET = ~10:30 Brasilia — o offset BRT/ET
//      varia com o horario de verao americano; a maquina trabalha em ET fuso-
//      proof, por isso o parametro abaixo e' em ET, nao em BRT).
//   2) Referencia = preco de abertura da 1a vela de 1min (1o print >= 09:30:00 ET).
//   3) Entrada em TEMPO REAL (nao espera a vela fechar): assim que o preco andar
//      TicksParaEntrada a partir da abertura, dispara a MERCADO na direcao do
//      movimento. So' monitora dentro de JanelaMonitoramentoSeg (default 60s =
//      "so' a 1a vela de 1min", como pedido).
//   4) 1 entrada por abertura (nao reentra no mesmo dia).
//   5) StopLossDolares / TakeProfitDolares: $ na posicao, configuraveis.
//   6) Break-even PROGRESSIVO em DEGRAUS (o pedido explicito do Andersson, ponto
//      6 do texto dele — diferente do TrailDolar continuo do AberturaExplosao):
//        - BeAtivacaoDolar : lucro ($) pra ativar a 1a protecao.
//        - BeProtegeDolar  : quanto desse lucro fica travado no stop na 1a vez
//                            (0 = breakeven exato).
//        - BeIncrementoDolar : a cada esse valor A MAIS de lucro (hwm), o stop
//                            sobe o MESMO valor (degrau), sempre so' pra cima
//                            (ratchet). BeIncrementoDolar=0 = trava 1x e para
//                            (sem novos degraus).
//
//  Os 3 valores de BE (ativacao/protege/incremento) NAO tinham default numerico
//  no pedido do Andersson (ele so' deu o "exemplo conceitual") — os defaults
//  abaixo (ativa em $100, protege $0/breakeven, sobe de $50 em $50) sao um
//  ponto de partida RAZOAVEL do Marcelo, confirmar/ajustar com ele antes de
//  bater o martelo.
//
//  PRE-REQUISITOS (igual ao AberturaExplosao):
//    - Market Replay (tick) OU Strategy Analyzer com TICK REPLAY LIGADO.
//    - Fuso global do NT8 = Eastern (ou qualquer fuso — o codigo e' fuso-proof).
//    - Instrumento MNQ (TickSize 0.25 / PointValue 2.0).
//
//  COMISSAO / SLIPPAGE: nao calculados aqui (igual ao AberturaExplosao) — o
//  veredito economico e' o relatorio do Strategy Analyzer / Market Replay.
//
//  ⚠️ Achado do dia 11/09 (grid honesto em Python, mesmo gatilho de 10 ticks,
//  janela de 60s): 17 de 18 combinacoes de degrau/stop deram NEGATIVO. Isso
//  NAO significa que esse .cs esta errado — significa que a mecanica "reage
//  ao 1o movimento da abertura" nao mostrou edge em nenhuma variacao testada
//  ate agora (nem gatilho 3t nem 10t, nem trailing continuo nem em degraus).
//  Construido do jeito que o Andersson pediu mesmo assim, pra ele ver com os
//  proprios olhos no Replay — mesmo processo que o Marcelo fez o dia inteiro.
//
//  NAO e' bot de producao. `BotAprovacao.cs` e o ONFADE seguem intactos.
// =============================================================================

namespace NinjaTrader.NinjaScript.Strategies
{
	public class AberturaNYSpecAndersson : Strategy
	{
		private double tickSz = 0.25;

		private const int FLATTEN_M         = 15 * 60 + 55;  // 15:55 ET
		private const int HALFDAY_FLATTEN_M = 12 * 60 + 55;  // 12:55 ET (early close)

		private static readonly HashSet<DateTime> NyseHalfDays = new HashSet<DateTime>
		{
			new DateTime(2022,11,25), new DateTime(2022,7,3),  new DateTime(2023,7,3),
			new DateTime(2023,11,24), new DateTime(2024,7,3),  new DateTime(2024,11,29),
			new DateTime(2024,12,24), new DateTime(2025,7,3),  new DateTime(2025,11,28),
			new DateTime(2025,12,24), new DateTime(2026,11,27),
		};

		// ---------- parametros (secao 7 do pedido do Andersson) ----------
		[NinjaScriptProperty] [Range(1, 40)]
		[Display(Name="Contratos", Order=1, GroupName="1. Abertura")]
		public int Contratos { get; set; }

		[NinjaScriptProperty] [Range(0, 23)]
		[Display(Name="HoraAberturaEt (ET; 9 = 09:30 ET, ~10:30 Brasilia no horario de verao americano)", Order=2, GroupName="1. Abertura")]
		public int HoraAberturaEt { get; set; }

		[NinjaScriptProperty] [Range(0, 59)]
		[Display(Name="MinutoAberturaEt (ET)", Order=3, GroupName="1. Abertura")]
		public int MinutoAberturaEt { get; set; }

		[NinjaScriptProperty] [Range(5, 900)]
		[Display(Name="JanelaMonitoramentoSeg (60 = so' a 1a vela de 1min, como pedido)", Order=4, GroupName="1. Abertura")]
		public int JanelaMonitoramentoSeg { get; set; }

		[NinjaScriptProperty] [Range(1, 200)]
		[Display(Name="TicksParaEntrada", Order=5, GroupName="1. Abertura")]
		public int TicksParaEntrada { get; set; }

		[NinjaScriptProperty] [Range(1, 100000)]
		[Display(Name="StopLossDolares ($ na posicao)", Order=1, GroupName="2. Stop e Alvo")]
		public double StopLossDolares { get; set; }

		[NinjaScriptProperty] [Range(0, 100000)]
		[Display(Name="TakeProfitDolares ($ na posicao; 0 = sem alvo)", Order=2, GroupName="2. Stop e Alvo")]
		public double TakeProfitDolares { get; set; }

		[NinjaScriptProperty] [Range(0, 100000)]
		[Display(Name="BeAtivacaoDolar (lucro $ pra ativar a 1a protecao)", Order=1, GroupName="3. Break-Even Progressivo")]
		public double BeAtivacaoDolar { get; set; }

		[NinjaScriptProperty] [Range(0, 100000)]
		[Display(Name="BeProtegeDolar (quanto trava no stop na 1a ativacao; 0 = breakeven)", Order=2, GroupName="3. Break-Even Progressivo")]
		public double BeProtegeDolar { get; set; }

		[NinjaScriptProperty] [Range(0, 100000)]
		[Display(Name="BeIncrementoDolar (a cada esse $ a mais de lucro, sobe o stop o mesmo valor; 0 = trava 1x e para)", Order=3, GroupName="3. Break-Even Progressivo")]
		public double BeIncrementoDolar { get; set; }

		[NinjaScriptProperty]
		[Display(Name="TradeWindowStart (yyyy-MM-dd, vazio = tudo)", Order=1, GroupName="4. Controle")]
		public string TradeWindowStart { get; set; }

		[NinjaScriptProperty]
		[Display(Name="TradeWindowEnd (yyyy-MM-dd, vazio = tudo)", Order=2, GroupName="4. Controle")]
		public string TradeWindowEnd { get; set; }

		[NinjaScriptProperty]
		[Display(Name="OutputDir (vazio = Documentos\\abertura_andersson)", Order=3, GroupName="4. Controle")]
		public string OutputDir { get; set; }

		// ---------- estado diario ----------
		private DateTime curDay;
		private DateTime rthStart;
		private bool     openCaptured;
		private double   openPx;
		private int      tradesToday;
		private int      flattenMToday;

		// ---------- estado da posicao ----------
		private bool     inTrade;
		private int      curSide;
		private double   curEntry;
		private DateTime curEntryTime;
		private DateTime curSigDay;
		private bool     exitSent;
		private DateTime curEntryEt;
		private double   hwmDolar;
		private double   stopDolLock;

		// ---------- controle ----------
		private DateTime twStart, twEnd;
		private bool     twAll;
		private string   outDir;
		private int      tid;
		private readonly List<string> tradeLog = new List<string>();
		private long     totalBars;
		private double   pointVal;
		private int      nTrades;
		private double   sumPts, sumCash;

		// ---------- fuso-proof ----------
		private TimeZoneInfo etTz;
		private TimeZoneInfo graficoTz;

		protected override void OnStateChange()
		{
			if (State == State.SetDefaults)
			{
				Description                   = @"Abertura de NY — spec do Andersson (11/09/2026): gatilho de N ticks na 1a vela de 1min, entrada em tempo real, SL/TP em $ configuraveis, break-even progressivo em degraus configuraveis. Motor reaproveitado do AberturaExplosao.cs. Rodar em Tick Replay.";
				Name                          = "AberturaNYSpecAndersson";
				Calculate                     = Calculate.OnEachTick;
				EntriesPerDirection           = 1;
				EntryHandling                 = EntryHandling.AllEntries;
				IsExitOnSessionCloseStrategy  = true;
				ExitOnSessionCloseSeconds     = 30;
				IsFillLimitOnTouch            = false;
				MaximumBarsLookBack           = MaximumBarsLookBack.TwoHundredFiftySix;
				OrderFillResolution           = OrderFillResolution.Standard;
				Slippage                      = 0;
				StartBehavior                 = StartBehavior.WaitUntilFlat;
				TimeInForce                   = TimeInForce.Gtc;
				TraceOrders                   = false;
				RealtimeErrorHandling         = RealtimeErrorHandling.StopCancelClose;
				StopTargetHandling            = StopTargetHandling.PerEntryExecution;
				BarsRequiredToTrade           = 1;
				IsInstantiatedOnEachOptimizationIteration = false;

				Contratos              = 6;
				HoraAberturaEt         = 9;
				MinutoAberturaEt       = 30;
				JanelaMonitoramentoSeg = 60;
				TicksParaEntrada       = 10;
				StopLossDolares        = 250;
				TakeProfitDolares      = 500;
				BeAtivacaoDolar        = 100;
				BeProtegeDolar         = 0;
				BeIncrementoDolar      = 50;
				TradeWindowStart       = "";
				TradeWindowEnd         = "";
				OutputDir              = "";
			}
			else if (State == State.DataLoaded)
			{
				pointVal = Instrument.MasterInstrument.PointValue;
				tickSz   = TickSize;

				try { etTz = TimeZoneInfo.FindSystemTimeZoneById("Eastern Standard Time"); } catch { etTz = null; }
				graficoTz = ResolveFusoGrafico();
				Print("  Fuso do grafico detectado : " + (graficoTz != null ? graficoTz.Id : "(nao detectado -> assume ET)"));

				outDir = string.IsNullOrWhiteSpace(OutputDir)
					? Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.MyDocuments), "abertura_andersson")
					: OutputDir;
				try { Directory.CreateDirectory(outDir); } catch (Exception e) { Print("ERRO criando OutputDir: " + e.Message); }

				twAll = string.IsNullOrWhiteSpace(TradeWindowStart) && string.IsNullOrWhiteSpace(TradeWindowEnd);
				if (!twAll)
				{
					if (!DateTime.TryParseExact(TradeWindowStart, "yyyy-MM-dd", CultureInfo.InvariantCulture, DateTimeStyles.None, out twStart))
						{ Print("  *** ERRO: TradeWindowStart invalido -> usando tudo."); twAll = true; }
					if (!DateTime.TryParseExact(TradeWindowEnd, "yyyy-MM-dd", CultureInfo.InvariantCulture, DateTimeStyles.None, out twEnd))
						{ Print("  *** ERRO: TradeWindowEnd invalido -> usando tudo."); twAll = true; }
				}

				Print("==================================================================");
				Print("  AberturaNYSpecAndersson — pedido do Andersson (11/09), motor AberturaExplosao");
				Print("  Instrumento : " + Instrument.FullName
				      + "   TickSize : " + TickSize.ToString(CultureInfo.InvariantCulture)
				      + "   PointValue : " + pointVal.ToString(CultureInfo.InvariantCulture));
				Print("  Trading Hours : " + (Bars != null && Bars.TradingHours != null ? Bars.TradingHours.Name : "(?)"));
				Print("  Calculate : " + Calculate + "   (Tick Replay TEM que estar ligado no Analyzer)");
				Print("  Abertura=" + HoraAberturaEt.ToString("00") + ":" + MinutoAberturaEt.ToString("00") + " ET"
				      + "  Gatilho=" + TicksParaEntrada + "t  JanelaMonitoramento=" + JanelaMonitoramentoSeg + "s"
				      + "  Contratos=" + Contratos);
				Print("  StopLoss=$" + StopLossDolares + "  TakeProfit=$" + TakeProfitDolares
				      + "  BE: ativa=$" + BeAtivacaoDolar + " protege=$" + BeProtegeDolar + " incremento=$" + BeIncrementoDolar);
				Print("  Janela de trade : " + (twAll ? "TUDO" : (TradeWindowStart + " -> " + TradeWindowEnd)));
				Print("  OutputDir : " + outDir);
				if (Math.Abs(TickSize - 0.25) > 1e-9 || Math.Abs(pointVal - 2.0) > 1e-9)
					Print("  *** AVISO: TickSize/PointValue != MNQ (0.25 / 2.0).");
				Print("==================================================================");

				tradeLog.Add("trade_id,contract,data_pregao,open_abertura,nivel_gatilho,direcao,"
					+ "bar_entrada_ts_et,entrada_preco_fill,bar_saida_ts_et,saida_motivo,saida_preco_fill,"
					+ "contratos,pnl_bruto_pts,pnl_bruto_cash");

				ResetDayState(DateTime.MinValue);
				inTrade = false; exitSent = false; tid = 0;
			}
			else if (State == State.Terminated)
			{
				FlushFiles();
			}
		}

		private void ResetDayState(DateTime d)
		{
			curDay        = d;
			openCaptured  = false;
			openPx        = 0.0;
			tradesToday   = 0;
			flattenMToday = NyseHalfDays.Contains(d.Date) ? HALFDAY_FLATTEN_M : FLATTEN_M;
		}

		protected override void OnBarUpdate()
		{
			totalBars++;
		}

		protected override void OnMarketData(MarketDataEventArgs e)
		{
			if (e.MarketDataType != MarketDataType.Last) return;
			if (BarsInProgress != 0 || CurrentBar < 1) return;

			DateTime et = EmET(e.Time);
			int      m  = et.Hour * 60 + et.Minute;
			DateTime d  = et.Date;
			double   px = e.Price;

			// ---------------- 1. virada de dia ----------------
			if (d != curDay)
				ResetDayState(d);

			// ---------------- 2. captura do OPEN de NY (1o tick >= HoraAberturaEt:MinutoAberturaEt) ----------------
			if (!openCaptured && et.Hour == HoraAberturaEt && et.Minute >= MinutoAberturaEt && et.Minute < MinutoAberturaEt + 15)
			{
				openPx       = px;
				openCaptured = true;
				rthStart     = et;
			}

			// ---------------- 3. flatten por horario ----------------
			if (inTrade && !exitSent && m >= flattenMToday)
			{
				if (curSide > 0) ExitLong ("AbFlat", "AbLong");
				else             ExitShort("AbFlat", "AbShort");
				exitSent = true;
				return;
			}

			// ---------------- 4. gestao da posicao (tick a tick) — BE progressivo em degraus ----------------
			if (inTrade && !exitSent)
			{
				double pnl = (px - curEntry) * curSide * pointVal * Contratos;
				if (pnl > hwmDolar) hwmDolar = pnl;

				// take profit
				if (TakeProfitDolares > 0 && pnl >= TakeProfitDolares)
				{
					if (curSide > 0) ExitLong ("AbAlvo", "AbLong");
					else             ExitShort("AbAlvo", "AbShort");
					exitSent = true;
					return;
				}

				// BE progressivo: 1a ativacao em BeAtivacaoDolar, depois sobe de
				// BeIncrementoDolar em BeIncrementoDolar (ratchet, so' pra cima).
				if (hwmDolar >= BeAtivacaoDolar)
				{
					double degraus = BeIncrementoDolar > 0
						? Math.Floor((hwmDolar - BeAtivacaoDolar) / BeIncrementoDolar)
						: 0.0;
					double novoStop = BeProtegeDolar + degraus * BeIncrementoDolar;
					if (novoStop > stopDolLock) stopDolLock = novoStop;
				}

				if (pnl <= stopDolLock)
				{
					string tag = stopDolLock <= -StopLossDolares + 1e-6 ? "AbStop"
					           : stopDolLock <= BeProtegeDolar + 1e-6   ? "AbBe"
					           : "AbTrail";
					if (curSide > 0) ExitLong (tag, "AbLong");
					else             ExitShort(tag, "AbShort");
					exitSent = true;
					return;
				}
			}

			// ---------------- 5. trigger: TEMPO REAL, so' na 1a JanelaMonitoramentoSeg ----------------
			if (!inTrade && !exitSent && openCaptured && tradesToday == 0
			    && Position.MarketPosition == MarketPosition.Flat)
			{
				double decorrido = (et - rthStart).TotalSeconds;
				if (decorrido <= JanelaMonitoramentoSeg)
				{
					double disp = px - openPx;
					int side = 0;
					if      (disp >=  TicksParaEntrada * tickSz) side = +1;
					else if (disp <= -TicksParaEntrada * tickSz) side = -1;

					if (side != 0)
					{
						curSide   = side;
						curSigDay = d;
						tradesToday++;
						exitSent  = false;
						hwmDolar  = 0.0;
						if (side > 0) EnterLong (Contratos, "AbLong");
						else          EnterShort(Contratos, "AbShort");
					}
				}
			}
		}

		protected override void OnExecutionUpdate(Execution execution, string executionId, double price,
			int quantity, MarketPosition marketPosition, string orderId, DateTime time)
		{
			if (execution.Order == null) return;
			string on = execution.Order.Name;

			// ----- ENTRADA -----
			if (on == "AbLong" || on == "AbShort")
			{
				if (!inTrade)
				{
					inTrade      = true;
					curEntry     = price;
					curEntryTime = time;
					curEntryEt   = EmET(time);
					hwmDolar     = 0.0;
					stopDolLock  = -StopLossDolares;
				}
				return;
			}

			// ----- SAIDA -----
			bool isExit = on == "AbStop" || on == "AbBe" || on == "AbTrail" || on == "AbAlvo"
			              || on == "AbFlat" || on == "Exit on session close";
			if (isExit && inTrade && Position.MarketPosition == MarketPosition.Flat)
			{
				string motivo = on == "AbStop"  ? "STOP"
				              : on == "AbBe"     ? "BE"
				              : on == "AbTrail"  ? "TRAIL"
				              : on == "AbAlvo"   ? "ALVO"
				              : "FLATTEN";

				double pnlPts  = (price - curEntry) * curSide;
				double pnlCash = pnlPts * pointVal * quantity;

				if (twAll || (curSigDay >= twStart && curSigDay <= twEnd))
				{
					nTrades++;
					sumPts  += pnlPts;
					sumCash += pnlCash;
					try
					{
						tradeLog.Add(string.Join(",", new string[] {
							tid.ToString(CultureInfo.InvariantCulture),
							Instrument.MasterInstrument.Name,
							curSigDay.ToString("yyyy-MM-dd"),
							Num(openPx), Num(openPx + curSide * TicksParaEntrada * tickSz),
							curSide > 0 ? "LONG" : "SHORT",
							Iso(curEntryTime), Num(curEntry),
							Iso(time), motivo, Num(price),
							quantity.ToString(CultureInfo.InvariantCulture),
							Num(pnlPts), Num(pnlCash)
						}));
					}
					catch (Exception e) { Print("ERRO montando linha do trade: " + e.Message); }
				}
				tid++;
				inTrade  = false;
				exitSent = false;
			}
		}

		private static string Iso(DateTime t)
		{
			return t.ToString("yyyy-MM-dd'T'HH:mm:ss", CultureInfo.InvariantCulture);
		}
		private static string Num(double v)
		{
			return Math.Round(v, 4).ToString(CultureInfo.InvariantCulture);
		}

		// ===================== FUSO-PROOF (converte Time[0]/e.Time p/ ET) =====================
		private DateTime EmET(DateTime t)
		{
			if (graficoTz != null && etTz != null)
			{
				try
				{
					DateTime utc = TimeZoneInfo.ConvertTimeToUtc(DateTime.SpecifyKind(t, DateTimeKind.Unspecified), graficoTz);
					return TimeZoneInfo.ConvertTimeFromUtc(utc, etTz);
				}
				catch { }
			}
			return t;
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

		private void FlushFiles()
		{
			try
			{
				Print("------------------------------------------------------------------");
				Print("  [FLUSH] AberturaNYSpecAndersson");
				Print("  barras processadas : " + totalBars + "   trades : " + nTrades);

				if (totalBars == 0)
				{
					Print("  *** 0 BARRAS — a estrategia nao processou nenhuma barra.");
					Print("      Causas comuns: (a) contrato sem historico no periodo; (b) Market Replay");
					Print("      nao foi dado Play; (c) instrumento/fuso errado.");
				}

				if (!string.IsNullOrWhiteSpace(outDir) && tradeLog.Count > 1)
				{
					try
					{
						Directory.CreateDirectory(outDir);
						string path = Path.Combine(outDir, "trades_abertura_andersson.csv");
						File.WriteAllLines(path, tradeLog);
						Print("  csv : " + path + "  (" + (tradeLog.Count - 1) + " trades)");
					}
					catch (Exception e) { Print("  ERRO gravando csv: " + e.Message); }
				}

				Print("  soma pts(bruto) : " + Math.Round(sumPts, 2)
				      + "   soma cash(bruto, s/ comissao) : " + Math.Round(sumCash, 2));
				Print("  [NOTA] P&L economico = relatorio do Strategy Analyzer (comissao + deslizamento).");
				Print("------------------------------------------------------------------");
			}
			catch (Exception e)
			{
				Print("ERRO no FlushFiles: " + e.Message);
			}
		}
	}
}
