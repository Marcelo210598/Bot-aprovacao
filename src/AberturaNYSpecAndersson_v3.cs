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
//  AberturaNYSpecAndersson_v3 — MESMO motor/gestao do V2 (14/09/2026), mas com
//  DUAS JANELAS DE ENTRADA independentes (manha + noite), cada uma com seu
//  proprio horario de abertura E seu proprio horario de flatten, ligadas por
//  toggle separado:
//
//    AtivarAberturaManha  -> HoraAberturaManhaEt:MinutoAberturaManhaEt (default 09:30 ET)
//                            flatten em HoraFlattenManhaEt:MinutoFlattenManhaEt (default 15:55 ET)
//    AtivarAberturaNoite  -> HoraAberturaNoiteEt:MinutoAberturaNoiteEt (default 18:00 ET
//                            = 19h Brasilia no horario de verao americano)
//                            flatten em HoraFlattenNoiteEt:MinutoFlattenNoiteEt (default 20:00 ET
//                            = 21h Brasilia; janela 19-21h BRT que ja tinha aparecido antes
//                            como "acelerador" da noturna no projeto)
//
//  Pedido do Marcelo (14/09 tarde): testar SO' a abertura noturna em junho/2026
//  primeiro; se o resultado for satisfatorio, ligar as duas janelas juntas
//  (manha + noite) e testar jun+jul. Por isso o .cs ja fica pronto pras duas,
//  mas com a manha DESLIGADA por default (`AtivarAberturaManha=false`).
//
//  Gatilho, stop/alvo em $ e break-even progressivo em degraus = EXATAMENTE
//  o mesmo mecanismo do V2 (4 contratos, stop $150, alvo $500, BE ativa
//  $60/protege $0/incremento $30) — nao mudei a gestao, so' a abertura ganhou
//  2 janelas em vez de 1. V2 fica INTOCADO em `AberturaNYSpecAndersson_v2.cs`
//  (resultado registrado: 45 dias jun+jul, +$408,00, PF 1,34, DD continuo $524).
//
//  ⚠️ Limitacao conhecida: o ajuste de meio-expediente (`NyseHalfDays`, fecho
//  12:55 ET) so' se aplica ao flatten da janela da MANHA (e' o fecho cash da
//  NYSE). A janela da NOITE usa sempre `HoraFlattenNoiteEt` fixo, mesmo em
//  vespera de feriado — caso raro, nao tratado aqui.
//
//  So' uma posicao aberta por vez (a 2a janela so' dispara se a 1a ja fechou).
//  Rodar em Tick Replay. NAO e' bot de producao. `BotAprovacao.cs` e o
//  ONFADE seguem intactos.
// =============================================================================

namespace NinjaTrader.NinjaScript.Strategies
{
	public class AberturaNYSpecAndersson_v3 : Strategy
	{
		private double tickSz = 0.25;

		private static readonly HashSet<DateTime> NyseHalfDays = new HashSet<DateTime>
		{
			new DateTime(2022,11,25), new DateTime(2022,7,3),  new DateTime(2023,7,3),
			new DateTime(2023,11,24), new DateTime(2024,7,3),  new DateTime(2024,11,29),
			new DateTime(2024,12,24), new DateTime(2025,7,3),  new DateTime(2025,11,28),
			new DateTime(2025,12,24), new DateTime(2026,11,27),
		};

		// ---------- parametros: janela da MANHA ----------
		[NinjaScriptProperty]
		[Display(Name="AtivarAberturaManha", Order=1, GroupName="1. Janela Manha")]
		public bool AtivarAberturaManha { get; set; }

		[NinjaScriptProperty] [Range(0, 23)]
		[Display(Name="HoraAberturaManhaEt (9 = 09:30 ET, ~10:30 Brasilia no horario de verao)", Order=2, GroupName="1. Janela Manha")]
		public int HoraAberturaManhaEt { get; set; }

		[NinjaScriptProperty] [Range(0, 59)]
		[Display(Name="MinutoAberturaManhaEt", Order=3, GroupName="1. Janela Manha")]
		public int MinutoAberturaManhaEt { get; set; }

		[NinjaScriptProperty] [Range(0, 23)]
		[Display(Name="HoraFlattenManhaEt (15 = 15:55 ET, fecho RTH)", Order=4, GroupName="1. Janela Manha")]
		public int HoraFlattenManhaEt { get; set; }

		[NinjaScriptProperty] [Range(0, 59)]
		[Display(Name="MinutoFlattenManhaEt", Order=5, GroupName="1. Janela Manha")]
		public int MinutoFlattenManhaEt { get; set; }

		// ---------- parametros: janela da NOITE ----------
		[NinjaScriptProperty]
		[Display(Name="AtivarAberturaNoite", Order=1, GroupName="2. Janela Noite")]
		public bool AtivarAberturaNoite { get; set; }

		[NinjaScriptProperty] [Range(0, 23)]
		[Display(Name="HoraAberturaNoiteEt (18 = 18:00 ET = 19h Brasilia no horario de verao)", Order=2, GroupName="2. Janela Noite")]
		public int HoraAberturaNoiteEt { get; set; }

		[NinjaScriptProperty] [Range(0, 59)]
		[Display(Name="MinutoAberturaNoiteEt", Order=3, GroupName="2. Janela Noite")]
		public int MinutoAberturaNoiteEt { get; set; }

		[NinjaScriptProperty] [Range(0, 23)]
		[Display(Name="HoraFlattenNoiteEt (20 = 20:00 ET = 21h Brasilia)", Order=4, GroupName="2. Janela Noite")]
		public int HoraFlattenNoiteEt { get; set; }

		[NinjaScriptProperty] [Range(0, 59)]
		[Display(Name="MinutoFlattenNoiteEt", Order=5, GroupName="2. Janela Noite")]
		public int MinutoFlattenNoiteEt { get; set; }

		// ---------- parametros: gatilho (compartilhado pelas 2 janelas) ----------
		[NinjaScriptProperty] [Range(1, 40)]
		[Display(Name="Contratos", Order=1, GroupName="3. Gatilho")]
		public int Contratos { get; set; }

		[NinjaScriptProperty] [Range(5, 900)]
		[Display(Name="JanelaMonitoramentoSeg (60 = so' a 1a vela de 1min, como pedido)", Order=2, GroupName="3. Gatilho")]
		public int JanelaMonitoramentoSeg { get; set; }

		[NinjaScriptProperty] [Range(1, 200)]
		[Display(Name="TicksParaEntrada", Order=3, GroupName="3. Gatilho")]
		public int TicksParaEntrada { get; set; }

		// ---------- parametros: stop/alvo/BE (compartilhado, igual V2) ----------
		[NinjaScriptProperty] [Range(1, 100000)]
		[Display(Name="StopLossDolares ($ na posicao)", Order=1, GroupName="4. Stop e Alvo")]
		public double StopLossDolares { get; set; }

		[NinjaScriptProperty] [Range(0, 100000)]
		[Display(Name="TakeProfitDolares ($ na posicao; 0 = sem alvo)", Order=2, GroupName="4. Stop e Alvo")]
		public double TakeProfitDolares { get; set; }

		[NinjaScriptProperty] [Range(0, 100000)]
		[Display(Name="BeAtivacaoDolar (lucro $ pra ativar a 1a protecao)", Order=1, GroupName="5. Break-Even Progressivo")]
		public double BeAtivacaoDolar { get; set; }

		[NinjaScriptProperty] [Range(0, 100000)]
		[Display(Name="BeProtegeDolar (quanto trava no stop na 1a ativacao; 0 = breakeven)", Order=2, GroupName="5. Break-Even Progressivo")]
		public double BeProtegeDolar { get; set; }

		[NinjaScriptProperty] [Range(0, 100000)]
		[Display(Name="BeIncrementoDolar (a cada esse $ a mais de lucro, sobe o stop o mesmo valor; 0 = trava 1x e para)", Order=3, GroupName="5. Break-Even Progressivo")]
		public double BeIncrementoDolar { get; set; }

		[NinjaScriptProperty]
		[Display(Name="TradeWindowStart (yyyy-MM-dd, vazio = tudo)", Order=1, GroupName="6. Controle")]
		public string TradeWindowStart { get; set; }

		[NinjaScriptProperty]
		[Display(Name="TradeWindowEnd (yyyy-MM-dd, vazio = tudo)", Order=2, GroupName="6. Controle")]
		public string TradeWindowEnd { get; set; }

		[NinjaScriptProperty]
		[Display(Name="OutputDir (vazio = Documentos\\abertura_andersson_v3)", Order=3, GroupName="6. Controle")]
		public string OutputDir { get; set; }

		// ---------- estado diario ----------
		private DateTime curDay;

		private bool     manhaOpenCaptured;
		private double   manhaOpenPx;
		private DateTime manhaRthStart;
		private bool     manhaTradeDone;
		private int      flattenMManha;

		private bool     noiteOpenCaptured;
		private double   noiteOpenPx;
		private DateTime noiteRthStart;
		private bool     noiteTradeDone;
		private int      flattenMNoite;

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
		private string   curJanela;     // "MANHA" ou "NOITE" — da entrada corrente
		private double   curOpenPxRef;  // openPx da janela que gerou a entrada corrente
		private int      curFlattenM;   // horario de flatten (minutos do dia ET) da entrada corrente

		// ---------- acumuladores de fill parcial (entrada/saida podem encher em >1 pedaco) ----------
		private int      entryQtyFilled;
		private double   entryPxQtySum;
		private int      exitQtyFilled;
		private double   exitPxQtySum;
		private double   exitCashAccum;

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
		private int      nTradesManha, nTradesNoite;
		private double   sumCashManha, sumCashNoite;

		// ---------- fuso-proof ----------
		private TimeZoneInfo etTz;
		private TimeZoneInfo graficoTz;

		protected override void OnStateChange()
		{
			if (State == State.SetDefaults)
			{
				Description                   = @"Abertura de NY — V3 (14/09/2026): motor V2 (gatilho de N ticks na 1a vela + stop/alvo em $ + BE progressivo), agora com 2 janelas de entrada independentes (manha 09:30 ET / noite 18:00 ET), cada uma com seu horario de flatten. Default: so' a noite ativada. Rodar em Tick Replay.";
				Name                          = "AberturaNYSpecAndersson_v3";
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

				// Pedido do Marcelo (14/09): so' NOITE ativada por default, testar
				// junho/2026 primeiro. Manha fica pronta mas desligada.
				AtivarAberturaManha    = false;
				HoraAberturaManhaEt    = 9;
				MinutoAberturaManhaEt  = 30;
				HoraFlattenManhaEt     = 15;
				MinutoFlattenManhaEt   = 55;

				AtivarAberturaNoite    = true;
				HoraAberturaNoiteEt    = 18;
				MinutoAberturaNoiteEt  = 0;
				HoraFlattenNoiteEt     = 20;
				MinutoFlattenNoiteEt   = 0;

				// Gatilho/gestao — igual V2
				Contratos              = 4;
				JanelaMonitoramentoSeg = 60;
				TicksParaEntrada       = 10;
				StopLossDolares        = 150;
				TakeProfitDolares      = 500;
				BeAtivacaoDolar        = 60;
				BeProtegeDolar         = 0;
				BeIncrementoDolar      = 30;

				// Pedido do Marcelo (14/09): testar junho/2026 primeiro.
				TradeWindowStart       = "2026-06-01";
				TradeWindowEnd         = "2026-06-30";
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
					? Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.MyDocuments), "abertura_andersson_v3")
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
				Print("  AberturaNYSpecAndersson_v3 — motor V2, 2 janelas independentes");
				Print("  Instrumento : " + Instrument.FullName
				      + "   TickSize : " + TickSize.ToString(CultureInfo.InvariantCulture)
				      + "   PointValue : " + pointVal.ToString(CultureInfo.InvariantCulture));
				Print("  Trading Hours : " + (Bars != null && Bars.TradingHours != null ? Bars.TradingHours.Name : "(?)"));
				Print("  Calculate : " + Calculate + "   (Tick Replay TEM que estar ligado no Analyzer)");
				Print("  MANHA : ativa=" + AtivarAberturaManha
				      + "  abertura=" + HoraAberturaManhaEt.ToString("00") + ":" + MinutoAberturaManhaEt.ToString("00") + " ET"
				      + "  flatten=" + HoraFlattenManhaEt.ToString("00") + ":" + MinutoFlattenManhaEt.ToString("00") + " ET");
				Print("  NOITE : ativa=" + AtivarAberturaNoite
				      + "  abertura=" + HoraAberturaNoiteEt.ToString("00") + ":" + MinutoAberturaNoiteEt.ToString("00") + " ET"
				      + "  flatten=" + HoraFlattenNoiteEt.ToString("00") + ":" + MinutoFlattenNoiteEt.ToString("00") + " ET");
				Print("  Gatilho=" + TicksParaEntrada + "t  JanelaMonitoramento=" + JanelaMonitoramentoSeg + "s  Contratos=" + Contratos);
				Print("  StopLoss=$" + StopLossDolares + "  TakeProfit=$" + TakeProfitDolares
				      + "  BE: ativa=$" + BeAtivacaoDolar + " protege=$" + BeProtegeDolar + " incremento=$" + BeIncrementoDolar);
				Print("  Janela de trade (filtro do relatorio) : " + (twAll ? "TUDO" : (TradeWindowStart + " -> " + TradeWindowEnd)));
				Print("  OutputDir : " + outDir);
				if (Math.Abs(TickSize - 0.25) > 1e-9 || Math.Abs(pointVal - 2.0) > 1e-9)
					Print("  *** AVISO: TickSize/PointValue != MNQ (0.25 / 2.0).");
				Print("==================================================================");

				tradeLog.Add("trade_id,contract,data_pregao,janela,open_abertura,nivel_gatilho,direcao,"
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
			curDay            = d;
			bool halfDay      = NyseHalfDays.Contains(d.Date);

			manhaOpenCaptured = false;
			manhaOpenPx       = 0.0;
			manhaTradeDone    = false;
			flattenMManha     = halfDay ? (12 * 60 + 55) : (HoraFlattenManhaEt * 60 + MinutoFlattenManhaEt);

			noiteOpenCaptured = false;
			noiteOpenPx       = 0.0;
			noiteTradeDone    = false;
			flattenMNoite     = HoraFlattenNoiteEt * 60 + MinutoFlattenNoiteEt;
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

			// ---------------- 2. captura do OPEN de cada janela ativa ----------------
			if (AtivarAberturaManha && !manhaOpenCaptured
			    && et.Hour == HoraAberturaManhaEt && et.Minute >= MinutoAberturaManhaEt && et.Minute < MinutoAberturaManhaEt + 15)
			{
				manhaOpenPx       = px;
				manhaOpenCaptured = true;
				manhaRthStart     = et;
			}
			if (AtivarAberturaNoite && !noiteOpenCaptured
			    && et.Hour == HoraAberturaNoiteEt && et.Minute >= MinutoAberturaNoiteEt && et.Minute < MinutoAberturaNoiteEt + 15)
			{
				noiteOpenPx       = px;
				noiteOpenCaptured = true;
				noiteRthStart     = et;
			}

			// ---------------- 3. flatten por horario (da janela que gerou a entrada) ----------------
			if (inTrade && !exitSent && m >= curFlattenM)
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

			// ---------------- 5. trigger: MANHA primeiro, depois NOITE (so' 1 entrada por tick) ----------------
			if (!inTrade && !exitSent && Position.MarketPosition == MarketPosition.Flat)
			{
				if (AtivarAberturaManha && manhaOpenCaptured && !manhaTradeDone
				    && (et - manhaRthStart).TotalSeconds <= JanelaMonitoramentoSeg)
				{
					int side = DetectaSide(px, manhaOpenPx);
					if (side != 0)
					{
						manhaTradeDone = true;
						AbreEntrada(side, d, "MANHA", manhaOpenPx, flattenMManha);
						return;
					}
				}
				else if (AtivarAberturaNoite && noiteOpenCaptured && !noiteTradeDone
				         && (et - noiteRthStart).TotalSeconds <= JanelaMonitoramentoSeg)
				{
					int side = DetectaSide(px, noiteOpenPx);
					if (side != 0)
					{
						noiteTradeDone = true;
						AbreEntrada(side, d, "NOITE", noiteOpenPx, flattenMNoite);
					}
				}
			}
		}

		private int DetectaSide(double px, double openPxRef)
		{
			double disp = px - openPxRef;
			if      (disp >=  TicksParaEntrada * tickSz) return +1;
			else if (disp <= -TicksParaEntrada * tickSz) return -1;
			return 0;
		}

		private void AbreEntrada(int side, DateTime d, string janela, double openPxRef, int flattenM)
		{
			curSide      = side;
			curSigDay    = d;
			curJanela    = janela;
			curOpenPxRef = openPxRef;
			curFlattenM  = flattenM;
			exitSent     = false;
			hwmDolar     = 0.0;
			if (side > 0) EnterLong (Contratos, "AbLong");
			else          EnterShort(Contratos, "AbShort");
		}

		protected override void OnExecutionUpdate(Execution execution, string executionId, double price,
			int quantity, MarketPosition marketPosition, string orderId, DateTime time)
		{
			if (execution.Order == null) return;
			string on = execution.Order.Name;

			// ----- ENTRADA (pode encher em >1 fill parcial — acumula media ponderada) -----
			if (on == "AbLong" || on == "AbShort")
			{
				if (!inTrade)
				{
					inTrade        = true;
					curEntryTime   = time;
					curEntryEt     = EmET(time);
					hwmDolar       = 0.0;
					stopDolLock    = -StopLossDolares;
					entryQtyFilled = 0;
					entryPxQtySum  = 0.0;
					exitQtyFilled  = 0;
					exitPxQtySum   = 0.0;
					exitCashAccum  = 0.0;
				}
				entryQtyFilled += quantity;
				entryPxQtySum  += price * quantity;
				curEntry        = entryPxQtySum / entryQtyFilled;  // media ponderada, atualiza a cada fill
				return;
			}

			// ----- SAIDA (idem — acumula TODOS os fills ate a posicao ficar flat) -----
			bool isExit = on == "AbStop" || on == "AbBe" || on == "AbTrail" || on == "AbAlvo"
			              || on == "AbFlat" || on == "Exit on session close";
			if (isExit && inTrade)
			{
				string motivo = on == "AbStop"  ? "STOP"
				              : on == "AbBe"     ? "BE"
				              : on == "AbTrail"  ? "TRAIL"
				              : on == "AbAlvo"   ? "ALVO"
				              : "FLATTEN";

				exitQtyFilled += quantity;
				exitPxQtySum  += price * quantity;
				exitCashAccum += (price - curEntry) * curSide * pointVal * quantity;

				// so' fecha/loga o trade quando TODA a posicao saiu (fills parciais nao contam ainda)
				if (Position.MarketPosition != MarketPosition.Flat)
					return;

				double avgExitPx = exitPxQtySum / exitQtyFilled;
				double pnlCash   = exitCashAccum;
				double pnlPts    = pnlCash / (pointVal * exitQtyFilled);  // media de pontos por contrato

				if (twAll || (curSigDay >= twStart && curSigDay <= twEnd))
				{
					nTrades++;
					sumPts  += pnlPts;
					sumCash += pnlCash;
					if (curJanela == "MANHA") { nTradesManha++; sumCashManha += pnlCash; }
					else                      { nTradesNoite++; sumCashNoite += pnlCash; }
					try
					{
						tradeLog.Add(string.Join(",", new string[] {
							tid.ToString(CultureInfo.InvariantCulture),
							Instrument.MasterInstrument.Name,
							curSigDay.ToString("yyyy-MM-dd"),
							curJanela,
							Num(curOpenPxRef), Num(curOpenPxRef + curSide * TicksParaEntrada * tickSz),
							curSide > 0 ? "LONG" : "SHORT",
							Iso(curEntryTime), Num(curEntry),
							Iso(time), motivo, Num(avgExitPx),
							exitQtyFilled.ToString(CultureInfo.InvariantCulture),
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
				// Guard cedo: com 0 barras a estrategia nunca chegou a tocar em OnMarketData,
				// entao nao ha nada consistente pra flushar. Sai ANTES de qualquer outra
				// operacao (mesmo Print composto) - mesmo padrao usado no OnFadeHarness.cs
				// pra evitar o "Index was out of range" quando o Analyzer/Replay nao rodou
				// dado nenhum (estrategia so' foi adicionada/configurada, sem dar Play).
				if (totalBars == 0)
				{
					Print("==================================================================");
					Print("  *** 0 BARRAS — a estrategia nao processou nenhuma barra.");
					Print("      Causas comuns: (a) contrato sem historico no periodo; (b) Market Replay/");
					Print("      Analyzer nao foi dado Play; (c) instrumento/fuso errado.");
					Print("  Nenhum arquivo escrito.");
					Print("==================================================================");
					return;
				}

				Print("------------------------------------------------------------------");
				Print("  [FLUSH] AberturaNYSpecAndersson_v3");
				Print("  barras processadas : " + totalBars + "   trades : " + nTrades
				      + "  (manha=" + nTradesManha + " / noite=" + nTradesNoite + ")");

				if (!string.IsNullOrWhiteSpace(outDir) && tradeLog.Count > 1)
				{
					try
					{
						Directory.CreateDirectory(outDir);
						string path = Path.Combine(outDir, "trades_abertura_andersson_v3.csv");
						File.WriteAllLines(path, tradeLog);
						Print("  csv : " + path + "  (" + (tradeLog.Count - 1) + " trades)");
					}
					catch (Exception e) { Print("  ERRO gravando csv: " + e.Message); }
				}

				Print("  soma pts(bruto) : " + Math.Round(sumPts, 2)
				      + "   soma cash(bruto, s/ comissao) : " + Math.Round(sumCash, 2));
				Print("  manha : cash(bruto) = " + Math.Round(sumCashManha, 2) + "   noite : cash(bruto) = " + Math.Round(sumCashNoite, 2));
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
