import React from 'react';
import { PAY_TABLE, PAY_TABLE_ORDER } from '../constants';

interface PayTableProps {
    betAmount: number;
    handResult: string;
}

const PayTable: React.FC<PayTableProps> = ({ betAmount, handResult }) => {
    return (
        <div className="w-full pt-1 px-3">
            <div className="grid grid-cols-2 gap-x-4 gap-y-0 text-xs font-mono">
                {PAY_TABLE_ORDER.map((handName) => {
                    const payout = PAY_TABLE[handName] || 0;
                    const isWinningHand = handName === handResult && payout > 0;
                    
                    const rowClasses = `
                        transition-colors duration-300 rounded-md
                        ${isWinningHand ? 'bg-brand-yellow text-brand-dark-bg' : 'text-slate-300'}
                    `;

                    return (
                        <React.Fragment key={handName}>
                            <div className={`text-left font-medium px-2 leading-tight ${rowClasses}`}>
                                {handName}
                            </div>
                            <div className={`text-right font-semibold px-2 leading-tight ${rowClasses}`}>
                                {(payout * betAmount).toLocaleString()}
                            </div>
                        </React.Fragment>
                    );
                })}
            </div>
        </div>
    );
};

export default PayTable;