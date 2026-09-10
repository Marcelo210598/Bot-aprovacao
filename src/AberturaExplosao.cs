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
//  AberturaExplosao — breakout direcional da ABERTURA de NY (explosao da 1a vela)
// -----------------------------------------------------------------------------
//  Ideia (Marcelo, 09/09/2026): liga o bot antes das 09:30 ET, pega o preco de
//  ABERTURA (1o print >= 09:30:00 ET), e entra na direcao do PRIMEIRO rompimento
//  de +-GatilhoTicks desse preco, dentro dos primeiros JanelaLeituraSeg segundos.
//  Protege com breakeven + trailing escalonado. Alvo = $ na posicao.
//
//  >>> TRIGGER CAUSALMENTE HONESTO <<<
//  Roda em Calculate.OnEachTick. O rompimento e' decidido pelo PRIMEIRO tick que
//  negocia atraves do nivel — nao ha ambiguidade (um tick esta em UM preco).
//  Isso corrige o achado de 10/09: no dado OHLC de 1s, ~70% dos pregoes o 1o
//  segundo toca +3t E -3t e o harness Python tinha que ADIVINHAR a ordem (pela
//  cor do bar = look-ahead). Aqui, com tick real (Tick Replay / ao vivo / Market
//  Replay), a ordem e' observada, nao adivinhada.
//
//  PRE-REQUISITOS:
//    - Grafico 1-min (ou menor) + **TICK REPLAY LIGADO** no Strategy Analyzer
//      (Analisador -> engrenagem -> "Tick replay" = marcado). Sem isso o trigger
//      degenera pro fecho da barra de 1min e o teste nao vale.
//    - Fuso global do NT8 = (UTC-05:00) Eastern  -> Time[0] em ET.
//    - Trading Hours : CME US Index Futures ETH.
//    - Instrumento   : MNQ (TickSize 0.25 / PointValue 2.0).
//         * dado longo 2022-2026 : usar o slot de import ("MNQ DEC21" continuo,
//           Databento/Eastern — MESMO da Fase A do ONFADE).
//         * meses recentes com tick : contrato front-month normal.
//
//  COMISSAO / SLIPPAGE: este codigo NAO calcula nenhum dos dois.
//    - Slippage -> campo "Deslizamento" do Strategy Analyzer.
//    - Comissao -> template "Modelo de comissao" do Analyzer.
//  O CSV daqui registra fills BRUTOS (checagem de mecanica). Veredito economico
//  = relatorio do Analyzer.
//
//  PARAMETROS (o cliente vai poder mexer quando o bot for vendido):
//    Contratos          6   (25K aceita ate 4 full / 40 micros)
//    AlvoDolar          500  ($ de P&L NA POSICAO p/ take-profit; 0 = sem alvo)
//    GatilhoTicks        3
//    JanelaLeituraSeg  180
//    StopTicks           6
//    BeTicks             6   (maxima a favor p/ travar stop em 0)
//    TrailTicks          6   (distancia do trailing atras da maxima, apos o BE)
//
//  Contrato matematico espelhado em backtest/abertura_harness.py (referencia
//  logica, granularidade 1s — nao bit-exact com tick, e' esperado).
//
//  NAO e' bot de producao. `BotAprovacao.cs` e o ONFADE seguem intactos.
// =============================================================================

namespace NinjaTrader.NinjaScript.Strategies
{
	public class AberturaExplosao : Strategy
	{
		private double tickSz = 0.25;                     // = TickSize (setado em DataLoaded; adapta MNQ/MYM/...)

		private const int SIG_FIRST_M        = 9 * 60 + 30;   // 09:30 ET (abertura de NY)
		private const int FLATTEN_M          = 15 * 60 + 55;  // 15:55 ET
		private const int HALFDAY_FLATTEN_M  = 12 * 60 + 55;  // 12:55 ET (early close)

		private static readonly HashSet<DateTime> NyseHalfDays = new HashSet<DateTime>
		{
			new DateTime(2022,11,25), new DateTime(2022,7,3),  new DateTime(2023,7,3),
			new DateTime(2023,11,24), new DateTime(2024,7,3),  new DateTime(2024,11,29),
			new DateTime(2024,12,24), new DateTime(2025,7,3),  new DateTime(2025,11,28),
			new DateTime(2025,12,24), new DateTime(2026,11,27),
		};

		// ---------- parametros ----------
		[NinjaScriptProperty] [Range(1, 40)]
		[Display(Name="Contratos", Order=1, GroupName="1. Abertura")]
		public int Contratos { get; set; }

		[NinjaScriptProperty] [Range(0, 100000)]
		[Display(Name="AlvoDolar ($ na posicao; 0 = sem alvo)", Order=2, GroupName="1. Abertura")]
		public double AlvoDolar { get; set; }

		[NinjaScriptProperty] [Range(1, 50)]
		[Display(Name="GatilhoTicks", Order=3, GroupName="1. Abertura")]
		public int GatilhoTicks { get; set; }

		[NinjaScriptProperty] [Range(5, 900)]
		[Display(Name="JanelaLeituraSeg", Order=4, GroupName="1. Abertura")]
		public int JanelaLeituraSeg { get; set; }

		[NinjaScriptProperty] [Range(1, 200)]
		[Display(Name="StopTicks", Order=5, GroupName="1. Abertura")]
		public int StopTicks { get; set; }

		[NinjaScriptProperty] [Range(1, 400)]
		[Display(Name="BeTicks (maxima a favor p/ travar BE)", Order=6, GroupName="1. Abertura")]
		public int BeTicks { get; set; }

		[NinjaScriptProperty] [Range(1, 400)]
		[Display(Name="TrailTicks (distancia do trailing apos BE)", Order=7, GroupName="1. Abertura")]
		public int TrailTicks { get; set; }

		[NinjaScriptProperty]
		[Display(Name="InverterDirecao (fada a abertura em vez de seguir)", Order=8, GroupName="1. Abertura")]
		public bool InverterDirecao { get; set; }

		[NinjaScriptProperty]
		[Display(Name="TradeWindowStart (yyyy-MM-dd, vazio = tudo)", Order=8, GroupName="2. Controle")]
		public string TradeWindowStart { get; set; }

		[NinjaScriptProperty]
		[Display(Name="TradeWindowEnd (yyyy-MM-dd, vazio = tudo)", Order=9, GroupName="2. Controle")]
		public string TradeWindowEnd { get; set; }

		[NinjaScriptProperty]
		[Display(Name="OutputDir (vazio = Documentos\\abertura)", Order=10, GroupName="2. Controle")]
		public string OutputDir { get; set; }

		// ---------- estado diario ----------
		private DateTime curDay;
		private bool     openCaptured;
		private double   openPx;
		private DateTime openBarStart;      // ET: inicio da barra de abertura (09:30)
		private int      tradesToday;
		private int      flattenMToday;

		// ---------- estado da posicao ----------
		private bool     inTrade;
		private int      curSide;           // +1 long, -1 short
		private double   curEntry;
		private DateTime curEntryTime;
		private DateTime curSigDay;
		private double   hwmFav;            // maxima a favor, em pontos
		private bool     beArmed;
		private double   stopPx;            // preco do stop sintetico corrente
		private double   tpPx;              // preco do alvo ($ -> preco); NaN = sem alvo
		private bool     exitSent;

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

		// ---------- fuso-proof (converte Time[0] p/ ET, seja qual for o fuso do grafico) ----------
		private TimeZoneInfo etTz;
		private TimeZoneInfo graficoTz;

		protected override void OnStateChange()
		{
			if (State == State.SetDefaults)
			{
				Description                   = @"Breakout direcional da abertura de NY (explosao da 1a vela). Trigger no 1o tick que rompe +-GatilhoTicks do preco de abertura, dentro de JanelaLeituraSeg. BE + trailing escalonado + alvo em $. Rodar em Tick Replay. Comissao/slippage = Strategy Analyzer.";
				Name                          = "AberturaExplosao";
				Calculate                     = Calculate.OnEachTick;
				EntriesPerDirection           = 1;
				EntryHandling                 = EntryHandling.AllEntries;
				IsExitOnSessionCloseStrategy  = true;
				ExitOnSessionCloseSeconds     = 30;
				IsFillLimitOnTouch            = false;
				MaximumBarsLookBack           = MaximumBarsLookBack.TwoHundredFiftySix;
				OrderFillResolution           = OrderFillResolution.Standard;
				Slippage                      = 0;               // Analyzer controla ("Deslizamento")
				StartBehavior                 = StartBehavior.WaitUntilFlat;
				TimeInForce                   = TimeInForce.Gtc;
				TraceOrders                   = false;
				RealtimeErrorHandling         = RealtimeErrorHandling.StopCancelClose;
				StopTargetHandling            = StopTargetHandling.PerEntryExecution;
				BarsRequiredToTrade           = 1;
				IsInstantiatedOnEachOptimizationIteration = false;

				Contratos        = 6;
				AlvoDolar        = 500.0;
				GatilhoTicks     = 3;
				JanelaLeituraSeg = 180;
				StopTicks        = 6;
				BeTicks          = 6;
				TrailTicks       = 6;
				InverterDirecao  = false;
				TradeWindowStart = "";
				TradeWindowEnd   = "";
				OutputDir        = "";
			}
			else if (State == State.DataLoaded)
			{
				pointVal = Instrument.MasterInstrument.PointValue;
				tickSz   = TickSize;

				try { etTz = TimeZoneInfo.FindSystemTimeZoneById("Eastern Standard Time"); } catch { etTz = null; }
				graficoTz = ResolveFusoGrafico();
				Print("  Fuso do grafico detectado : " + (graficoTz != null ? graficoTz.Id : "(nao detectado -> assume ET)"));

				outDir = string.IsNullOrWhiteSpace(OutputDir)
					? Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.MyDocuments), "abertura")
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
				Print("  AberturaExplosao — abertura de NY   [build: v3 10/09 - timing ok + InverterDirecao]");
				Print("  Instrumento : " + Instrument.FullName
				      + "   TickSize : " + TickSize.ToString(CultureInfo.InvariantCulture)
				      + "   PointValue : " + pointVal.ToString(CultureInfo.InvariantCulture));
				Print("  Trading Hours : " + (Bars != null && Bars.TradingHours != null ? Bars.TradingHours.Name : "(?)"));
				Print("  TimeZone da maquina : " + TimeZoneInfo.Local.Id + "  (Time[0] TEM que estar em ET)");
				Print("  Calculate : " + Calculate + "   (Tick Replay TEM que estar ligado no Analyzer)");
				Print("  Contratos=" + Contratos + "  AlvoDolar=" + AlvoDolar + "  Gatilho=" + GatilhoTicks + "t"
				      + "  Janela=" + JanelaLeituraSeg + "s  Stop=" + StopTicks + "t  BE=" + BeTicks + "t  Trail=" + TrailTicks + "t");
				Print("  Janela de trade : " + (twAll ? "TUDO" : (TradeWindowStart + " -> " + TradeWindowEnd)));
				Print("  OutputDir : " + outDir);
				if (Math.Abs(TickSize - 0.25) > 1e-9 || Math.Abs(pointVal - 2.0) > 1e-9)
					Print("  *** AVISO: TickSize/PointValue != MNQ (0.25 / 2.0).");
				Print("==================================================================");

				tradeLog.Add("trade_id,contract,data_pregao,open_0930,nivel_gatilho,direcao,"
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
			if (CurrentBar < 1) return;
			totalBars++;

			// NT8 carimba a barra intraday no FECHO. Numa barra em formacao (OnEachTick),
			// Time[0] ja retorna o horario de fecho -> subtrai 1 min p/ ter o INICIO da barra.
			// (era esse o bug: as 09:29 o codigo lia "09:30" e entrava antes da 1a vela.)
			DateTime etStart = EmET(Time[0]).AddMinutes(-1);   // FUSO-PROOF + inicio da barra
			int      m   = etStart.Hour * 60 + etStart.Minute;
			DateTime d   = etStart.Date;
			double   px  = Close[0];                      // ultimo preco (cada tick)

			// ---------------- 1. virada de dia ----------------
			if (d != curDay)
				ResetDayState(d);

			// ---------------- 2. captura do preco de abertura (barra que COMECA >= 09:30:00 ET) ----------------
			if (!openCaptured && etStart.Hour == 9 && etStart.Minute >= 30 && etStart.Minute < 40)
			{
				openPx       = Open[0];                   // open da 1a barra do RTH
				openCaptured = true;
				openBarStart = etStart;
			}

			// ---------------- 3. flatten por horario ----------------
			if (inTrade && !exitSent && m >= flattenMToday)
			{
				if (curSide > 0) ExitLong ("AbFlat", "AbLong");
				else             ExitShort("AbFlat", "AbShort");
				exitSent = true;
				return;
			}

			// ---------------- 4. gestao da posicao (tick a tick) ----------------
			if (inTrade && !exitSent)
			{
				double favPts = (px - curEntry) * curSide;         // excursao a favor, em pontos
				if (favPts > hwmFav) hwmFav = favPts;

				// alvo em $ -> preco alvo (setado no fill); checa por preco
				if (!double.IsNaN(tpPx) &&
				    ((curSide > 0 && High[0] >= tpPx) || (curSide < 0 && Low[0] <= tpPx)))
				{
					if (curSide > 0) ExitLong ("AbAlvo", "AbLong");
					else             ExitShort("AbAlvo", "AbShort");
					exitSent = true;
					return;
				}

				// breakeven: trava stop em 0 quando a maxima a favor >= BeTicks
				if (!beArmed && hwmFav >= BeTicks * tickSz - 1e-9)
				{
					beArmed = true;
					double be = curEntry;
					stopPx = curSide > 0 ? Math.Max(stopPx, be) : Math.Min(stopPx, be);
				}
				// trailing: apos o BE, stop = maxima - TrailTicks, so aperta
				if (beArmed)
				{
					double trail = curEntry + curSide * (hwmFav - TrailTicks * tickSz);
					stopPx = curSide > 0 ? Math.Max(stopPx, trail) : Math.Min(stopPx, trail);
				}

				// stop sintetico: saida a mercado quando o preco cruza
				if ((curSide > 0 && Low[0] <= stopPx) || (curSide < 0 && High[0] >= stopPx))
				{
					string tag = !beArmed ? "AbStop" : (Math.Abs(stopPx - curEntry) < tickSz / 2 ? "AbBe" : "AbTrail");
					if (curSide > 0) ExitLong (tag, "AbLong");
					else             ExitShort(tag, "AbShort");
					exitSent = true;
					return;
				}
			}

			// ---------------- 5. trigger de entrada (1o tick que rompe, dentro da janela) ----------------
			if (!inTrade && !exitSent && openCaptured && tradesToday == 0
			    && Position.MarketPosition == MarketPosition.Flat
			    && (etStart - openBarStart).TotalSeconds <= JanelaLeituraSeg)
			{
				double up = openPx + GatilhoTicks * tickSz;
				double dn = openPx - GatilhoTicks * tickSz;
				int side = 0;
				if      (High[0] >= up) side = +1;
				else if (Low[0]  <= dn) side = -1;

				if (side != 0 && InverterDirecao) side = -side;   // fada a abertura

				if (side != 0)
				{
					curSide      = side;
					curSigDay    = d;
					tradesToday++;
					exitSent     = false;
					beArmed      = false;
					hwmFav       = 0.0;
					if (side > 0) EnterLong (Contratos, "AbLong");
					else          EnterShort(Contratos, "AbShort");
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
					stopPx       = price - curSide * StopTicks * tickSz;
					tpPx         = AlvoDolar > 0
						? price + curSide * (AlvoDolar / (pointVal * Contratos))
						: double.NaN;
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
							Num(openPx), Num(openPx + curSide * GatilhoTicks * tickSz),
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

		// ===================== FUSO-PROOF (converte Time[0] p/ ET) =====================
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
			return t;   // fallback: assume grafico ja em ET
		}

		// Le por reflection o fuso de exibicao do NT8 (Tools > Options > General > Time zone).
		// Reflection p/ nunca quebrar a compilacao entre versoes: se nao achar, retorna null (fallback ET).
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
				Print("  [FLUSH] AberturaExplosao");
				Print("  barras processadas : " + totalBars + "   trades : " + nTrades);

				if (totalBars == 0)
				{
					Print("  *** 0 BARRAS — a estrategia nao processou nenhuma barra.");
					Print("      Causas comuns: (a) contrato sem historico no periodo (ex: 'MYM JUN26'");
					Print("      num replay de jul/ago — use o FRONT-MONTH: MNQ SEP26); (b) Market Replay");
					Print("      nao foi dado Play; (c) instrumento/fuso errado.");
				}

				if (!string.IsNullOrWhiteSpace(outDir) && tradeLog.Count > 1)
				{
					try
					{
						Directory.CreateDirectory(outDir);
						string path = Path.Combine(outDir, "trades_abertura_native.csv");
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
