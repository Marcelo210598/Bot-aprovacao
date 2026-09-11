#region Using declarations
using System;
using System.ComponentModel;
using System.ComponentModel.DataAnnotations;
using NinjaTrader.Cbi;
using NinjaTrader.Gui.Tools;
using NinjaTrader.Data;
using NinjaTrader.NinjaScript;
#endregion

// ============================================================================
// ABERTURA NY BREAKOUT
// ----------------------------------------------------------------------------
// Estratégia criada do zero (não é cópia de nenhum produto de terceiros).
//
// LÓGICA:
// 1. No horário configurado (padrão 09:30 NY = 10:30 Brasília), o robô guarda
//    o preço de ABERTURA do primeiro candle de 1 minuto como referência.
// 2. Durante a janela de monitoramento (padrão: só esse 1º minuto, mas
//    configurável), ele acompanha tick a tick se o preço andou X dólares
//    (padrão $20) para cima ou para baixo em relação a essa referência.
// 3. Assim que o movimento de X dólares acontece, entra a MERCADO na direção
//    do movimento (compra se subiu, venda se caiu).
// 4. Define Stop Loss e Take Profit em dólares (padrão $100 / $250).
// 5. Quando o trade andar Y dólares a favor (padrão $20), move o stop para
//    o preço de entrada (zero a zero) — breakeven.
// 6. Por padrão, só permite 1 operação por dia (configurável).
// 7. Fecha qualquer posição em aberto no fim da sessão, por segurança
//    (configurável).
//
// OBSERVAÇÕES IMPORTANTES:
// - Os valores em dólares são convertidos para pontos de preço usando
//   Instrument.MasterInstrument.PointValue, então o robô se adapta
//   automaticamente ao contrato carregado no gráfico (NQ, MNQ, ES, MES...).
//   Os cálculos assumem 1 contrato; se "Quantidade" > 1, o risco/alvo total
//   em dólares multiplica pela quantidade.
// - O robô cria uma série interna de 1 minuto, então funciona mesmo se você
//   aplicar em um gráfico de outro tipo/período.
// - Em backtest (Strategy Analyzer) o disparo tick a tick só é 100% fiel se
//   você tiver dados de tick para o período testado. Em tempo real (Sim101
//   ou conta real) funciona tick a tick normalmente.
// ============================================================================

namespace NinjaTrader.NinjaScript.Strategies
{
    public class AberturaNYAprovacao : Strategy
    {
        // ---- Estado interno ----
        private double referenciaAbertura = 0;
        private bool monitorando = false;
        private bool operacaoRealizadaHoje = false;
        private bool breakevenAplicado = false;
        private bool travaLucroAplicada = false;
        private double precoEntrada = 0;
        private DateTime diaAtual = DateTime.MinValue;
        private DateTime horaInicioJanela = DateTime.MinValue;
        private DateTime horaFimJanela = DateTime.MinValue;
        private DateTime momentoInicioRealtime = DateTime.MinValue;

        protected override void OnStateChange()
        {
            if (State == State.SetDefaults)
            {
                Description = "Breakout de abertura NY (10:30 Brasília) com stop/gain/breakeven em dólares, totalmente configurável.";
                Name = "AberturaNYAprovação";
                Calculate = Calculate.OnEachTick;
                EntriesPerDirection = 1;
                EntryHandling = EntryHandling.AllEntries;
                IsExitOnSessionCloseStrategy = true;
                ExitOnSessionCloseSeconds = 30;
                IsFillLimitOnTouch = false;
                MaximumBarsLookBack = MaximumBarsLookBack.TwoHundredFiftySix;
                OrderFillResolution = OrderFillResolution.Standard;
                Slippage = 0;
                StartBehavior = StartBehavior.WaitUntilFlat;
                TimeInForce = TimeInForce.Gtc;
                TraceOrders = false;
                RealtimeErrorHandling = RealtimeErrorHandling.IgnoreAllErrors;
                StopTargetHandling = StopTargetHandling.PerEntryExecution;
                BarsRequiredToTrade = 1;
                IsInstantiatedOnEachOptimizationIteration = true;

                // ---- Parâmetros padrão ----
                HoraInicio = 9;
                MinutoInicio = 30;
                JanelaMonitoramentoMinutos = 1;
                GatilhoEntradaTicks = 10;
                StopLossDolares = 400;
                TakeProfitDolares = 1550;
                BreakevenGatilhoDolares = 20;
                TravaLucroGatilhoDolares = 500;
                BreakevenOffsetTicks = 0;
                Quantidade = 4;
                SomenteUmaOperacaoPorDia = true;
                TempoAquecimentoSegundos = 65;
                ModoDebug = false;
            }
            else if (State == State.Configure)
            {
                // Série interna de 1 minuto (independente do período do gráfico)
                AddDataSeries(BarsPeriodType.Minute, 1);
            }
            else if (State == State.Realtime)
            {
                // Marca o momento real (relógio da máquina) em que a estratégia
                // realmente começou a rodar ao vivo. Usado para o "aquecimento".
                momentoInicioRealtime = DateTime.Now;
            }
        }

        protected override void OnBarUpdate()
        {
            // Só processa a série interna de 1 minuto (índice 1)
            if (BarsInProgress != 1)
                return;

            // Ignora completamente o processamento de dados históricos.
            // Sem isso, o robô pode "entrar" num candle antigo durante o carregamento
            // do histórico, e essa posição vira uma ordem real assim que a estratégia
            // liga de verdade (é isso que causou a entrada automática ao aplicar).
            if (State != State.Realtime)
                return;

            // Segurança: só evita reagir a movimento que já tinha acontecido ANTES
            // de você ligar a estratégia (a vela em formação pode já ter andado).
            // Só libera operar depois de X segundos rodando de verdade ao vivo.
            if (momentoInicioRealtime == DateTime.MinValue)
                momentoInicioRealtime = DateTime.Now;

            if ((DateTime.Now - momentoInicioRealtime).TotalSeconds < TempoAquecimentoSegundos)
            {
                return;
            }

            if (CurrentBars[1] < 1)
                return;

            double pointValue = Instrument.MasterInstrument.PointValue;
            double tickSize = Instrument.MasterInstrument.TickSize;

            // O NinjaTrader rotula toda vela de tempo pelo horário de FECHAMENTO
            // (ex: uma vela que abre às 9h39 e fecha às 9h40 é rotulada "9h40").
            // Corrigimos aqui para trabalhar com o horário real de ABERTURA da vela,
            // que é o que o usuário configura nos parâmetros.
            DateTime agora = Times[1][0].AddMinutes(-1);

            // --- Detecta novo dia e reseta o estado ---
            if (agora.Date != diaAtual)
            {
                diaAtual = agora.Date;
                operacaoRealizadaHoje = false;
                monitorando = false;
                breakevenAplicado = false;
                travaLucroAplicada = false;
                referenciaAbertura = 0;

                horaInicioJanela = agora.Date + new TimeSpan(HoraInicio, MinutoInicio, 0);
                horaFimJanela = horaInicioJanela.AddMinutes(JanelaMonitoramentoMinutos);

                if (ModoDebug)
                    Print(string.Format("{0} | [" + Name + "] Novo dia. Janela de entrada: {1} até {2}", agora, horaInicioJanela, horaFimJanela));
            }

            // --- Gerencia posição aberta (breakeven) ---
            if (Position.MarketPosition != MarketPosition.Flat)
            {
                GerenciarBreakeven(pointValue, tickSize);
                return; // enquanto estiver posicionado, não avalia nova entrada
            }

            // --- Se já operou hoje e a regra é 1 operação/dia, não faz nada mais ---
            if (SomenteUmaOperacaoPorDia && operacaoRealizadaHoje)
                return;

            // --- Fora da janela de horário, não monitora ---
            if (agora < horaInicioJanela)
            {
                monitorando = false;
                return;
            }

            if (agora >= horaFimJanela)
            {
                if (monitorando && ModoDebug)
                    Print(string.Format("{0} | [" + Name + "] Janela de entrada encerrada sem gatilho de {1} ticks.", agora, GatilhoEntradaTicks));
                monitorando = false;
                return;
            }

            // --- Estamos dentro da janela: captura referência de abertura (uma vez) ---
            if (!monitorando)
            {
                referenciaAbertura = Opens[1][0];
                monitorando = true;

                if (ModoDebug)
                    Print(string.Format("{0} | [" + Name + "] Referência de abertura capturada: {1}", agora, referenciaAbertura));
            }

            if (referenciaAbertura <= 0)
                return;

            // --- Calcula o movimento em pontos equivalente ao gatilho em ticks ---
            double gatilhoPontos = GatilhoEntradaTicks * tickSize;

            // IMPORTANTE: usamos o PREÇO ATUAL (não a máxima/mínima acumulada da vela).
            // Isso garante que, se o preço subir e depois reverter, o robô não fique
            // "lembrando" de um pico antigo que já não reflete a força atual do movimento.
            double movimentoAtual = Closes[1][0] - referenciaAbertura;

            if (movimentoAtual >= gatilhoPontos)
            {
                EnterLong(1, Quantidade, "EntradaCompra");
                operacaoRealizadaHoje = true;
                monitorando = false;

                if (ModoDebug)
                    Print(string.Format("{0} | [" + Name + "] GATILHO DE COMPRA. Ref={1} Preço atual={2} Mov=${3:0.00}",
                        agora, referenciaAbertura, Closes[1][0], movimentoAtual * pointValue));
            }
            else if (-movimentoAtual >= gatilhoPontos)
            {
                EnterShort(1, Quantidade, "EntradaVenda");
                operacaoRealizadaHoje = true;
                monitorando = false;

                if (ModoDebug)
                    Print(string.Format("{0} | [" + Name + "] GATILHO DE VENDA. Ref={1} Preço atual={2} Mov=${3:0.00}",
                        agora, referenciaAbertura, Closes[1][0], -movimentoAtual * pointValue));
            }
        }

        private void GerenciarBreakeven(double pointValue, double tickSize)
        {
            if (precoEntrada <= 0)
                return;

            double precoAtual = Closes[1][0];
            double diffPontos = Position.MarketPosition == MarketPosition.Long
                ? precoAtual - precoEntrada
                : precoEntrada - precoAtual;

            double lucroAtualDolares = diffPontos * pointValue * Position.Quantity;

            // --- Nível 2: trava de lucro (mais alto, checado primeiro) ---
            // Ex: se o lucro atingir $500, move o stop para travar exatamente $500.
            if (!travaLucroAplicada && lucroAtualDolares >= TravaLucroGatilhoDolares)
            {
                double distanciaTravaPontos = TravaLucroGatilhoDolares / pointValue;
                double novoStop = Position.MarketPosition == MarketPosition.Long
                    ? precoEntrada + distanciaTravaPontos
                    : precoEntrada - distanciaTravaPontos;

                if (Position.MarketPosition == MarketPosition.Long)
                    ExitLongStopMarket(1, true, Position.Quantity, novoStop, "StopLoss", "EntradaCompra");
                else
                    ExitShortStopMarket(1, true, Position.Quantity, novoStop, "StopLoss", "EntradaVenda");

                travaLucroAplicada = true;
                breakevenAplicado = true; // esse nível já cobre/substitui o breakeven

                if (ModoDebug)
                    Print(string.Format("{0} | [" + Name + "] TRAVA DE LUCRO aplicada (${1}). Novo stop = {2}", Times[1][0].AddMinutes(-1), TravaLucroGatilhoDolares, novoStop));

                return;
            }

            // --- Nível 1: breakeven (zero a zero, ou com offset) ---
            if (breakevenAplicado || travaLucroAplicada)
                return;

            if (lucroAtualDolares >= BreakevenGatilhoDolares)
            {
                double offset = BreakevenOffsetTicks * tickSize;
                double novoStop = Position.MarketPosition == MarketPosition.Long
                    ? precoEntrada + offset
                    : precoEntrada - offset;

                if (Position.MarketPosition == MarketPosition.Long)
                    ExitLongStopMarket(1, true, Position.Quantity, novoStop, "StopLoss", "EntradaCompra");
                else
                    ExitShortStopMarket(1, true, Position.Quantity, novoStop, "StopLoss", "EntradaVenda");

                breakevenAplicado = true;

                if (ModoDebug)
                    Print(string.Format("{0} | [" + Name + "] BREAKEVEN aplicado. Novo stop = {1}", Times[1][0].AddMinutes(-1), novoStop));
            }
        }

        // ---------------------------------------------------------------------
        // REDE DE SEGURANÇA: como usamos RealtimeErrorHandling.IgnoreAllErrors
        // (pra não deixar a estratégia inteira desligar sozinha por causa de UMA
        // ordem de stop rejeitada em um movimento rápido de mercado), SOMOS
        // OBRIGADOS a tratar esse erro na mão aqui. Se o Stop Loss for rejeitado
        // OU não puder ser alterado (o mercado já passou do preço na hora que a
        // ordem chegou na corretora), fechamos a posição a MERCADO imediatamente,
        // pra nunca ficar com uma operação aberta e sem proteção nenhuma.
        // ---------------------------------------------------------------------
        protected override void OnOrderUpdate(Order order, double limitPrice, double stopPrice, int quantity,
            int filled, double averageFillPrice, OrderState orderState, DateTime time, ErrorCode error, string comment)
        {
            if (order.Name != "StopLoss")
                return;

            bool falhou = orderState == OrderState.Rejected || error == ErrorCode.UnableToChangeOrder;

            if (falhou && Position.MarketPosition != MarketPosition.Flat)
            {
                if (Position.MarketPosition == MarketPosition.Long)
                    ExitLong(1, Position.Quantity, "SaidaEmergencia", "EntradaCompra");
                else
                    ExitShort(1, Position.Quantity, "SaidaEmergencia", "EntradaVenda");

                if (ModoDebug)
                    Print(string.Format("{0} | [" + Name + "] ALERTA: Stop Loss falhou (estado={1}, erro={2}). Fechando posição a MERCADO por segurança.",
                        DateTime.Now, orderState, error));
            }
        }

        protected override void OnExecutionUpdate(Execution execution, string executionId, double price,
            int quantity, MarketPosition marketPosition, string orderId, DateTime time)
        {
            if (execution.Order == null)
                return;

            double pointValue = Instrument.MasterInstrument.PointValue;

            // --- Entrada preenchida: registra preço e lança stop/alvo iniciais ---
            if (execution.Order.Name == "EntradaCompra" && marketPosition == MarketPosition.Long)
            {
                precoEntrada = price;
                breakevenAplicado = false;
                travaLucroAplicada = false;

                double stopPrice = precoEntrada - (StopLossDolares / pointValue);
                double targetPrice = precoEntrada + (TakeProfitDolares / pointValue);

                ExitLongStopMarket(1, true, Quantidade, stopPrice, "StopLoss", "EntradaCompra");
                ExitLongLimit(1, true, Quantidade, targetPrice, "TakeProfit", "EntradaCompra");

                if (ModoDebug)
                    Print(string.Format("{0} | [" + Name + "] Compra preenchida @ {1} | Stop={2} Alvo={3}", time, precoEntrada, stopPrice, targetPrice));
            }
            else if (execution.Order.Name == "EntradaVenda" && marketPosition == MarketPosition.Short)
            {
                precoEntrada = price;
                breakevenAplicado = false;
                travaLucroAplicada = false;

                double stopPrice = precoEntrada + (StopLossDolares / pointValue);
                double targetPrice = precoEntrada - (TakeProfitDolares / pointValue);

                ExitShortStopMarket(1, true, Quantidade, stopPrice, "StopLoss", "EntradaVenda");
                ExitShortLimit(1, true, Quantidade, targetPrice, "TakeProfit", "EntradaVenda");

                if (ModoDebug)
                    Print(string.Format("{0} | [" + Name + "] Venda preenchida @ {1} | Stop={2} Alvo={3}", time, precoEntrada, stopPrice, targetPrice));
            }

            // --- Posição voltou a zero: reseta estado do trade ---
            if (Position.MarketPosition == MarketPosition.Flat)
            {
                if (ModoDebug && (execution.Order.Name == "StopLoss" || execution.Order.Name == "TakeProfit"))
                    Print(string.Format("{0} | [" + Name + "] Posição encerrada por {1} @ {2}", time, execution.Order.Name, price));

                precoEntrada = 0;
                breakevenAplicado = false;
                travaLucroAplicada = false;
            }
        }

        #region Propriedades (parâmetros configuráveis na aba Strategy do NinjaTrader)

        [NinjaScriptProperty]
        [Range(0, 23)]
        [Display(Name = "Hora de início (0-23)", Description = "Hora do horário do gráfico. Padrão 9 = 09:30 NY = 10:30 Brasília.", Order = 1, GroupName = "1 - Horário de Entrada")]
        public int HoraInicio { get; set; }

        [NinjaScriptProperty]
        [Range(0, 59)]
        [Display(Name = "Minuto de início (0-59)", Description = "Minuto do horário do gráfico.", Order = 2, GroupName = "1 - Horário de Entrada")]
        public int MinutoInicio { get; set; }

        [NinjaScriptProperty]
        [Range(1, 60)]
        [Display(Name = "Janela de monitoramento (min)", Description = "Quantos minutos após o início o robô ainda pode disparar a entrada.", Order = 3, GroupName = "1 - Horário de Entrada")]
        public int JanelaMonitoramentoMinutos { get; set; }

        [NinjaScriptProperty]
        [Range(1, int.MaxValue)]
        [Display(Name = "Gatilho de entrada (ticks)", Description = "Movimento em ticks (a partir da abertura) necessário para disparar a ordem. No NQ, 1 tick = $5 (4 ticks = $20).", Order = 1, GroupName = "2 - Entrada")]
        public int GatilhoEntradaTicks { get; set; }

        [NinjaScriptProperty]
        [Range(1, int.MaxValue)]
        [Display(Name = "Quantidade (contratos)", Order = 2, GroupName = "2 - Entrada")]
        public int Quantidade { get; set; }

        [NinjaScriptProperty]
        [Range(0, int.MaxValue)]
        [Display(Name = "Aquecimento antes de operar (segundos)", Description = "Tempo mínimo rodando ao vivo antes de permitir qualquer entrada. Evita reagir a movimento que já tinha acontecido antes de ativar o robô.", Order = 4, GroupName = "2 - Entrada")]
        public int TempoAquecimentoSegundos { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Somente 1 operação por dia", Order = 5, GroupName = "2 - Entrada")]
        public bool SomenteUmaOperacaoPorDia { get; set; }

        [NinjaScriptProperty]
        [Range(1, double.MaxValue)]
        [Display(Name = "Stop Loss ($)", Order = 1, GroupName = "3 - Gerenciamento de Risco")]
        public double StopLossDolares { get; set; }

        [NinjaScriptProperty]
        [Range(1, double.MaxValue)]
        [Display(Name = "Take Profit ($)", Order = 2, GroupName = "3 - Gerenciamento de Risco")]
        public double TakeProfitDolares { get; set; }

        [NinjaScriptProperty]
        [Range(1, double.MaxValue)]
        [Display(Name = "Gatilho de Breakeven ($)", Description = "Lucro em dólares para mover o stop para zero a zero.", Order = 3, GroupName = "3 - Gerenciamento de Risco")]
        public double BreakevenGatilhoDolares { get; set; }

        [NinjaScriptProperty]
        [Range(0, int.MaxValue)]
        [Display(Name = "Offset do Breakeven (ticks)", Description = "Ticks acima/abaixo do preço de entrada ao aplicar o breakeven (0 = exatamente no preço de entrada).", Order = 4, GroupName = "3 - Gerenciamento de Risco")]
        public int BreakevenOffsetTicks { get; set; }

        [NinjaScriptProperty]
        [Range(1, double.MaxValue)]
        [Display(Name = "Trava de Lucro ($)", Description = "Quando o lucro atingir esse valor, o stop é movido para travar exatamente esse lucro (nível de proteção acima do breakeven).", Order = 5, GroupName = "3 - Gerenciamento de Risco")]
        public double TravaLucroGatilhoDolares { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Modo Debug (prints no Output)", Order = 1, GroupName = "4 - Outros")]
        public bool ModoDebug { get; set; }

        #endregion
    }
}
