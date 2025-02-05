export interface AnalysisResponse {
  // analysis: {
    total_income: number;
    essential_spending: number;
    discretionary_spending: number;
    savings_rate: number;
    debt_payments: number;
    spending_patterns: {
      sum: {
        debt: number;
        discretionary: number;
        essential: number;
        income: number;
        savings: number;
      };
      count: {
        debt: number;
        discretionary: number;
        essential: number;
        income: number;
        savings: number;
      };
    };
    transaction_frequency: number;
    average_balance: number;
  // };
  // assessment: string;
}