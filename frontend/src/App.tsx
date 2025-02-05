import React, { useState } from 'react';
import { DragDropZone } from './components/DragDropZone';
import { AnalysisChart } from './components/AnalysisChart';
import { MetricCard } from './components/MetricCard';
import { CreditScorePieChart } from './components/CreditScorePieChart';
import { AnalysisResponse } from './types';
import { DollarSign, CreditCard, Wallet, PiggyBank, TrendingUp, ChevronDown, ChevronUp } from 'lucide-react';
import { Alert, AlertTitle, AlertDescription } from "./components/alert";

function App() {
  const [isLoading, setIsLoading] = useState(false);
  const [analysisData, setAnalysisData] = useState<AnalysisResponse | null>(null);
  const [isAssessmentOpen, setIsAssessmentOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleFileUpload = async (file: File) => {
    setIsLoading(true);
    setError(null);
    try {
      const formData = new FormData();
      formData.append('file', file);
    
      const response = await fetch('http://localhost:8000/analyze-statement', {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        throw new Error(`Analysis failed: ${response.statusText}`);
      }
      let res = (await response.text()) as string; // L M F A O 
      let data = JSON.parse(res); 
      console.log(data)
      setAnalysisData(data);
    } catch (error) {
      console.error('Error uploading file:', error);
      setError(error instanceof Error ? error.message : 'Failed to analyze statement');
      setAnalysisData(null);
    } finally {
      setIsLoading(false);
    }
  };

  const formatCurrency = (value: number) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      maximumFractionDigits: 0,
    }).format(value);
  };

  const getChartData = () => {
    if (!analysisData) return [];
    const { sum } = analysisData.spending_patterns;
    
    return Object.entries(sum)
      .filter(([key]) => key !== 'nan')
      .map(([name, value]) => ({
        name: name.charAt(0).toUpperCase() + name.slice(1),
        value: value || 0
      }));
  };

  const getCreditScoreData = () => {
    if (!analysisData) return { score: 0, data: [] };
    const { sum } = analysisData.spending_patterns;
    const income = sum.income || 0;
    const savings = sum.savings || 0;
    const debt = sum.debt || 0;
    const essential = sum.essential || 0;
    const discretionary = sum.discretionary || 0;

    const savingsRatio = income > 0 ? (savings / income) * 100 : 0;
    const debtRatio = income > 0 ? (debt / income) * 100 : 100;
    const essentialRatio = income > 0 ? (essential / income) * 100 : 100;
    const discretionaryRatio = income > 0 ? (discretionary / income) * 100 : 100;

    const data = [
      {
        name: 'Income Stability',
        value: income > 0 ? 25 : 10,
        color: income > 0 ? '#4CAF50' : '#F44336'
      },
      {
        name: 'Essential/Discretionary',
        value: 20,
        color: discretionaryRatio < essentialRatio ? '#4CAF50' : '#FF9800'
      },
      {
        name: 'Savings Rate',
        value: savingsRatio > 20 ? 25 : 15,
        color: savingsRatio > 20 ? '#4CAF50' : '#2196F3'
      },
      {
        name: 'Debt Management',
        value: debtRatio < 30 ? 20 : 10,
        color: debtRatio < 30 ? '#4CAF50' : '#F44336'
      },
      {
        name: 'Transaction Pattern',
        value: analysisData.transaction_frequency > 50 ? 20 : 15,
        color: analysisData.transaction_frequency > 50 ? '#4CAF50' : '#2196F3'
      }
    ];

    const totalScore = Math.round((data.reduce((sum, item) => sum + item.value, 0) / 100) * 10);

    return { score: totalScore, data };
  };

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="max-w-7xl mx-auto px-4 py-12">
        <h1 className="text-3xl font-bold text-gray-900 mb-8 text-center bank-title">inCredulous</h1>
        
        {error && (
          <Alert variant="destructive" className="mb-6">
            <AlertTitle>Error</AlertTitle>
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}

        {!analysisData ? (
          <div className="max-w-xl mx-auto">
            <DragDropZone onFileUpload={handleFileUpload} />
          </div>
        ) : (
          <div className="space-y-8">
            <div className="bg-white rounded-xl shadow-sm p-6">
              <CreditScorePieChart {...getCreditScoreData()} />
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
              <MetricCard
                title="Total Income"
                value={formatCurrency(analysisData.total_income)}
                icon={<DollarSign className="w-6 h-6 text-blue-500" />}
              />
              <MetricCard
                title="Essential Spending"
                value={formatCurrency(analysisData.essential_spending)}
                icon={<CreditCard className="w-6 h-6 text-blue-500" />}
              />
              <MetricCard
                title="Discretionary Spending"
                value={formatCurrency(analysisData.discretionary_spending)}
                icon={<Wallet className="w-6 h-6 text-blue-500" />}
              />
              <MetricCard
                title="Savings Rate"
                value={formatCurrency(analysisData.savings_rate)}
                icon={<PiggyBank className="w-6 h-6 text-blue-500" />}
              />
            </div>

            <div className="bg-white rounded-xl shadow-sm p-6">
              <h2 className="text-xl font-semibold mb-4">Spending Overview</h2>
              <AnalysisChart data={getChartData()} />
            </div>

            {/* <div className="bg-white rounded-xl shadow-sm">
              <button
                onClick={() => setIsAssessmentOpen(!isAssessmentOpen)}
                className="w-full p-6 flex items-center justify-between text-left"
              >
                <div className="flex items-center gap-3">
                  <TrendingUp className="w-6 h-6 text-blue-500" />
                  <h2 className="text-xl font-semibold">Financial Assessment</h2>
                </div>
                {isAssessmentOpen ? (
                  <ChevronUp className="w-5 h-5 text-gray-500" />
                ) : (
                  <ChevronDown className="w-5 h-5 text-gray-500" />
                )}
              </button>
              {isAssessmentOpen && (
                <div className="px-6 pb-6">
                  <p className="text-gray-600 whitespace-pre-line">Lorem</p>
                </div>
              )}
            </div> */}
          </div>
        )}

        {isLoading && (
          <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center">
            <div className="bg-white p-6 rounded-lg">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500 mx-auto"></div>
              <p className="text-center mt-4">Analyzing PDF...</p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default App;