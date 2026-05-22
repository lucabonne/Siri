import React, { useState, useEffect } from 'react';

export const LearningPanel: React.FC = () => {
  const [learningState, setLearningState] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchLearningState = async () => {
    // Simulated fetch - in a real app this would call /v1/learning/status
    setLoading(true);
    try {
      // Mock data for now since we don't have the explicit FastAPI endpoints yet
      setLearningState({
        feedback_count: 5,
        preferences: {
          "topic_coding": 1.2,
          "topic_workflow_1": 1.5,
        },
        tool_scores: {
          "shell_exec": 0.8,
          "file_write": 0.9,
        },
        memory_adjustments_count: 2,
        last_updated: new Date().toISOString()
      });
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchLearningState();
  }, []);

  const handleReset = () => {
    if (window.confirm("Are you sure you want to completely reset all explicit learning and feedback?")) {
      setLearningState({
        feedback_count: 0,
        preferences: {},
        tool_scores: {},
        memory_adjustments_count: 0,
        last_updated: new Date().toISOString()
      });
      alert("Learning state reset successfully.");
    }
  };

  const handleExport = () => {
    const dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify(learningState, null, 2));
    const downloadAnchorNode = document.createElement('a');
    downloadAnchorNode.setAttribute("href", dataStr);
    downloadAnchorNode.setAttribute("download", "siri_learning_state.json");
    document.body.appendChild(downloadAnchorNode);
    downloadAnchorNode.click();
    downloadAnchorNode.remove();
  };

  const handleImport = () => {
    const input = document.createElement('input');
    input.type = 'file';
    input.accept = '.json';
    input.onchange = e => {
      const file = (e.target as HTMLInputElement).files?.[0];
      if (!file) return;
      const reader = new FileReader();
      reader.onload = e => {
        try {
          const content = e.target?.result as string;
          // In a real app, this would post to /v1/learning/import
          alert("Import simulated successfully.");
          fetchLearningState();
        } catch (err) {
          alert("Failed to parse JSON file.");
        }
      };
      reader.readAsText(file);
    };
    input.click();
  };

  if (loading && !learningState) {
    return <div className="p-6 text-gray-500">Loading learning state...</div>;
  }

  if (error) {
    return <div className="p-6 text-red-500">Error: {error}</div>;
  }

  return (
    <div className="p-6 max-w-4xl mx-auto text-sm text-gray-800 dark:text-gray-200">
      <h2 className="text-2xl font-semibold mb-6">Learning Layer</h2>
      <p className="mb-4 text-gray-600 dark:text-gray-400">
        This panel shows the current state of Siri's explicit learning. Siri only learns from your explicit thumbs up/down feedback and does not adapt autonomously.
      </p>
      
      {learningState && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-8">
          <div className="bg-white dark:bg-gray-800 p-4 rounded-xl border border-gray-200 dark:border-gray-700 shadow-sm">
            <h3 className="font-semibold mb-2">Summary</h3>
            <ul className="space-y-2 text-gray-600 dark:text-gray-300">
              <li><strong>Total Feedback Events:</strong> {learningState.feedback_count}</li>
              <li><strong>Active Preferences:</strong> {Object.keys(learningState.preferences || {}).length}</li>
              <li><strong>Tracked Tools:</strong> {Object.keys(learningState.tool_scores || {}).length}</li>
              <li><strong>Memory Adjustments:</strong> {learningState.memory_adjustments_count}</li>
              <li><strong>Last Updated:</strong> {new Date(learningState.last_updated).toLocaleString()}</li>
            </ul>
          </div>
          
          <div className="bg-white dark:bg-gray-800 p-4 rounded-xl border border-gray-200 dark:border-gray-700 shadow-sm overflow-auto max-h-64">
            <h3 className="font-semibold mb-2">Preference Weights</h3>
            {Object.keys(learningState.preferences || {}).length === 0 ? (
              <p className="text-gray-500">No preference weights learned yet.</p>
            ) : (
              <ul className="space-y-1 text-gray-600 dark:text-gray-300">
                {Object.entries(learningState.preferences).map(([key, weight]) => (
                  <li key={key} className="flex justify-between">
                    <span>{key}</span>
                    <span className="font-mono bg-gray-100 dark:bg-gray-900 px-2 rounded">
                      {Number(weight).toFixed(2)}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      )}

      <div className="bg-white dark:bg-gray-800 p-4 rounded-xl border border-gray-200 dark:border-gray-700 shadow-sm mb-6">
        <h3 className="font-semibold mb-2 text-red-600 dark:text-red-400">Controls</h3>
        <p className="text-gray-600 dark:text-gray-400 mb-4 text-xs">
          Manage your learning data locally. Data is never synced to the cloud.
        </p>
        <div className="flex gap-4">
          <button 
            onClick={handleExport}
            className="px-4 py-2 bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-200 rounded-lg font-medium hover:bg-blue-200 dark:hover:bg-blue-800 transition-colors"
          >
            Export Data
          </button>
          <button 
            onClick={handleImport}
            className="px-4 py-2 bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-200 rounded-lg font-medium hover:bg-green-200 dark:hover:bg-green-800 transition-colors"
          >
            Import Data
          </button>
          <button 
            onClick={handleReset}
            className="px-4 py-2 bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-200 rounded-lg font-medium hover:bg-red-200 dark:hover:bg-red-800 transition-colors ml-auto"
          >
            Reset Learning
          </button>
        </div>
      </div>
    </div>
  );
};
