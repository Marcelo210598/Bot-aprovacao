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
using System.Globalization;
#endregion

// =============================================================================
//  NomadeBot_GapAndGo  —  candidata C, teste no Strategy Analyzer (02/09/2026)
// -----------------------------------------------------------------------------
//  POR QUE ESTE BOT EXISTE:
//    A candidata B (event 8h30 ET) e a candidata A (momentum continuation) foram
//    testadas em Python (2022-2026) e NAO tem edge. A candidata C tem 2 metades:
//      - gap-FILL (fade o gap)  -> CATASTROFE (PF ~0,2 — o MNQ TENDE, nao volta)
//      - gap-and-GO (a favor)   -> PF ~1,29 IS 2022-2025 E ~1,30 no holdout 2026,
//                                  POSITIVO TODO ANO (2022 1,27 / 23 1,27 / 24 1,32
//                                  / 25 1,30 / 26 1,30). 1o sinal robusto do projeto.
//
//  ⚠️ RESSALVAS (ler docs/estrategia-nova-2026-09.md + historico/2026-09-02.md):
//    1. O motor Python do projeto e ~40% otimista no PF. PF 1,29 la pode virar
//       ~1,0-1,1 AQUI. ESTE ANALYZER e' o juiz. Corte: PF > 1,3 em 2022-2025 com
//       comissao + Deslizamento (Slippage) 3-5 ticks. Senao, gap-and-go morre tambem.
//    2. O edge e' INSEPARAVEL do stop LARGO. Testado: capar o stop em 25-40pt
//       (~$250-400) mata o PF (cai pra ~1,0, holdout negativo). Risco mediano por
//       trade = 30-82pt ($300-825 em 5 MNQ). maxDD ~$6.500.
//    3. Por isso NAO cabe no DD trailing $1.000 da Apex 25K (sim de aprovacao: 31%).
//       Precisa firma de DD ESTATICO (Tradeify / MyFundedFutures / TPT): sim de
//       aprovacao ~42% ($2.500 estatico). Este bot NAO tem guarda de DD interna.
//
//  LOGICA:
//    - Na abertura do RTH (9h30 ET): gap = Open[0] - fechamento do RTH anterior.
//    - So opera se GapMinPontos <= |gap| <= GapMaxPontos.
//    - Forma o "opening range" (OR) = max/min dos 1os ORMinutos (15) minutos.
//    - Na barra que fecha o OR: se o gap SEGUROU (close dessa barra do lado certo
//      do fechamento anterior), entra A FAVOR do gap, a MERCADO.
//    - Stop = outro extremo do OR (SEM cap — e' a natureza da estrategia).
//    - Alvo = RR x risco (bracket fixo, sem trailing tick-a-tick).
//    - Flat as FlattenHora (13h00 ET). 1 trade/dia.
//
//  FUSO DO GRAFICO — CRITICO:
//    Os horarios abaixo (HHMM) sao lidos como ToTime(Time[0]). O arquivo importado
//    "MNQ 12-25" (dados_databento/MNQ_NT8_import_2022_2026.zip) esta em fuso
//    America/Chicago. Entao, com esse dado, RTH open = 08:30 CT, RTH close = 15:00
//    CT, flatten 12:00 CT.  ->  DEFAULTS ABAIXO JA ESTAO EM CHICAGO.
//    Se o grafico estiver em ET, mude p/ 930 / 1600 / 1300. Confira SEMPRE olhando
//    o Print do 1o gap no log e comparando com um calendario.
//
//  USO: Strategy Analyzer, MNQ 1 min, Calculate = OnBarClose, periodo 2022-01 ->
//       2025-12 (IS). Depois 2026 (holdout). Comissao NinjaTrader Brokerage,
//       Deslizamento 3-5 ticks. So escreve versao de producao se PF > 1,3 no IS.
// -----------------------------------------------------------------------------

namespace NinjaTrader.NinjaScript.Strategies
{
	public class NomadeBot_GapAndGo : Strategy
	{
		// ---------- Estado da sessao RTH ----------
		private string  diaRth        = "";
		private double  fechRthAnter   = double.NaN;   // fechamento do RTH de ontem
		private double  fechRthHoje    = double.NaN;   // ultimo close visto dentro do RTH de hoje
		private bool    dentroRth      = false;
		private bool    dentroRthAnt   = false;

		// ---------- Estado do setup do dia ----------
		private double  rthOpen        = double.NaN;
		private double  gapPontos      = 0;
		private double  orHigh         = double.NaN;
		private double  orLow          = double.NaN;
		private int     orBarras       = 0;
		private bool    setupAvaliado  = false;   // ja decidiu (entrou ou descartou) hoje
		private bool    tradeHoje      = false;
		private int     tradeSeq       = 0;

		protected override void OnStateChange()
		{
			if (State == State.SetDefaults)
			{
				Description					= @"Candidata C: gap-and-go. Gap que segura o opening range -> a favor, bracket fixo. TESTE no Strategy Analyzer (ver cabecalho).";
				Name						= "NomadeBot_GapAndGo";
				Calculate					= Calculate.OnBarClose;
				EntriesPerDirection			= 1;
				EntryHandling				= EntryHandling.AllEntries;
				IsExitOnSessionCloseStrategy	= false;
				IsFillLimitOnTouch			= false;
				MaximumBarsLookBack			= MaximumBarsLookBack.TwoHundredFiftySix;
				OrderFillResolution			= OrderFillResolution.Standard;
				Slippage					= 0;    // usar o "Deslizamento" do Analyzer, nao aqui
				StartBehavior				= StartBehavior.AdoptAccountPosition;
				TimeInForce					= TimeInForce.Gtc;
				TraceOrders					= false;
				RealtimeErrorHandling		= RealtimeErrorHandling.IgnoreAllErrors;
				StopTargetHandling			= StopTargetHandling.PerEntryExecution;
				BarsRequiredToTrade			= 30;
				IsInstantiatedOnEachOptimizationIteration = true;

				Contratos			= 5;

				// horarios em HHMM, no FUSO DO GRAFICO (default = Chicago, ver cabecalho)
				HorarioOpenRTH		= 830;
				HorarioCloseRTH		= 1500;
				FlattenHora			= 1200;

				ORMinutos			= 15;
				GapMinPontos		= 20.0;
				GapMaxPontos		= 150.0;
				RR					= 2.0;
			}
			else if (State == State.Configure) { }
			else if (State == State.DataLoaded) { }
		}

		protected override void OnBarUpdate()
		{
			if (CurrentBars[0] < BarsRequiredToTrade)
				return;

			int    agora = ToTime(Time[0]) / 100;             // HHMM no fuso do grafico
			string hoje  = Time[0].ToString("yyyy-MM-dd");

			dentroRthAnt = dentroRth;
			dentroRth    = agora >= HorarioOpenRTH && agora < HorarioCloseRTH;

			// mantem o ultimo close dentro do RTH de hoje (vira o "fechRthAnter" amanha)
			if (dentroRth)
				fechRthHoje = Close[0];

			// -------- Virada pra um novo dia de RTH --------
			// primeira barra que entra no RTH num dia diferente
			bool novaSessaoRth = dentroRth && !dentroRthAnt && hoje != diaRth;
			if (novaSessaoRth)
			{
				// o fechamento de RTH de ontem e o ultimo close que acumulamos
				fechRthAnter  = fechRthHoje;
				fechRthHoje   = Close[0];
				diaRth        = hoje;

				rthOpen       = Open[0];
				orHigh        = High[0];
				orLow         = Low[0];
				orBarras      = 1;
				setupAvaliado = false;
				tradeHoje     = false;

				gapPontos = double.IsNaN(fechRthAnter) ? 0 : (rthOpen - fechRthAnter);
				return;
			}

			// -------- Flatten forcado --------
			if (agora >= FlattenHora)
			{
				if (Position.MarketPosition == MarketPosition.Long)   ExitLong("Flatten_EOD");
				else if (Position.MarketPosition == MarketPosition.Short) ExitShort("Flatten_EOD");
				return;
			}

			if (hoje != diaRth || setupAvaliado || double.IsNaN(rthOpen))
				return;

			// -------- Acumula o opening range --------
			if (orBarras < ORMinutos)
			{
				orHigh = Math.Max(orHigh, High[0]);
				orLow  = Math.Min(orLow,  Low[0]);
				orBarras++;
				if (orBarras < ORMinutos)
					return;
			}

			// -------- Barra que fecha o OR: decide --------
			setupAvaliado = true;

			if (double.IsNaN(fechRthAnter) || double.IsNaN(gapPontos))
				return;

			double agap = Math.Abs(gapPontos);
			if (agap < GapMinPontos || agap > GapMaxPontos)
			{
				Print(string.Format("{0}  gap {1:F1}pt fora da banda [{2:F0},{3:F0}] — sem trade", Time[0], gapPontos, GapMinPontos, GapMaxPontos));
				return;
			}

			int lado = gapPontos > 0 ? 1 : -1;
			double px = Close[0];

			// gap "segurou"? close do OR do lado certo do fechamento anterior
			bool segurou = (lado == 1 && px > fechRthAnter) || (lado == -1 && px < fechRthAnter);
			if (!segurou)
			{
				Print(string.Format("{0}  gap {1:F1}pt NAO segurou (px {2:F2} vs prevClose {3:F2}) — sem trade", Time[0], gapPontos, px, fechRthAnter));
				return;
			}

			// risco = distancia ao outro extremo do OR (SEM cap — e' a natureza da estrategia)
			double risco = lado == 1 ? (px - orLow) : (orHigh - px);
			if (risco < 2.5)
				risco = 2.5;

			double stopPrice = px - lado * risco;
			double tgtPrice  = px + lado * RR * risco;

			string sinal = (lado == 1 ? "GG_Long_" : "GG_Short_") + (++tradeSeq);
			SetStopLoss(sinal, CalculationMode.Price, stopPrice, false);
			SetProfitTarget(sinal, CalculationMode.Price, tgtPrice);

			if (lado == 1) EnterLong(Contratos, sinal);
			else           EnterShort(Contratos, sinal);

			tradeHoje = true;
			Print(string.Format("{0}  {1} gap {2:F1}pt @ {3:F2} | OR [{4:F2}, {5:F2}] risco {6:F1}pt | SL {7:F2} TP {8:F2}",
				Time[0], (lado == 1 ? "LONG" : "SHORT"), gapPontos, px, orLow, orHigh, risco, stopPrice, tgtPrice));
		}

		#region Propriedades
		[NinjaScriptProperty]
		[Range(1, int.MaxValue)]
		[Display(Name = "Contratos", GroupName = "1. Geral", Order = 0)]
		public int Contratos { get; set; }

		[NinjaScriptProperty]
		[Range(0, 2359)]
		[Display(Name = "Abertura RTH (HHMM, fuso do grafico)", GroupName = "2. Horarios", Order = 0)]
		public int HorarioOpenRTH { get; set; }

		[NinjaScriptProperty]
		[Range(0, 2359)]
		[Display(Name = "Fechamento RTH (HHMM)", GroupName = "2. Horarios", Order = 1)]
		public int HorarioCloseRTH { get; set; }

		[NinjaScriptProperty]
		[Range(0, 2359)]
		[Display(Name = "Flatten (HHMM)", GroupName = "2. Horarios", Order = 2)]
		public int FlattenHora { get; set; }

		[NinjaScriptProperty]
		[Range(2, 120)]
		[Display(Name = "Minutos do opening range", GroupName = "3. Setup", Order = 0)]
		public int ORMinutos { get; set; }

		[NinjaScriptProperty]
		[Range(0.0, double.MaxValue)]
		[Display(Name = "Gap minimo (pontos)", GroupName = "3. Setup", Order = 1)]
		public double GapMinPontos { get; set; }

		[NinjaScriptProperty]
		[Range(0.0, double.MaxValue)]
		[Display(Name = "Gap maximo (pontos)", GroupName = "3. Setup", Order = 2)]
		public double GapMaxPontos { get; set; }

		[NinjaScriptProperty]
		[Range(0.5, 10.0)]
		[Display(Name = "RR (alvo / risco)", GroupName = "3. Setup", Order = 3)]
		public double RR { get; set; }
		#endregion
	}
}
