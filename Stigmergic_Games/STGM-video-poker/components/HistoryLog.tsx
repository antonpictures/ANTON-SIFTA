import React from 'react';
import { GambleHistoryItem } from '../types';

interface HistoryLogProps {
    history: GambleHistoryItem[];
}

const HistoryLog: React.FC<HistoryLogProps> = ({ history }) => {
    
    const formatTimestamp = (timestamp: number) => {
        return new Date(timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    };

    return (
        <div className="w-full mt-1">
            <h3 className="text-center text-sm font-semibold text-slate-400 mb-2">GAMBLE HISTORY</h3>
            <div className="bg-brand-panel-bg rounded-2xl p-3 shadow-lg h-40 overflow-y-auto">
                {history.length === 0 ? (
                    <div className="flex items-center justify-center h-full">
                        <p className="text-slate-500">Your gamble results will appear here.</p>
                    </div>
                ) : (
                    <ul className="space-y-2">
                        {history.map(item => {
                            return (
                                <li 
                                    key={item.id} 
                                    className={`flex justify-between items-center text-sm p-2 rounded-lg ${
                                        item.outcome === 'cashed_out' ? 'bg-green-500/10' : 'bg-red-500/10'
                                    }`}
                                >
                                    <div className="flex items-center flex-wrap">
                                        <span className={`font-bold w-20 shrink-0 ${
                                            item.outcome === 'cashed_out' ? 'text-brand-green' : 'text-brand-red'
                                        }`}>
                                            {item.outcome === 'cashed_out' ? 'CASH OUT' : 'LOST'}
                                        </span>

                                        {item.outcome === 'cashed_out' && item.wonCards && item.wonCards.length > 0 && (
                                            <div className="flex items-center ml-2 space-x-1 flex-wrap">
                                                {item.wonCards.map((card, index) => {
                                                    const isCardRed = card.suit === '♥' || card.suit === '♦';
                                                    return (
                                                        <span key={index} className={`inline-block px-1.5 py-0.5 rounded text-xs font-bold text-white ${
                                                            isCardRed ? 'bg-brand-red' : 'bg-black'
                                                        }`}>
                                                            {card.value}{card.suit}
                                                        </span>
                                                    );
                                                })}
                                            </div>
                                        )}

                                        {item.outcome === 'lost' && (
                                            <div className="flex items-center ml-2 space-x-1 flex-wrap">
                                                {item.wonCards?.map((card, index) => {
                                                    const isCardRed = card.suit === '♥' || card.suit === '♦';
                                                    return (
                                                        <span key={`win-${index}`} className={`inline-block px-1.5 py-0.5 rounded text-xs font-bold text-white opacity-70 ${
                                                            isCardRed ? 'bg-brand-red' : 'bg-black'
                                                        }`}>
                                                            {card.value}{card.suit}
                                                        </span>
                                                    );
                                                })}
                                                {item.finalCard && (
                                                    <span className={`inline-block px-1.5 py-0.5 rounded text-xs font-bold text-white ring-2 ring-offset-1 ring-offset-brand-panel-bg ring-brand-red ${
                                                        (item.finalCard.suit === '♥' || item.finalCard.suit === '♦') ? 'bg-brand-red' : 'bg-black'
                                                    }`}>
                                                        {item.finalCard.value}{item.finalCard.suit}
                                                    </span>
                                                )}
                                            </div>
                                        )}
                                        
                                        <span className="text-slate-300 ml-2">
                                            {item.amount.toLocaleString()} $MPS
                                        </span>
                                    </div>
                                    <div className="text-right flex items-center">
                                        <span className="text-slate-400 mr-2 shrink-0">(Streak: {item.streak})</span>
                                        <span className="text-xs text-slate-500 shrink-0">{formatTimestamp(item.timestamp)}</span>
                                    </div>
                                </li>
                            );
                        })}
                    </ul>
                )}
            </div>
        </div>
    );
};

export default HistoryLog;