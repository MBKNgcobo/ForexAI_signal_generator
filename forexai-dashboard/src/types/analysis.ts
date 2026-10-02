export interface AgentAnalysis {
  direction: string;
  confidence: number;
  summary: string;
}

export interface RiskAssessment {
  risk_level: string;
  approved: boolean;
  agreement: number;
  reason: string;
  entry_price: number | null;
  stop_loss: number | null;
  take_profit: number | null;
  risk_reward: number | null;
}

export interface FinalDecision {
  direction: string;
  confidence: number;
  reasoning: string;
}

export interface AnalysisResult {
  symbol: string;
  timeframe: string;
  technicalAnalysis: AgentAnalysis;      // Fixed to camelCase
  fundamentalAnalysis: AgentAnalysis;    // Fixed to camelCase
  quantPrediction: AgentAnalysis;        // Fixed to camelCase
  riskAssessment: RiskAssessment;        // Fixed to camelCase
  finalDecision: FinalDecision;          // Fixed to camelCase
}

export interface SignalResult {
  signalId: string;
  direction: string;
  confidence: number;
  entryPrice: number;
  stopLoss: number;
  takeProfit: number;
  riskReward: number;
  timeframe: string;
  status: string;
  reasoning: string;
}

export interface AnalysisWithSignalResult {
  analysis: AnalysisResult;
  signal: SignalResult | null;
}
