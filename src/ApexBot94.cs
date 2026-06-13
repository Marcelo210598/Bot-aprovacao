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
//  ApexBot94  —  Bot de APROVACAO de conta Apex (config "94 em 15 dias")
// -----------------------------------------------------------------------------
//  Estrategia: reversao na maxima/minima do dia anterior ("Niveis 94").
//  Config validada em 1 ano de dados reais (MNQ 5 contratos):
//    94% de aprovacao | mediana 15 dias | PF 1.53 | risco $125/trade.
//
//  Esta e a Strategy de PRODUCAO (opera ao vivo). O backtest comparativo
//  fica em ApexApprovalSim.cs. A logica de entrada/saida aqui e identica a
//  do script validado backtest/run_mnq_5contr.py.
//
//  COMO USAR NO NT8:
//    1) Copie p/ Documents\NinjaTrader 8\bin\Custom\Strategies\
//    2) Editor NinjaScript > F5 (compilar)
//    3) Rode num grafico MNQ de 1 minuto, sessao US (horario do PC em ET
//       OU use o trading hours "CME US Index Futures RTH").
//    4) FORWARD TEST PRIMEIRO: Sim101 / Market Replay antes de ir pra conta real.
//
//  PARAMETROS PADRAO = config vencedora (5 MNQ):
//    TP 60pt | SL 12,5pt | BE +3,75 trava +2,5 | trail 1,75 | stop diario $750
//
//  IMPORTANTE:
//    - Calculate = OnBarClose: decisoes no FECHAMENTO de cada barra de 1min
//      (igual ao backtest). Os stops/alvos ficam como ordens no servidor e
//      disparam ao toque intrabar.
//    - O ponto do MNQ vale $2; 5 contratos = $10/ponto. Ajuste Contratos se
//      for usar NQ (cheio) em vez de MNQ.
// =============================================================================

namespace NinjaTrader.NinjaScript.Strategies
{
	public class ApexBot94 : Strategy
	{
		// ---------- Niveis do dia anterior (gatilho de entrada) ----------
		private double pdHigh = 0, pdLow = 0;     // high/low do dia ANTERIOR
		private double curHigh = 0, curLow = 0;   // acumula high/low do dia atual
		private string diaNiveis = "";
		private int    barInicioDia = 0;          // barra em que o dia atual comecou (p/ desenhar as linhas)

		// ---------- Gestao da posicao aberta ----------
		private double entryPrice = 0;   // preco de entrada (Position.AveragePrice)
		private double stopPrice  = 0;   // preco atual do stop (sobe com trailing)
		private double favPrice   = 0;   // melhor preco a favor desde a entrada
		private bool   beFeito    = false; // breakeven ja acionado
		private bool   gerenciando = false; // ja inicializei stop/alvo desta posicao
		private string sinalAtivo = "";   // nome do sinal da entrada vigente

		// ---------- Kill switch / controle diario ----------
		private string diaCorrente = "";
		private double pnlInicioDia = 0;  // realizado acumulado no inicio do dia
		private bool   bloqueadoHoje = false;

		// ---------- Controle de meta (opcional: para ao aprovar) ----------
		private HashSet<string> diasOperados = new HashSet<string>();
		private bool aprovado = false;    // bateu meta + min dias -> para de operar

		protected override void OnStateChange()
		{
			if (State == State.SetDefaults)
			{
				Description					= @"Bot de aprovacao Apex (Niveis 94): reversao na max/min do dia anterior. Config 5 MNQ: 94% / mediana 15 dias.";
				Name						= "ApexBot94";
				Calculate					= Calculate.OnBarClose;
				EntriesPerDirection			= 1;
				EntryHandling				= EntryHandling.AllEntries;
				IsExitOnSessionCloseStrategy = true;
				ExitOnSessionCloseSeconds	= 30;
				IsFillLimitOnTouch			= false;
				MaximumBarsLookBack			= MaximumBarsLookBack.TwoHundredFiftySix;
				OrderFillResolution			= OrderFillResolution.Standard;
				Slippage					= 0;
				StartBehavior				= StartBehavior.WaitUntilFlat;
				TimeInForce					= TimeInForce.Gtc;
				TraceOrders					= false;
				RealtimeErrorHandling		= RealtimeErrorHandling.StopCancelClose;
				StopTargetHandling			= StopTargetHandling.PerEntryExecution;
				BarsRequiredToTrade			= 20;
				IsInstantiatedOnEachOptimizationIteration = true;

				// ----- Config vencedora (5 MNQ) -----
				Contratos			= 5;

				// Pontos (config "94 em 15 dias")
				AlvoPontos			= 60.0;   // TP — deixar o ganho correr e o segredo da velocidade
				StopPontos			= 12.5;   // SL — risco $125/trade com 5 MNQ
				BreakevenTrigPontos	= 3.75;   // ao ganhar +3,75pt...
				BreakevenLockPontos	= 2.5;    // ...trava o stop em +2,5pt
				TrailingPontos		= 1.75;   // trailing curto a partir do breakeven
				TolToqueTicks		= 20;     // tolerancia de toque na zona (20 ticks = 5pt) — otimizado 13/06: 95%, 19 aprov/ano, +21% PnL vs 6 ticks

				// Risco diario
				StopDiarioDolar		= 750.0;  // kill switch: para o dia ao perder $750
				MaxTradesDia		= 0;       // 0 = sem limite (config principal); use 12 p/ variante amarrada

				// Horarios (HHmm em ET — rode o grafico/PC em US Eastern)
				SessaoInicio		= 930;
				EntradaFim			= 1500;
				FlattenHora			= 1555;

				// Meta de aprovacao (para de operar quando atingida)
				PararAoAprovar		= true;
				MetaLucroDolar		= 1500.0;
				MinDiasOperados		= 7;

				// Visual
				DesenharNiveis		= true;
			}
			else if (State == State.Configure)
			{
				// nada a configurar aqui — stop/alvo sao definidos por posicao
			}
		}

		protected override void OnBarUpdate()
		{
			if (CurrentBars[0] < BarsRequiredToTrade)
				return;

			int agora = ToTime(Time[0]) / 100;            // HHmm
			string hoje = Time[0].ToString("yyyy-MM-dd");

			// ---------------- Virada de dia ----------------
			if (hoje != diaCorrente)
			{
				diaCorrente   = hoje;
				bloqueadoHoje = false;
				pnlInicioDia  = RealizadoAcumulado();
			}

			// ---------------- Niveis do dia anterior ----------------
			bool emSessao = agora >= SessaoInicio && agora < 1600;
			if (hoje != diaNiveis)
			{
				if (curHigh > 0) { pdHigh = curHigh; pdLow = curLow; }
				diaNiveis = hoje;
				curHigh = emSessao ? High[0] : 0;
				curLow  = emSessao ? Low[0]  : 0;
				barInicioDia = CurrentBar;
			}
			else if (emSessao)
			{
				curHigh = curHigh == 0 ? High[0] : Math.Max(curHigh, High[0]);
				curLow  = curLow  == 0 ? Low[0]  : Math.Min(curLow,  Low[0]);
			}

			// ---------------- Desenha as linhas dos niveis no grafico ----------------
			DesenhaNiveis(hoje);

			// ---------------- Gestao da posicao aberta ----------------
			if (Position.MarketPosition != MarketPosition.Flat)
			{
				diasOperados.Add(hoje);
				GerenciaPosicao();
			}
			else if (gerenciando)
			{
				// saiu da posicao (stop/alvo bateu) -> reseta estado de gestao
				gerenciando = false;
				sinalAtivo  = "";
			}

			// ---------------- Kill switch diario ----------------
			double pnlDia = RealizadoAcumulado() - pnlInicioDia + UnrealizadoPiorCaso();
			if (StopDiarioDolar > 0 && pnlDia <= -StopDiarioDolar)
			{
				bloqueadoHoje = true;
				if (Position.MarketPosition != MarketPosition.Flat)
					FechaPosicao("StopDiario");
			}

			// ---------------- Meta de aprovacao (para de operar) ----------------
			if (PararAoAprovar && !aprovado)
			{
				if (RealizadoAcumulado() >= MetaLucroDolar && diasOperados.Count >= MinDiasOperados)
				{
					aprovado = true;
					if (Position.MarketPosition != MarketPosition.Flat)
						FechaPosicao("MetaAtingida");
					Print(string.Format("[ApexBot94] META ATINGIDA em {0} | realizado ${1:N2} | {2} dias operados — PARANDO de operar.",
						hoje, RealizadoAcumulado(), diasOperados.Count));
				}
			}

			// ---------------- Flatten no fim do dia ----------------
			if (agora >= FlattenHora)
			{
				if (Position.MarketPosition != MarketPosition.Flat)
					FechaPosicao("FlattenEOD");
				return;
			}

			// ---------------- Entrada ----------------
			if (aprovado || bloqueadoHoje) return;
			if (Position.MarketPosition != MarketPosition.Flat) return;
			if (MaxTradesDia > 0 && TradesHoje() >= MaxTradesDia) return;

			EntradaNiveis(agora);
		}

		// ---------------- Logica de entrada (Niveis: max/min dia anterior) ----------------
		private void EntradaNiveis(int agora)
		{
			if (agora < SessaoInicio || agora >= EntradaFim) return;
			if (pdHigh <= 0 || pdLow <= 0) return;

			double tol = TolToqueTicks * TickSize;
			double h = High[0], l = Low[0], c = Close[0];

			// ----- tocou a zona da MAXIMA do dia anterior? (setup de SHORT) -----
			if (h >= pdHigh - tol)
			{
				if (c < pdHigh)
				{
					sinalAtivo = "NIV_S";
					EnterShort(Contratos, sinalAtivo);
					Print(string.Format("{0}  >>> SHORT @ {1:F2}  | tocou Max {2:F2} (H={3:F2}) e FECHOU ABAIXO (C={4:F2})",
						Time[0], c, pdHigh, h, c));
				}
				else
				{
					Print(string.Format("{0}  toque no Max {1:F2} SEM rejeicao (H={2:F2}, C={3:F2} >= linha) -> nao entrou",
						Time[0], pdHigh, h, c));
				}
				return;
			}

			// ----- tocou a zona da MINIMA do dia anterior? (setup de LONG) -----
			if (l <= pdLow + tol)
			{
				if (c > pdLow)
				{
					sinalAtivo = "NIV_L";
					EnterLong(Contratos, sinalAtivo);
					Print(string.Format("{0}  >>> LONG @ {1:F2}  | tocou Min {2:F2} (L={3:F2}) e FECHOU ACIMA (C={4:F2})",
						Time[0], c, pdLow, l, c));
				}
				else
				{
					Print(string.Format("{0}  toque no Min {1:F2} SEM reacao (L={2:F2}, C={3:F2} <= linha) -> nao entrou",
						Time[0], pdLow, l, c));
				}
			}
		}

		// ---------------- Gestao de stop/alvo/breakeven/trailing ----------------
		private void GerenciaPosicao()
		{
			bool isLong = Position.MarketPosition == MarketPosition.Long;

			// 1a barra na posicao: define entrada, stop inicial e alvo
			if (!gerenciando)
			{
				entryPrice = Position.AveragePrice;
				favPrice   = entryPrice;
				beFeito    = false;
				stopPrice  = isLong ? entryPrice - StopPontos : entryPrice + StopPontos;
				gerenciando = true;

				SetProfitTarget(sinalAtivo, CalculationMode.Price,
					isLong ? entryPrice + AlvoPontos : entryPrice - AlvoPontos);
				SetStopLoss(sinalAtivo, CalculationMode.Price, stopPrice, false);
				return;
			}

			// barras seguintes: atualiza favoravel + breakeven + trailing
			if (isLong)
			{
				favPrice = Math.Max(favPrice, High[0]);
				if (!beFeito && (favPrice - entryPrice) >= BreakevenTrigPontos)
				{
					stopPrice = Math.Max(stopPrice, entryPrice + BreakevenLockPontos);
					beFeito = true;
				}
				if (beFeito)
					stopPrice = Math.Max(stopPrice, favPrice - TrailingPontos);
			}
			else
			{
				favPrice = Math.Min(favPrice, Low[0]);
				if (!beFeito && (entryPrice - favPrice) >= BreakevenTrigPontos)
				{
					stopPrice = Math.Min(stopPrice, entryPrice - BreakevenLockPontos);
					beFeito = true;
				}
				if (beFeito)
					stopPrice = Math.Min(stopPrice, favPrice + TrailingPontos);
			}

			// reposiciona a ordem de stop no novo preco
			SetStopLoss(sinalAtivo, CalculationMode.Price, stopPrice, false);
		}

		// ---------------- Desenho das linhas de max/min do dia anterior ----------------
		private void DesenhaNiveis(string hoje)
		{
			if (!DesenharNiveis) return;

			// texto de status no canto (confirma que os niveis estao sendo calculados)
			Draw.TextFixed(this, "statusNiveis",
				"Niveis dia anterior:\n" +
				"  Max (short): " + (pdHigh > 0 ? pdHigh.ToString("F2") : "(aguardando 1o dia)") + "\n" +
				"  Min (long):  " + (pdLow  > 0 ? pdLow.ToString("F2")  : "(aguardando 1o dia)"),
				TextPosition.TopRight);

			if (pdHigh <= 0 || pdLow <= 0) return;

			// linhas horizontais (atravessam o grafico inteiro — sempre visiveis)
			Draw.HorizontalLine(this, "PDH", pdHigh, Brushes.Red,       DashStyleHelper.Dash, 2);
			Draw.HorizontalLine(this, "PDL", pdLow,  Brushes.LimeGreen, DashStyleHelper.Dash, 2);
		}

		private void FechaPosicao(string motivo)
		{
			if (Position.MarketPosition == MarketPosition.Long)  ExitLong("X_" + motivo, sinalAtivo);
			else if (Position.MarketPosition == MarketPosition.Short) ExitShort("X_" + motivo, sinalAtivo);
		}

		// ---------------- Helpers de PnL ----------------
		private double RealizadoAcumulado()
		{
			return SystemPerformance != null
				? SystemPerformance.AllTrades.TradesPerformance.Currency.CumProfit
				: 0;
		}

		// Pior caso intraday da barra (nao subestima a perda do kill switch)
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
			string hoje = Time[0].ToString("yyyy-MM-dd");
			var trades = SystemPerformance.AllTrades;
			for (int i = trades.Count - 1; i >= 0; i--)
			{
				if (trades[i].Exit.Time.ToString("yyyy-MM-dd") == hoje) n++;
				else break;
			}
			// soma a posicao aberta de hoje, se houver
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
		#endregion
	}
}
