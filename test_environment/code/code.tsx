import { useState } from 'react';
import { testCases } from './data';
import { Terminal, FileCode2, CheckCircle2, AlertTriangle, Bug, Code2, Download, Play, X, Gamepad2, Loader2, Waves } from 'lucide-react';
import { cn } from './lib/utils';
import CodeSwimmers from './CodeSwimmers';

export default function App() {
  const [activeTab, setActiveTab] = useState(testCases[0].id);
  const [activeFile, setActiveFile] = useState<'broken' | 'test' | 'fixed'>('broken');
  
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [isRunning, setIsRunning] = useState(false);
  const [testOutput, setTestOutput] = useState('');
  
  const [view, setView] = useState<'benchmark' | 'game'>('benchmark');

  const activeCase = testCases.find(c => c.id === activeTab) || testCases[0];

  const runTests = async () => {
    setIsModalOpen(true);
    setIsRunning(true);
    setTestOutput("Initializing test runner...\n");
    try {
      const res = await fetch('/api/run-tests');
      const data = await res.json();
      setTestOutput(data.output);
    } catch (err: any) {
      setTestOutput("Failed to connect to test server: " + err.message);
    } finally {
      setIsRunning(false);
    }
  };

  return (
    <div className="min-h-screen bg-neutral-950 text-neutral-300 font-sans selection:bg-indigo-500/30">
      <header className="border-b border-neutral-800 bg-neutral-900/50 backdrop-blur-sm sticky top-0 z-10">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="bg-indigo-500/10 p-2 rounded-lg border border-indigo-500/20">
              <Terminal className="w-5 h-5 text-indigo-400" />
            </div>
            <div>
              <h1 className="text-neutral-100 font-semibold tracking-tight">ANTON-SIFTA Benchmark</h1>
              <p className="text-xs text-neutral-500 font-mono">Code Repair AI Test Suite</p>
            </div>
          </div>
          <div className="flex items-center gap-4">
            <button 
              onClick={() => setView(v => v === 'game' ? 'benchmark' : 'game')}
              className={cn(
                "text-sm flex items-center gap-2 transition-colors px-4 py-1.5 rounded-md font-medium shadow-sm border",
                view === 'game' 
                  ? "bg-neutral-800 text-neutral-200 border-neutral-700 hover:bg-neutral-700"
                  : "bg-blue-600 text-blue-50 border-blue-500 hover:bg-blue-500"
              )}
            >
              <Waves className="w-4 h-4" />
              {view === 'game' ? 'Exit Game' : 'Play Code Swimmers'}
            </button>
            <button 
              onClick={runTests}
              className="text-sm flex items-center gap-2 text-indigo-100 bg-indigo-600 hover:bg-indigo-500 transition-colors px-4 py-1.5 rounded-md font-medium shadow-sm"
            >
              <Play className="w-4 h-4" />
              Run All Tests
            </button>
            <a 
              href="#" 
              className="text-sm flex items-center gap-2 text-neutral-400 hover:text-neutral-200 transition-colors bg-neutral-800/50 px-3 py-1.5 rounded-md border border-neutral-700/50"
              onClick={(e) => {
                e.preventDefault();
                alert("The test suite files have been generated in the /test_suite directory of the project workspace. You can download the project to access them.");
              }}
            >
              <Download className="w-4 h-4" />
              Download Suite
            </a>
          </div>
        </div>
      </header>

      {view === 'game' ? (
        <main className="h-[calc(100vh-4rem)]">
          <CodeSwimmers />
        </main>
      ) : (
        <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
          
          {/* Sidebar */}
          <div className="lg:col-span-3 space-y-6">
            <div>
              <h2 className="text-xs font-semibold text-neutral-500 uppercase tracking-wider mb-3 px-2">Test Cases</h2>
              <nav className="space-y-1">
                {testCases.map((tc) => (
                  <button
                    key={tc.id}
                    onClick={() => setActiveTab(tc.id)}
                    className={cn(
                      "w-full flex items-center gap-3 px-3 py-2.5 text-sm rounded-lg transition-all duration-200 text-left",
                      activeTab === tc.id 
                        ? "bg-indigo-500/10 text-indigo-300 border border-indigo-500/20 shadow-sm" 
                        : "text-neutral-400 hover:bg-neutral-800/50 hover:text-neutral-200 border border-transparent"
                    )}
                  >
                    {activeTab === tc.id ? <AlertTriangle className="w-4 h-4" /> : <FileCode2 className="w-4 h-4 opacity-50" />}
                    <span className="truncate">{tc.title}</span>
                  </button>
                ))}
              </nav>
            </div>

            <div className="bg-neutral-900/50 border border-neutral-800 rounded-xl p-4">
              <h3 className="text-sm font-medium text-neutral-200 mb-2">About this suite</h3>
              <p className="text-xs text-neutral-400 leading-relaxed">
                These test cases simulate functional safety and logic errors in Python. They are designed to evaluate the capability of AI agents to identify and repair software-induced faults.
              </p>
            </div>
          </div>

          {/* Main Content */}
          <div className="lg:col-span-9 flex flex-col min-h-[600px]">
            <div className="mb-6">
              <h2 className="text-2xl font-semibold text-neutral-100 tracking-tight mb-2">{activeCase.title}</h2>
              <p className="text-neutral-400">{activeCase.description}</p>
            </div>

            <div className="flex-1 bg-[#0d0d0d] border border-neutral-800 rounded-xl overflow-hidden flex flex-col shadow-xl">
              <div className="flex items-center border-b border-neutral-800 bg-neutral-900/80 px-2">
                <div className="flex space-x-1 py-2">
                  <button
                    onClick={() => setActiveFile('broken')}
                    className={cn(
                      "flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-md transition-colors",
                      activeFile === 'broken' 
                        ? "bg-red-500/10 text-red-400" 
                        : "text-neutral-500 hover:text-neutral-300 hover:bg-neutral-800/50"
                    )}
                  >
                    <Bug className="w-4 h-4" />
                    broken.py
                  </button>
                  <button
                    onClick={() => setActiveFile('test')}
                    className={cn(
                      "flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-md transition-colors",
                      activeFile === 'test' 
                        ? "bg-blue-500/10 text-blue-400" 
                        : "text-neutral-500 hover:text-neutral-300 hover:bg-neutral-800/50"
                    )}
                  >
                    <Code2 className="w-4 h-4" />
                    test.py
                  </button>
                  <button
                    onClick={() => setActiveFile('fixed')}
                    className={cn(
                      "flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-md transition-colors",
                      activeFile === 'fixed' 
                        ? "bg-emerald-500/10 text-emerald-400" 
                        : "text-neutral-500 hover:text-neutral-300 hover:bg-neutral-800/50"
                    )}
                  >
                    <CheckCircle2 className="w-4 h-4" />
                    fixed.py
                  </button>
                </div>
              </div>
              <div className="flex-1 p-4 overflow-auto">
                <pre className="font-mono text-sm leading-relaxed">
                  <code className={cn(
                    activeFile === 'broken' && "text-red-300/90",
                    activeFile === 'test' && "text-blue-300/90",
                    activeFile === 'fixed' && "text-emerald-300/90",
                  )}>
                    {activeCase[activeFile]}
                  </code>
                </pre>
              </div>
            </div>
          </div>
        </div>
      </main>
      )}

      {/* Modal for Test Results and Games List */}
      {isModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 sm:p-6">
          <div 
            className="absolute inset-0 bg-black/60 backdrop-blur-sm"
            onClick={() => setIsModalOpen(false)}
          />
          <div className="relative bg-neutral-900 border border-neutral-800 rounded-2xl shadow-2xl w-full max-w-5xl max-h-[85vh] flex flex-col overflow-hidden animate-in fade-in zoom-in-95 duration-200">
            
            {/* Modal Header */}
            <div className="flex items-center justify-between px-6 py-4 border-b border-neutral-800 bg-neutral-900/80">
              <div className="flex items-center gap-3">
                <div className="bg-indigo-500/20 p-2 rounded-lg">
                  <Terminal className="w-5 h-5 text-indigo-400" />
                </div>
                <h2 className="text-lg font-semibold text-neutral-100">Test Execution Results</h2>
              </div>
              <button 
                onClick={() => setIsModalOpen(false)}
                className="p-2 text-neutral-400 hover:text-neutral-200 hover:bg-neutral-800 rounded-lg transition-colors"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Modal Body */}
            <div className="flex-1 overflow-hidden flex flex-col lg:flex-row">
              
              {/* Terminal Output Area */}
              <div className="flex-1 p-6 overflow-auto bg-[#0a0a0a] border-r border-neutral-800">
                <div className="flex items-center gap-2 mb-4 text-sm text-neutral-400 font-mono">
                  {isRunning ? (
                    <>
                      <Loader2 className="w-4 h-4 animate-spin text-indigo-400" />
                      Running test suite...
                    </>
                  ) : (
                    <>
                      <CheckCircle2 className="w-4 h-4 text-emerald-500" />
                      Execution finished
                    </>
                  )}
                </div>
                <pre className="font-mono text-sm text-neutral-300 whitespace-pre-wrap leading-relaxed">
                  {testOutput}
                </pre>
              </div>

              {/* Games List Sidebar */}
              <div className="w-full lg:w-80 bg-neutral-900 p-6 overflow-y-auto">
                <div className="flex items-center gap-2 mb-6">
                  <Gamepad2 className="w-5 h-5 text-purple-400" />
                  <h3 className="font-semibold text-neutral-200">Mini Games</h3>
                </div>
                <p className="text-xs text-neutral-500 mb-4">
                  Take a break while the tests run! Here are some classic games to play:
                </p>
                <ul className="space-y-3">
                  {[
                    { name: "Space Invaders", desc: "Defend the earth from aliens" },
                    { name: "Pac-Man", desc: "Eat dots and avoid ghosts" },
                    { name: "Tetris", desc: "Stack the falling blocks" },
                    { name: "Snake", desc: "Grow the snake, don't hit the walls" },
                    { name: "Pong", desc: "Classic table tennis" }
                  ].map((game, i) => (
                    <li key={i} className="group p-3 rounded-lg border border-neutral-800 bg-neutral-950/50 hover:bg-neutral-800 hover:border-neutral-700 transition-all cursor-pointer">
                      <div className="font-medium text-sm text-neutral-200 group-hover:text-purple-400 transition-colors">
                        {game.name}
                      </div>
                      <div className="text-xs text-neutral-500 mt-1">
                        {game.desc}
                      </div>
                    </li>
                  ))}
                </ul>
              </div>

            </div>
          </div>
        </div>
      )}
    </div>
  );
}
